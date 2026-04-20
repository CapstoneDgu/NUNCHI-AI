"""결제 에이전트 노드

주문 확정(confirm_order) → 결제 요청(request_payment) → 세션 종료(complete_session)
흐름을 순서대로 처리하는 ReAct 에이전트.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from mcp.server import make_payment_tools
from service.graph.state import KioskState

_PAYMENT_SYSTEM_PROMPT = """
너는 키오스크 결제 AI 어시스턴트다.
사용자가 결제를 완료할 수 있도록 단계별로 안내해줘.

결제 순서:
1. tool_confirm_order 로 주문을 확정한다. (order_id 반환됨)
2. tool_request_payment 로 결제를 요청한다. (order_id와 결제 수단 필요)
3. tool_complete_session 으로 세션을 종료한다.

결제 수단:
- 카드 결제 → IC_CARD
- 정맥 인증 → VEIN_AUTH

규칙:
- 결제 수단을 사용자에게 먼저 확인하고 진행해라.
- 결제 정보(카드번호 등 민감 정보)는 절대 로그나 응답에 포함하지 마라.
- 응답은 한국어로 친절하고 간결하게 해라.
""".strip()


async def run_payment_agent(state: KioskState, spring: SpringAdapter) -> dict:
    """결제 흐름 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0,  # 결제는 일관성이 중요하므로 0
    )

    tools = make_payment_tools(spring, state["session_id"])
    agent = create_react_agent(llm, tools, prompt=_PAYMENT_SYSTEM_PROMPT)

    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}
