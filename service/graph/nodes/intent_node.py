"""의도 분류 노드

사용자의 마지막 발화를 보고 어떤 에이전트 노드로 분기할지 결정한다.
분류 결과: order / payment / recommend / hesitation
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.config import get_settings
from core.model_context import get_current_model
from service.graph.state import KioskState

_INTENT_SYSTEM_PROMPT = """
너는 키오스크 AI의 의도 분류기다.
사용자의 발화를 보고 아래 5가지 중 하나만 반환해라. 다른 말은 절대 하지 마라.

- order      : 메뉴 탐색, 장바구니 담기/수정/삭제, 메뉴 문의, 장바구니 초기화 요청("처음부터", "다시 할게요", "취소"),
               옵션/추가 항목 거절("계란 추가 안 할게", "옵션 없이", "그냥 줘", "기본으로")
- payment    : 결제 요청, 주문 확정, 결제 수단 선택("카드로", "정맥으로", "결제할게요", "주문할게요"),
               더 이상 주문할 메뉴가 없다는 명확한 의사 표현("없어요", "됐어요", "그게 다야", "다 됐어요", "이게 다야")
- recommend  : 추천 요청, 뭐가 맛있냐, 인기 메뉴가 뭐냐, 조건 기반 추천 요청
- hesitation : 망설임, 침묵 후 재개, "음...", "뭐가 좋지", 결정 못 하는 발화
- clarify    : 키오스크 주문과 무관한 발화 (날씨/시간/잡담/욕설/광고/의미 불명),
               단순 인사("안녕", "안녕하세요", "처음이야"),
               단어 나열만 있고 의도가 불명확("국밥 삶기", "맛있는 거" 같은 모호한 한 마디)

판단 기준 (우선순위 순):
- "카드", "정맥", "결제" 단어가 포함된 발화는 반드시 payment 로 분류한다.
- "추가 안 할게", "옵션 없이", "기본으로", "그냥 담아줘" 처럼 옵션/추가 항목을 거절하는 발화는 order 로 분류한다. payment 가 아니다.
- "없어요", "됐어요", "그게 다야", "다 됐어요" 는 대화 맥락상 추가 주문이 없다는 확정 발화이면 payment, 옵션 거절이면 order 로 분류한다.
- "처음부터", "다시 할게요", "전부 취소" 는 order 로 분류한다.
- "아니요" 단독 발화는 대화 맥락을 보고 판단하되, 옵션 선택 중이면 order 로 분류한다.
- 단순 인사("안녕") · 키오스크와 무관한 잡담 · 의미 불명 단어 나열은 반드시 clarify 로 분류한다.
""".strip()


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=get_current_model(s.openai_model),
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
    if intent not in ("order", "payment", "recommend", "hesitation", "clarify"):
        intent = "clarify"  # 분류 실패 시 기본값 (OOD 발화로 간주)

    logging.debug("[의도 분류] 입력: %r → intent: %s", last_message.content, intent)

    return {"intent": intent}


def route_by_intent(state: KioskState) -> str:
    """조건부 엣지 함수 — intent 값을 다음 노드 이름으로 반환한다."""
    return state.get("intent") or "order"
