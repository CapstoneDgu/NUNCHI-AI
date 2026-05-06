"""의도 분류 노드

사용자의 마지막 발화를 보고 어떤 에이전트 노드로 분기할지 결정한다.
분류 결과: order / payment / recommend / hesitation
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.config import get_settings
from service.graph.state import KioskState

_INTENT_SYSTEM_PROMPT = """
너는 키오스크 AI의 의도 분류기다.
사용자의 발화를 보고 아래 4가지 중 하나만 반환해라. 다른 말은 절대 하지 마라.

- order      : 메뉴 탐색, 장바구니 담기/수정/삭제, 메뉴 문의, 장바구니 초기화 요청("처음부터", "다시 할게요", "취소")
- payment    : 결제 요청, 주문 확정, 결제 수단 선택("카드로", "정맥으로", "결제할게요", "주문할게요"),
               추가 주문이 없음을 밝히는 발화("없어요", "됐어요", "그게 다야", "아니요", "다 됐어요")
- recommend  : 추천 요청, 뭐가 맛있냐, 인기 메뉴가 뭐냐, 조건 기반 추천 요청
- hesitation : 망설임, 침묵 후 재개, "음...", "뭐가 좋지", 결정 못 하는 발화

판단 기준:
- "없어요", "됐어요", "그게 다야", "아니요" 처럼 추가 주문이 없다는 의사 표현은 반드시 payment 로 분류한다.
- "카드", "정맥", "결제" 단어가 포함된 발화는 반드시 payment 로 분류한다.
- "처음부터", "다시 할게요", "전부 취소" 는 order 로 분류한다.
""".strip()


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.openai_model,
        api_key=s.openai_api_key,
        temperature=0,
    )


async def classify_intent(state: KioskState) -> dict:
    """사용자 발화에서 의도를 분류해 state['intent']를 업데이트한다."""
    llm = _build_llm()

    if not state["messages"]:
        return {"intent": "order"}
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

    logging.debug("[의도 분류] 입력: %r → intent: %s", last_message.content, intent)

    return {"intent": intent}


def route_by_intent(state: KioskState) -> str:
    """조건부 엣지 함수 — intent 값을 다음 노드 이름으로 반환한다."""
    return state.get("intent") or "order"
