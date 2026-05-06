"""주문 에이전트 노드

메뉴 탐색, 장바구니 담기/수정/삭제를 처리하는 ReAct 에이전트.
MultiServerMCPClient로 FastMCP 서버에 연결해 Tool 목록을 가져온다.
"""

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.config import get_settings
from service.graph.state import KioskState

_ORDER_SYSTEM_PROMPT = """
너는 키오스크 주문 AI 어시스턴트다.
사용자가 메뉴를 탐색하거나 장바구니를 관리할 수 있도록 도와줘.

[NER + 메뉴 검색 플로우]
1. 사용자 발화에서 메뉴명을 추출한다.
2. tool_search_menus(name=추출한_메뉴명) 을 호출해 menuId를 확보한다.
3. 검색 결과가 여럿이면 대화 맥락에서 가장 적합한 것을 선택한다.
4. tool_add_cart_item(menuId=..., quantity=..., optionIds=[]) 으로 장바구니에 담는다.

[병렬 주문]
사용자가 여러 메뉴를 동시에 말하면 순서대로 (search → add) 를 반복한다.

[루프백]
장바구니에 담은 후 반드시 "더 시키실 메뉴가 있나요?" 라고 묻는다.
- 있다 → tool_update_step(step="BROWSE") 호출 후 계속 진행
- 없다 → 결제 단계로 안내

[건너뛰기]
메뉴+수량+결제 의사가 한 발화에 모두 있으면 단계를 무시하고 바로 담기+결제로 진행한다.

[장바구니 초기화]
사용자가 "처음부터", "다시 할게요", "전부 취소" 등을 말하면 tool_clear_cart(session_id=...) 를 호출한다.

규칙:
- 메뉴를 장바구니에 담기 전에 반드시 tool_get_menu_detail을 먼저 호출해 옵션을 확인해라.
- 옵션이 없으면 option_ids는 빈 배열([])로 전달해라.
- 메뉴명이나 가격을 임의로 만들지 말고 반드시 Tool로 조회한 결과만 사용해라.
- 응답은 한국어로 친절하고 간결하게 해라.
""".strip()


def _bind_session_id(tools: list[BaseTool], session_id: int) -> list[BaseTool]:
    """session_id 파라미터를 가진 tool에 state의 session_id를 강제 주입한다.
    LLM이 전달한 값을 무시하고 항상 state 값으로 덮어써서 세션 혼동을 방지한다."""
    result = []
    for tool in tools:
        if "session_id" not in (tool.args or {}):
            result.append(tool)
            continue

        original_coroutine = tool.coroutine

        async def _wrapped(*args, _orig=original_coroutine, _sid=session_id, **kwargs):
            kwargs["session_id"] = _sid
            return await _orig(*args, **kwargs)

        tool.coroutine = _wrapped
        result.append(tool)
    return result


_AVATAR_TONE = (
    "너는 눈치 키오스크의 아바타 AI야. 이름은 '눈치'야.\n"
    "말투: 친근하고 따뜻하게, 짧고 자연스럽게.\n"
    "이모지는 쓰지 말고, 키오스크 앞에 서 있는 사람에게 말하는 것처럼 응대해줘.\n\n"
)

_NORMAL_TONE = (
    "너는 키오스크 주문 보조 AI야.\n"
    "말투: 간결하고 정확하게.\n\n"
)


async def run_order_agent(state: KioskState) -> dict:
    """주문/장바구니 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    session_id = state["session_id"]
    mode = state.get("mode", "NORMAL")

    tone = _AVATAR_TONE if mode == "AVATAR" else _NORMAL_TONE
    system_prompt = tone + _ORDER_SYSTEM_PROMPT

    llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0.3)

    async with MultiServerMCPClient(
        {"kiosk": {"url": f"{s.mcp_server_url}/sse", "transport": "sse"}}
    ) as client:
        raw_tools = await client.get_tools()
        tools = _bind_session_id(raw_tools, session_id)
        agent = create_react_agent(llm, tools, prompt=system_prompt)
        result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"]}
