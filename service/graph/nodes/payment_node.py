"""결제 에이전트 노드

주문 확정(confirm_order) → 결제 요청(request_payment) → 세션 종료(complete_session)
흐름을 순서대로 처리하는 ReAct 에이전트.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.config import get_settings
from core.model_context import get_current_model
from service.graph.state import KioskState

_PAYMENT_SYSTEM_PROMPT = """
너는 키오스크 결제 안내 AI다.

[가장 중요 — 반드시 지켜라]
너는 결제를 직접 완료하지 않는다. 실제 결제(주문 확정, 카드/정맥/바코드 인증)는
키오스크 "화면(UI)"에서 사용자가 직접 진행한다. 너의 역할은 그 화면으로 안내하는 것뿐이다.
- tool_confirm_order, tool_request_payment, tool_complete_session 등 어떤 결제 관련 tool 도 절대 호출하지 마라.
- "결제가 완료되었습니다" 처럼 결제가 끝났다고 말하지 마라. 완료는 화면에서 일어난다.
- 너는 tool 을 호출할 필요가 전혀 없다.

[역할]
사용자가 결제/주문 완료 의사를 보이면, 알맞은 결제 화면으로 이동시키는 navigate action 을 반드시 반환한다.
화면이 전환되면서 실제 흐름이 진행되도록 하는 것이 핵심이다.

화면 액션(action) 규칙 — 반드시 아래대로:
- 결제/주문 완료/계산 의사("결제할게", "주문할게", "계산", "다 골랐어", "이제 됐어", "이걸로 주문")
  → {"type": "navigate", "page": "/summary"}   (주문 확인 화면으로)
- 결제 수단을 명시("카드/신용카드/IC카드", "정맥/정맥인증", "카카오페이/카카오바코드/바코드")
  → {"type": "navigate", "page": "/payment"}    (결제 화면에서 수단 선택)
- 결제와 무관하거나 단순 질문이면 action 은 null.

reply 규칙:
- 짧고 친절하게. 화면을 옮긴다는 안내를 담아라.
  예: "주문 확인 화면으로 갈게요. 확인하시고 결제 진행해주세요."
  예: "결제 화면으로 갈게요. 결제 수단을 선택해주세요."
- 마크다운 서식(**, *, #, `, _ 등) 금지. 순수 텍스트로만.

상황별 suggestions:
- 주문 확인 안내: ["결제할게", "메뉴 더 추가할게", "장바구니 확인해줘"]
- 결제 수단 안내: ["카드로 결제할게", "정맥으로 결제할게", "카카오페이로 결제할게"]

출력 형식:
```json
{
  "reply": "<응답 텍스트>",
  "suggestions": ["<다음 발화 1>", "<다음 발화 2>", "<다음 발화 3>"],
  "action": {"type": "navigate", "page": "/summary"}
}
```
""".strip()


async def run_payment_agent(state: KioskState) -> dict:
    """결제 흐름 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    session_id = state["session_id"]
    prompt = _PAYMENT_SYSTEM_PROMPT + f"\n\n현재 세션 ID: {session_id}"

    llm = ChatOpenAI(model=get_current_model(s.openai_model), api_key=s.openai_api_key, temperature=0, streaming=True)

    # 결제 노드는 화면 안내만 한다 — 결제 완료용 MCP tool 을 주지 않아 백엔드 결제를 못 한다.
    agent = create_react_agent(llm, [], prompt=prompt)
    result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"], "current_step": "CHECKOUT"}
