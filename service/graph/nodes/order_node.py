"""주문 에이전트 노드

메뉴 탐색, 장바구니 담기/수정/삭제를 처리하는 ReAct 에이전트.
MultiServerMCPClient로 FastMCP 서버에 연결해 Tool 목록을 가져온다.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.config import get_settings
from service.graph.state import KioskState

_ORDER_SYSTEM_PROMPT = """
너는 키오스크 주문 AI 어시스턴트다.
사용자가 메뉴를 탐색하거나 장바구니를 관리할 수 있도록 도와줘.

규칙:
- 메뉴를 장바구니에 담기 전에 반드시 tool_get_menu_detail을 먼저 호출해 옵션을 확인해라.
- 옵션이 없으면 option_ids는 빈 배열([])로 전달해라.
- 메뉴명이나 가격을 임의로 만들지 말고 반드시 Tool로 조회한 결과만 사용해라.
- 장바구니/주문 관련 Tool 호출 시 반드시 session_id 파라미터를 포함해라.
- 응답은 한국어로 친절하고 간결하게 해라.
""".strip()


async def run_order_agent(state: KioskState) -> dict:
    """주문/장바구니 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    session_id = state["session_id"]
    prompt = _ORDER_SYSTEM_PROMPT + f"\n\n현재 세션 ID: {session_id}"

    llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0.3)

    async with MultiServerMCPClient(
        {"kiosk": {"url": f"{s.mcp_server_url}/sse", "transport": "sse"}}
    ) as client:
        tools = client.get_tools()
        agent = create_react_agent(llm, tools, prompt=prompt)
        result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"]}
