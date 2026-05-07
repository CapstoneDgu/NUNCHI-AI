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
현재 단계와 사용자 발화를 보고 다음 단계를 결정해라.

단계 정의:
- BROWSE    : 큰 카테고리 결정 전 (무엇을 먹을지 아직 모름)
- SELECT    : 카테고리는 정해졌지만 메뉴 미정
- CONFIGURE : 메뉴는 정해졌고 수량/옵션 결정 중
- CHECKOUT  : 담기가 끝나고 결제로 가야 할 때

결정 규칙:
- 사용자가 메뉴+수량+결제 의사를 한 번에 말하면 → CHECKOUT
- 장바구니 담고 "더 없어요"라고 하면 → CHECKOUT
- 추가 주문이 생기면 → BROWSE
- 결제가 완료되면 → null (세션 종료)

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
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break

    response = await llm.ainvoke([
        {"role": "system", "content": _STEP_SYSTEM_PROMPT},
        {"role": "user", "content": f"현재 단계: {current_step}\n사용자 발화: {last_user_msg}"},
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
