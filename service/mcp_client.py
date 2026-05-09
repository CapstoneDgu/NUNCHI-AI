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
        {"kiosk": {"url": f"{s.mcp_server_url}/sse", "transport": "sse"}}
    )
    tools = await client.get_tools()
    _client = client
    _tools = tools


def get_mcp_tools() -> list[BaseTool]:
    if _tools is None:
        raise RuntimeError("MCP 클라이언트가 초기화되지 않았습니다. lifespan에서 initialize_mcp_client()를 먼저 호출하세요.")
    return list(_tools)
