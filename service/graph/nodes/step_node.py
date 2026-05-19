"""step_transition 노드

LLM이 현재 단계와 사용자 발화를 보고 다음 주문 단계를 결정한 뒤
Spring에 동기화한다.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from adapter.factory import get_spring_adapter
from core.config import get_settings
from kiosk_mcp.tools.session_tools import update_step

if TYPE_CHECKING:
    from service.graph.state import KioskState

_STEP_SYSTEM_PROMPT = """
현재 단계, 사용자 발화, AI 응답을 보고 다음 단계를 결정해라.

단계 정의:
- BROWSE    : 메뉴를 추가로 탐색 중 (담은 뒤 더 볼 것이 있을 때)
- SELECT    : 카테고리는 정해졌지만 메뉴 미정 (처음 탐색 시작)
- CONFIGURE : 메뉴는 정해졌고 수량/옵션 결정 중
- CHECKOUT  : 담기가 끝나고 결제로 가야 할 때

결정 규칙 (우선순위 순):
1. AI 응답에 "더 시키실 메뉴" 또는 "추가로 시키실" 문구가 있으면 → BROWSE
2. AI 응답에 "결제로 넘어가" 또는 "결제를 진행" 문구가 있으면 → CHECKOUT
3. 사용자가 메뉴+수량+결제 의사를 한 발화에 모두 말하면 → CHECKOUT
4. 사용자가 "없어요", "됐어요", "그게 다야", "아니요" 처럼 추가 없음을 말하면 → CHECKOUT
5. AI 응답에 옵션 선택을 요청하는 내용이 있으면 → CONFIGURE
6. AI 응답에 메뉴를 장바구니에 담았다는 내용이 있으면 → BROWSE
7. AI 응답에 특정 카테고리 내 메뉴 목록을 나열하거나 "골라보세요", "어떤 메뉴로 드릴까요?" 문구가 있으면 → SELECT
8. 그 외 → BROWSE

다음 단계 enum 값 하나만 출력해라. 반드시 아래 중 하나:
BROWSE / SELECT / CONFIGURE / CHECKOUT / null
""".strip()


async def transition_step(state: "KioskState") -> dict:
    """LLM이 다음 주문 단계를 결정하고 Spring에 동기화한다."""
    s = get_settings()
    llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0)

    messages = state.get("messages", [])
    current_step = state.get("current_step")
    session_id = state.get("session_id")

    last_user_msg = ""
    last_ai_msg = ""
    for msg in reversed(messages):
        if not last_ai_msg and hasattr(msg, "type") and msg.type == "ai":
            content = msg.content
            try:
                import json as _json
                import re as _re
                m = _re.search(r'\{.*\}', content, _re.DOTALL)
                if m:
                    data = _json.loads(m.group())
                    content = data.get("reply") or data.get("message") or content
            except Exception:
                pass
            last_ai_msg = content[:300]
        if not last_user_msg and hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
        if last_user_msg and last_ai_msg:
            break

    response = await llm.ainvoke([
        {"role": "system", "content": _STEP_SYSTEM_PROMPT},
        {"role": "user", "content": f"현재 단계: {current_step}\n사용자 발화: {last_user_msg}\nAI 응답: {last_ai_msg}"},
    ])

    _VALID_STEPS = {"BROWSE", "SELECT", "CONFIGURE", "CHECKOUT"}
    raw = response.content.strip().strip("`\"' .").upper()
    if raw == "NULL":
        next_step = None
    elif raw in _VALID_STEPS:
        next_step = raw
    else:
        logging.warning(f"[step 결정 형식 오류] raw={response.content!r} session={session_id}")
        return {"current_step": current_step}

    if next_step and session_id:
        spring = get_spring_adapter()
        try:
            await update_step(spring, session_id, next_step)
        except Exception as exc:
            logging.warning(f"[step 동기화 실패] session={session_id} step={next_step} | {exc}")

    return {"current_step": next_step}
