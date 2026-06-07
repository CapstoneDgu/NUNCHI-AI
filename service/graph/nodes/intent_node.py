"""의도 분류 노드

사용자의 마지막 발화를 보고 어떤 에이전트 노드로 분기할지 결정한다.
분류 결과: order / payment / recommend / hesitation
"""

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.llm_factory import build_llm
from service.graph.state import KioskState

_INTENT_SYSTEM_PROMPT = """
너는 키오스크 AI의 의도 분류기다.
사용자의 발화를 보고 아래 5가지 중 하나만 반환해라. 다른 말은 절대 하지 마라.

- order      : 메뉴 탐색, 메뉴 문의(있는지/가격/구성/맵기/양 등 "삼겹솥밥 있나", "얼마예요", "뭐 들어가요"),
               특정 음식·메뉴 이름 언급(우리 매장에 없는 메뉴여도 order),
               장바구니 담기/수정/삭제, 장바구니 초기화("처음부터", "다시 할게요", "취소"),
               옵션/추가 항목 거절("계란 추가 안 할게", "옵션 없이", "그냥 줘", "기본으로")
- payment    : 결제 요청, 주문 확정, 결제 수단 선택("카드로", "정맥으로", "결제할게요", "주문할게요"),
               더 이상 주문할 메뉴가 없다는 명확한 의사 표현("없어요", "됐어요", "그게 다야", "다 됐어요", "이게 다야")
- recommend  : 추천 요청, 뭐가 맛있냐, 인기 메뉴가 뭐냐, 조건 기반 추천 요청
- hesitation : 망설임, 침묵 후 재개, "음...", "뭐가 좋지", 결정 못 하는 발화
- clarify    : 음식·메뉴·주문·결제와 "전혀" 무관한 발화에만 쓴다 (날씨/시간/뉴스/길찾기/잡담/욕설/광고),
               단순 인사("안녕", "안녕하세요", "처음이야")

판단 기준 (우선순위 순):
- 음식·메뉴 이름이 언급되거나 "있나/있어요/파나요/얼마예요/뭐 들어가요/매워요" 같은 메뉴 문의는
  우리 매장에 없는 메뉴여도 반드시 order 로 분류한다. 절대 clarify 가 아니다.
- "카드", "정맥", "결제" 단어가 포함된 발화는 반드시 payment 로 분류한다.
- "추가 안 할게", "옵션 없이", "기본으로", "그냥 담아줘" 처럼 옵션/추가 항목을 거절하는 발화는 order 로 분류한다. payment 가 아니다.
- "없어요", "됐어요", "그게 다야", "다 됐어요" 는 대화 맥락상 추가 주문이 없다는 확정 발화이면 payment, 옵션 거절이면 order 로 분류한다.
- "X으로 할게", "X로 할게", "X로 해줘", "X 없이", "X 빼줘" 처럼 특정 선택지·옵션·재료를 지정하는 발화는 반드시 order 로 분류한다. (예: "된장국으로 할게", "없음으로 할게", "공기밥 없이 해줘")
- "처음부터", "다시 할게요", "전부 취소" 는 order 로 분류한다.
- "아니요" 단독 발화는 대화 맥락을 보고 판단하되, 옵션 선택 중이면 order 로 분류한다.
- clarify 는 음식/주문과 전혀 관련 없는 발화에만 쓴다. 조금이라도 메뉴·주문 관련이면 order 로 분류한다.
- 애매하면 clarify 가 아니라 order 로 분류한다. (거절보다 주문을 도와주는 쪽으로)

[참고: 직전 AI 메시지]
"네", "응", "아니요", "그래" 처럼 그 자체로는 의미가 없는 짧은 대답은 반드시 직전 AI 메시지가 무엇을 물었는지를 보고 판단해라.
- 직전 AI가 "담아드릴까요?", "결제 진행할까요?", "옵션은 어떻게 해드릴까요?" 등 주문/결제/옵션 관련 질문을 했다면 → 그에 대한 긍정/부정 답변은 order 또는 payment 로 분류한다 (clarify 아님).
- 직전 AI 메시지가 없거나 주문과 무관한 질문이었다면 기존 기준대로 판단한다.
""".strip()


def _extract_ai_reply_text(content) -> str:
    """AI 메시지 content에서 분류기에 보여줄 짧은 텍스트를 뽑아낸다.

    order_agent/recommend_agent 는 JSON 코드 블록으로 응답하므로 그 안의
    reply/message 필드만 추출하고, JSON 이 아니면 원문을 그대로 사용한다.
    """
    if isinstance(content, list):
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    return data.get("reply") or data.get("message") or text


async def classify_intent(state: KioskState) -> dict:
    """사용자 발화에서 의도를 분류해 state['intent']를 업데이트한다."""
    llm = build_llm(temperature=0)

    if not state["messages"]:
        return {"intent": "order"}
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return {"intent": "order"}  # 사용자 발화가 아니면 기본값

    # "네", "응" 같은 짧은 대답은 그 자체로 의미가 없으므로
    # 직전 AI 메시지(무엇을 물었는지)를 함께 보여줘 분류 정확도를 높인다.
    prev_ai_message = next(
        (m for m in reversed(state["messages"][:-1]) if isinstance(m, AIMessage)),
        None,
    )
    classifier_input = last_message.content
    if prev_ai_message is not None:
        prev_reply = _extract_ai_reply_text(prev_ai_message.content)
        if prev_reply:
            classifier_input = f"[직전 AI 메시지] {prev_reply}\n[현재 사용자 발화] {last_message.content}"

    response = await llm.ainvoke([
        SystemMessage(content=_INTENT_SYSTEM_PROMPT),
        HumanMessage(content=classifier_input),
    ])

    intent = response.content.strip().lower()
    if intent not in ("order", "payment", "recommend", "hesitation", "clarify"):
        intent = "order"  # 분류 실패 시 기본값 — 거절(clarify)보다 주문으로 도와준다

    logging.debug("[의도 분류] 입력: %r → intent: %s", classifier_input, intent)

    return {"intent": intent}


def route_by_intent(state: KioskState) -> str:
    """조건부 엣지 함수 — intent 값을 다음 노드 이름으로 반환한다."""
    return state.get("intent") or "order"
