"""결제 에이전트 노드

주문 확정(confirm_order) → 결제 요청(request_payment) → 세션 종료(complete_session)
흐름을 순서대로 처리하는 ReAct 에이전트.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.config import get_settings
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
- 모든 Tool 호출 시 session_id 파라미터를 반드시 포함해라.
- 결제 정보(카드번호 등 민감 정보)는 절대 로그나 응답에 포함하지 마라.
- 응답은 한국어로 친절하고 간결하게 해라.
""".strip()


async def run_payment_agent(state: KioskState) -> dict:
    """결제 흐름 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    session_id = state["session_id"]
    prompt = _PAYMENT_SYSTEM_PROMPT + f"\n\n현재 세션 ID: {session_id}"

    llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0)

    client = MultiServerMCPClient(
        {"kiosk": {"url": f"{s.mcp_server_url}/sse", "transport": "sse"}}
    )
    tools = await client.get_tools()
    agent = create_react_agent(llm, tools, prompt=prompt)
    result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"]}
