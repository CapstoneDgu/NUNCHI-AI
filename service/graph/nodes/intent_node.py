"""의도 분류 노드

사용자의 마지막 발화를 보고 어떤 에이전트 노드로 분기할지 결정한다.
분류 결과: order / payment / recommend / hesitation
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from core.config import get_settings
from service.graph.state import KioskState

_INTENT_SYSTEM_PROMPT = """
너는 키오스크 AI의 의도 분류기다.
사용자의 발화를 보고 아래 4가지 중 하나만 반환해라. 다른 말은 절대 하지 마라.

- order      : 메뉴 탐색, 장바구니 담기/수정/삭제, 메뉴 문의
- payment    : 결제 요청, 주문 확정, 결제 수단 선택
- recommend  : 추천 요청, 뭐가 맛있냐, 인기 메뉴가 뭐냐
- hesitation : 망설임, 침묵 후 재개, "음...", "뭐가 좋지", 결정 못 하는 발화
""".strip()


def _build_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0,  # 의도 분류는 일관성이 중요하므로 0
    )


async def classify_intent(state: KioskState) -> dict:
    """사용자 발화에서 의도를 분류해 state['intent']를 업데이트한다."""
    llm = _build_llm()

    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return {"intent": "order"}  # 사용자 발화가 아니면 기본값

    response = await llm.ainvoke([
        SystemMessage(content=_INTENT_SYSTEM_PROMPT),
        HumanMessage(content=last_message.content),
    ])

    intent = response.content.strip().lower()
    if intent not in ("order", "payment", "recommend", "hesitation"):
        intent = "order"  # 분류 실패 시 기본값

    return {"intent": intent}


def route_by_intent(state: KioskState) -> str:
    """조건부 엣지 함수 — intent 값을 다음 노드 이름으로 반환한다."""
    return state.get("intent") or "order"
