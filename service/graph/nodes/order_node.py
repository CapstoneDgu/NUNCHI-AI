"""주문 에이전트 노드

메뉴 탐색, 장바구니 담기/수정/삭제를 처리하는 ReAct 에이전트.
make_order_tools()로 생성된 Tool 목록을 LangGraph create_react_agent에 주입한다.
"""

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from mcp.server import make_order_tools
from service.graph.state import KioskState

_ORDER_SYSTEM_PROMPT = """
너는 키오스크 주문 AI 어시스턴트다.
사용자가 메뉴를 탐색하거나 장바구니를 관리할 수 있도록 도와줘.

규칙:
- 메뉴를 장바구니에 담기 전에 반드시 tool_get_menu_detail을 먼저 호출해 옵션을 확인해라.
- 옵션이 없으면 option_ids는 빈 배열([])로 전달해라.
- 메뉴명이나 가격을 임의로 만들지 말고 반드시 Tool로 조회한 결과만 사용해라.
- 응답은 한국어로 친절하고 간결하게 해라.
""".strip()


def _build_order_agent(spring: SpringAdapter):
    s = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0.3,
    )
    # 세션 ID는 state에서 가져오므로 노드 실행 시점에 주입
    return llm


async def run_order_agent(state: KioskState, spring: SpringAdapter) -> dict:
    """주문/장바구니 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0.3,
    )

    tools = make_order_tools(spring, state["session_id"])
    agent = create_react_agent(llm, tools, prompt=_ORDER_SYSTEM_PROMPT)

    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}
