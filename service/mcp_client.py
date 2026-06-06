"""MCP 클라이언트 싱글톤

서버 시작 시 한 번만 SSE 연결해 tool 목록을 캐싱한다.
이후 요청은 캐시된 리스트를 즉시 반환해 SSE 핸드셰이크 오버헤드를 제거한다.
"""

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from core.config import get_settings

_client: MultiServerMCPClient | None = None
_tools: list[BaseTool] | None = None


async def initialize_mcp_client() -> None:
    global _client, _tools
    if _client is not None and _tools is not None:
        return
    s = get_settings()
    client = MultiServerMCPClient(
        {"kiosk": {"url": f"{s.mcp_server_url}/", "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    _client = client
    _tools = tools


def get_mcp_tools() -> list[BaseTool]:
    if _tools is None:
        raise RuntimeError("MCP 클라이언트가 초기화되지 않았습니다. lifespan에서 initialize_mcp_client()를 먼저 호출하세요.")
    return list(_tools)


# recommend_agent 에 허용할 tool 이름 — 조회 전용
_RECOMMEND_ALLOWED = {
    "tool_get_categories",
    "tool_get_menus",
    "tool_get_top_menus",
    "tool_get_menu_detail",
    "tool_filter_menus",
    "tool_search_menus",
}


def get_recommend_tools() -> list[BaseTool]:
    """추천 에이전트 전용 tool 목록 — 장바구니/주문/결제 tool 제외."""
    return [t for t in get_mcp_tools() if t.name in _RECOMMEND_ALLOWED]
