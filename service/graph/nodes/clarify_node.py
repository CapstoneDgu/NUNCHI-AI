"""OOD/인사/모호 발화에 대한 응답 노드.

intent_node 가 'clarify' 로 분류한 발화를 받아 "메뉴 주문 관련해서만 도와드릴 수 있어요" 같은
짧은 안내 응답을 생성한다.

LLM 호출 없이 정해진 안내 멘트를 반환해 비용·지연을 줄인다.
"""

import logging

from langchain_core.messages import AIMessage

from service.graph.state import KioskState

# 가벼운 응답 풀 — 발화 유형에 따라 다른 멘트 선택 (기본은 메뉴 안내)
_CLARIFY_REPLIES = {
    "greeting": (
        "안녕하세요! 무엇을 도와드릴까요? "
        "메뉴를 추천해드릴까요, 아니면 직접 골라보시겠어요?"
    ),
    "default": (
        "죄송해요, 메뉴 주문과 관련된 요청만 도와드릴 수 있어요. "
        "메뉴 추천이나 주문을 말씀해 주세요."
    ),
}

# 단순 인사 패턴 (LLM 안 거치고도 빠르게 매칭)
_GREETING_KEYWORDS = (
    "안녕", "안뇽", "처음이야", "처음입니다", "처음이에요", "처음인데",
    "반가", "방가", "하이", "할로", "헬로", "좋은 아침", "좋은 저녁",
)


def _pick_reply(user_text: str) -> str:
    """사용자 발화 문자열 기반으로 적절한 안내 멘트를 고른다."""
    t = (user_text or "").strip().lower()
    if any(k in t for k in _GREETING_KEYWORDS):
        return _CLARIFY_REPLIES["greeting"]
    return _CLARIFY_REPLIES["default"]


async def run_clarify_node(state: KioskState) -> dict:
    """OOD/인사/모호 발화에 짧은 안내 응답을 채워 반환한다."""
    last_user_text = ""
    for msg in reversed(state.get("messages") or []):
        # HumanMessage 우선
        content = getattr(msg, "content", "")
        if msg.__class__.__name__ == "HumanMessage" and isinstance(content, str):
            last_user_text = content
            break

    reply_text = _pick_reply(last_user_text)
    logging.debug("[clarify_node] 입력=%r → reply=%r", last_user_text, reply_text)

    # 응답을 JSON 형식으로 — order_service 의 _parse_agent_reply 가 파싱할 수 있게
    import json
    payload = {
        "reply": reply_text,
        "suggestions": [
            "메뉴 추천해줘",
            "메뉴 직접 볼게",
            "처음부터 다시 할게",
        ],
        "action": None,
    }
    return {
        "messages": [AIMessage(content=json.dumps(payload, ensure_ascii=False))],
        # 현재 단계 그대로 유지 (BROWSE 가 기본)
        "current_step": state.get("current_step") or "BROWSE",
    }
