# FastMCP 서버 전환 계획

**목표**: 현재 `@tool` 방식(FastAPI 내부에서만 동작)을 FastMCP 독립 프로세스로 전환해
Claude Desktop 등 외부 AI 클라이언트에서도 Tool 직접 호출 가능하게 만든다.

---

## 변경 요약

| 구분 | 현재 | 변경 후 |
|------|------|---------|
| Tool 방식 | LangChain `@tool` 데코레이터 | FastMCP `@mcp_app.tool()` |
| 실행 위치 | FastAPI 프로세스 내부 | 포트 8090 독립 프로세스 |
| session_id 주입 | 클로저(팩토리 함수)로 주입 | Tool 파라미터로 직접 전달 |
| nodes 연결 방식 | `make_order_tools(spring, session_id)` | `MultiServerMCPClient` SSE 연결 |
| Spring 어댑터 위치 | 각 노드에서 주입 | MCP 서버 내부에서 전역 생성 |

---

## 변경 파일 목록

### 신규 생성
1. `mcp/mcp_server.py` — FastMCP 서버 본체 (port 8090)
2. `.env.local` — 로컬 개발용 환경 변수 템플릿
3. `docker-compose.yml` — fastapi + mcp 동시 실행 구성

### 수정
4. `requirements.txt` — `mcp[cli]`, `langchain-mcp-adapters` 의존성 추가
5. `core/config.py` — `mcp_server_url` 설정 추가
6. `service/graph/nodes/order_node.py` — `make_order_tools` → `MultiServerMCPClient` 교체
7. `service/graph/nodes/recommend_node.py` — `make_recommend_tools` → `MultiServerMCPClient` 교체
8. `service/graph/nodes/payment_node.py` — `make_payment_tools` → `MultiServerMCPClient` 교체

### 유지 (변경 없음)
- `mcp/tools/*.py` — 비즈니스 로직 그대로 재사용
- `mcp/server.py` — 전환 완료 후 삭제 예정, 지금은 유지

---

## 1단계: 의존성 및 설정 추가

### `requirements.txt` 추가
```
mcp[cli]>=1.0.0
langchain-mcp-adapters>=0.1.0
```

### `core/config.py` 수정
`Settings` 클래스에 아래 필드 추가:
```python
mcp_server_url: str = "http://localhost:8090"
```

---

## 2단계: `mcp/mcp_server.py` 신규 생성

FastMCP 인스턴스 하나에 전체 Tool을 등록한다.
`mcp/tools/*.py`의 함수를 그대로 호출하고, `spring: SpringAdapter`는 서버 시작 시 전역으로 생성한다.
`session_id`는 Tool 파라미터로 직접 받는다.

```python
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from mcp.tools.cart_tools import add_cart_item, get_cart, remove_cart_item, update_cart_item
from mcp.tools.menu_tools import filter_menus, get_categories, get_menu_detail, get_menus, get_top_menus
from mcp.tools.order_tools import confirm_order
from mcp.tools.payment_tools import request_payment
from mcp.tools.session_tools import complete_session, save_tool_log

mcp_app = FastMCP("nunchi-kiosk")
_spring: SpringAdapter | None = None

# --- 메뉴/카테고리 Tool ---

@mcp_app.tool()
async def tool_get_categories() -> str:
    """카테고리 목록을 조회한다."""
    ...

@mcp_app.tool()
async def tool_get_menus(category_id: int | None = None) -> str:
    """메뉴 목록 조회. category_id 지정 시 해당 카테고리만 반환."""
    ...

@mcp_app.tool()
async def tool_get_top_menus(limit: int = 5) -> str:
    """오늘 판매량 기준 인기 메뉴 목록."""
    ...

@mcp_app.tool()
async def tool_get_menu_detail(menu_id: int) -> str:
    """메뉴 상세 + 옵션. 장바구니 담기 전 반드시 호출."""
    ...

@mcp_app.tool()
async def tool_filter_menus(...) -> str:
    """조건(칼로리/알레르기/채식/온도/계절/가격) 기반 메뉴 필터링."""
    ...

# --- 장바구니 Tool ---

@mcp_app.tool()
async def tool_add_cart_item(session_id: int, menu_id: int, quantity: int, option_ids: list[int]) -> str:
    """장바구니에 메뉴 담기."""
    ...

@mcp_app.tool()
async def tool_get_cart(session_id: int) -> str:
    """현재 장바구니 전체 조회."""
    ...

@mcp_app.tool()
async def tool_update_cart_item(session_id: int, item_id: str, quantity: int) -> str:
    """장바구니 수량 수정."""
    ...

@mcp_app.tool()
async def tool_remove_cart_item(session_id: int, item_id: str) -> str:
    """장바구니 아이템 삭제."""
    ...

# --- 주문/결제 Tool ---

@mcp_app.tool()
async def tool_confirm_order(session_id: int) -> str:
    """장바구니를 주문으로 확정. 결제 전 반드시 호출."""
    ...

@mcp_app.tool()
async def tool_request_payment(session_id: int, order_id: int, method: str) -> str:
    """결제 요청. method: IC_CARD | VEIN_AUTH"""
    ...

@mcp_app.tool()
async def tool_complete_session(session_id: int) -> str:
    """주문 세션 종료. 결제 완료 후 호출."""
    ...
```

**진입점 (`__main__`)**:
```python
if __name__ == "__main__":
    import asyncio
    s = get_settings()
    _spring = SpringAdapter(s.spring_base_url)
    mcp_app.run(transport="sse", port=8090)
```

---

## 3단계: nodes 수정 — `MultiServerMCPClient` 교체

세 노드 모두 동일한 패턴으로 변경.
`spring: SpringAdapter` 파라미터 제거, session_id를 시스템 프롬프트에 포함시켜 LLM이 Tool 호출 시 자동으로 넘기게 한다.

### `order_node.py` 변경 패턴
```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from core.config import get_settings

async def run_order_agent(state: KioskState) -> dict:
    s = get_settings()
    session_id = state["session_id"]
    prompt = _ORDER_SYSTEM_PROMPT + f"\n\n현재 세션 ID: {session_id} — 장바구니/주문 Tool 호출 시 반드시 session_id={session_id} 를 전달해라."

    async with MultiServerMCPClient({"kiosk": {"url": s.mcp_server_url + "/sse", "transport": "sse"}}) as client:
        tools = client.get_tools()
        llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0.3)
        agent = create_react_agent(llm, tools, prompt=prompt)
        result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"]}
```

- `recommend_node.py` — 동일 패턴, `make_recommend_tools` 제거
- `payment_node.py` — 동일 패턴, `make_payment_tools` 제거

---

## 4단계: `.env.local` 신규 생성

로컬 개발 시 사용할 환경변수 템플릿 (`.gitignore`에 포함):
```
OPEN_API_KEY=sk-...
SPRING_BASE_URL=http://localhost:8080
MCP_SERVER_URL=http://localhost:8090
```

---

## 5단계: `docker-compose.yml` 신규 생성

같은 AI 이미지를 두 컨테이너로 분리 실행 (FastAPI / MCP 서버).

```yaml
version: "3.9"
services:
  fastapi:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    env_file: .env

  mcp:
    build: .
    command: python -m mcp.mcp_server
    ports:
      - "8090:8090"
    env_file: .env
```

---

## 작업 순서

| 순서 | 파일 | 작업 내용 |
|------|------|----------|
| 1 | `requirements.txt` | `mcp[cli]`, `langchain-mcp-adapters` 추가 |
| 2 | `core/config.py` | `mcp_server_url` 필드 추가 |
| 3 | `mcp/mcp_server.py` | FastMCP 서버 전체 구현 |
| 4 | `service/graph/nodes/order_node.py` | `MultiServerMCPClient` 교체, spring 파라미터 제거 |
| 5 | `service/graph/nodes/recommend_node.py` | 동일 |
| 6 | `service/graph/nodes/payment_node.py` | 동일 |
| 7 | `.env.local` | 로컬 환경변수 템플릿 생성 |
| 8 | `docker-compose.yml` | 서비스 구성 파일 생성 |
| 9 | `mcp/server.py` | 레거시 파일 삭제 |

---

## 로컬 실행 방법 (도커 없이)

터미널 3개를 동시에 실행:
```
# 터미널 1 — Spring
cd spring_project && ./gradlew bootRun

# 터미널 2 — MCP 서버
cd capstone_ai && python -m mcp.mcp_server

# 터미널 3 — FastAPI
cd capstone_ai && uvicorn app.main:app --reload
```

---

## 변경하지 않는 것

- `mcp/tools/*.py` — 비즈니스 로직 그대로 재사용, 함수 시그니처 유지
- Spring 코드 — 수정 없음 (MCP 서버도 동일한 Spring HTTP API 호출)
- 도메인 모델 (`domain/*.py`) — 변경 없음
- `adapter/spring_adapter.py` — 변경 없음
