# MCP 개발 포트폴리오 — NUNCHI KIOSK AI 서버

**프로젝트**: 눈치(NUNCHI) 키오스크 — LLM Agentic AI 기반 자율주문 키오스크  
**역할**: FastAPI AI 서버 설계 및 MCP 서버 구축  
**기간**: 캡스톤 프로젝트 (2026)

---

## 1. MCP란 무엇인가

**MCP(Model Context Protocol)**는 Anthropic이 정의한 개방형 표준 프로토콜로,  
AI 모델(LLM)과 외부 시스템 사이의 Tool 호출 방식을 표준화한다.

### 기존 방식의 한계

```
LLM ──(독자 규격)──> 외부 시스템 A
LLM ──(또 다른 규격)──> 외부 시스템 B
```

플랫폼마다 Tool 정의 방식, 호출 포맷, 인증 방식이 달라 재사용이 불가능했다.

### MCP가 해결하는 것

```
Claude Desktop ─┐
LangGraph Agent ─┤──(MCP 표준)──> MCP Server ──> 실제 시스템 (DB, API 등)
기타 AI 클라이언트 ─┘
```

MCP 서버 하나를 만들면, 이를 지원하는 **모든 AI 클라이언트**에서 동일한 Tool을 호출할 수 있다.

### MCP의 핵심 개념

| 개념 | 설명 |
|------|------|
| **Tool** | AI가 호출할 수 있는 함수. 이름, 파라미터, 반환값으로 구성 |
| **MCP Server** | Tool을 외부에 노출하는 독립 프로세스 |
| **MCP Client** | Tool을 호출하는 쪽 (Claude Desktop, LangGraph 등) |
| **Transport** | 서버-클라이언트 간 통신 방식. `stdio`(로컬) 또는 `SSE`(네트워크) |

### stdio vs SSE 트랜스포트

```
stdio: Claude Desktop ──stdin/stdout──> MCP Server (로컬 프로세스로 실행)
SSE:   LangGraph Agent ──HTTP SSE──────> MCP Server (포트 8090 리슨)
```

이 프로젝트는 두 트랜스포트를 환경변수 하나(`MCP_TRANSPORT`)로 전환 가능하게 설계했다.

---

## 2. 프로젝트 전체 아키텍처

```
[사용자]
   │ 음성 / 터치
   ▼
[React 키오스크 UI]
   │ REST / WebSocket
   ▼
[FastAPI AI 서버]  ◄──── LangGraph (의도 분류 → 에이전트 분기 → Tool 실행)
   │ MultiServerMCPClient (SSE)
   ▼
[FastMCP 서버 — kiosk_mcp]  ◄──── Claude Desktop (stdio)
   │ HTTP REST
   ▼
[Spring Boot 백엔드]
   │
   ▼
[PostgreSQL]
```

**FastMCP 서버는 두 방향에서 동시에 접근 가능하다:**
- 키오스크 내부: LangGraph 에이전트가 SSE로 연결
- 외부: Claude Desktop이 stdio로 직접 연결

---

## 3. 무엇을 만들었나

### 3-1. FastMCP 독립 서버 (`kiosk_mcp/mcp_server.py`)

LangChain `@tool` 방식(FastAPI 프로세스 내부에서만 동작)을 **FastMCP 독립 서버**로 전환했다.

**이전 구조의 문제:**
```python
# FastAPI 안에서만 쓸 수 있는 @tool
@tool
def get_menus(category_id: int) -> str:
    ...
# → 외부 Claude Desktop 접근 불가, 클로저로 spring 주입 필요
```

**전환 후:**
```python
# FastMCP 서버로 외부 공개
mcp_app = FastMCP("nunchi-kiosk")

@mcp_app.tool()
async def tool_get_menus(category_id: Optional[int] = None) -> str:
    """메뉴 목록을 조회한다."""
    ...
```

### 3-2. 구현한 MCP Tool 목록 (총 14개)

| 분류 | Tool | 기능 |
|------|------|------|
| **세션** | `tool_create_session` | 주문 세션 생성, session_id 발급 |
| **세션** | `tool_save_message` | 대화 메시지 DB 저장 (USER/ASSISTANT) |
| **메뉴** | `tool_get_categories` | 카테고리 목록 조회 |
| **메뉴** | `tool_get_menus` | 전체 / 카테고리별 메뉴 조회 |
| **메뉴** | `tool_get_top_menus` | 오늘 판매량 기준 인기 메뉴 |
| **메뉴** | `tool_get_menu_detail` | 메뉴 상세 + 옵션 그룹 조회 |
| **메뉴** | `tool_filter_menus` | 17개 파라미터 복합 필터 (칼로리·가격·알레르기·층·식당명 등) |
| **장바구니** | `tool_add_cart_item` | 메뉴 담기 (옵션 포함) |
| **장바구니** | `tool_get_cart` | 장바구니 전체 조회 |
| **장바구니** | `tool_update_cart_item` | 수량 수정 |
| **장바구니** | `tool_remove_cart_item` | 아이템 삭제 |
| **주문** | `tool_confirm_order` | 장바구니 → 주문 확정 |
| **결제** | `tool_request_payment` | IC_CARD / VEIN_AUTH 결제 요청 |
| **세션** | `tool_complete_session` | 주문 세션 종료 |

### 3-3. LangGraph 기반 AI 에이전트 그래프

사용자 발화를 받아 의도에 따라 에이전트를 분기하는 그래프를 설계했다.

```
입력 ──> [의도 분류기]
              │
    ┌─────────┼──────────┬──────────┐
    ▼         ▼          ▼          ▼
 주문 에이전트 결제 에이전트 추천 에이전트 눈치 감지기
                                        │
                                        ▼
                                   추천 에이전트
```

**눈치(NUNCHI) 기능**: 사용자가 명시적 요청 없이도 망설임 신호(체류시간, 반복탐색, 침묵, 헤징 발화)를 감지해 먼저 추천을 제안한다.

### 3-4. 계층 분리 설계

```
kiosk_mcp/mcp_server.py   ← MCP Tool 진입점 (FastMCP 서버)
kiosk_mcp/tools/*.py      ← Tool 비즈니스 로직 (순수 함수)
adapter/spring_adapter.py ← Spring API HTTP 클라이언트
domain/*.py               ← Pydantic 도메인 모델
```

Tool 로직과 MCP 진입점을 분리해, LangGraph 에이전트와 Claude Desktop 양쪽에서 동일한 비즈니스 로직을 재사용한다.

---

## 4. Claude Desktop에서 이 프로젝트에 접근하는 방법

### 연결 원리

Claude Desktop은 MCP 서버를 **로컬 프로세스로 직접 실행**한다.  
설정 파일(`claude_desktop_config.json`)에 MCP 서버 실행 커맨드를 등록하면,  
Claude Desktop이 앱 시작 시 해당 프로세스를 띄우고 `stdin/stdout`으로 통신한다.

```
Claude Desktop
    │  앱 시작 시 자동 실행
    ▼
python -m kiosk_mcp.mcp_server  (stdio 모드)
    │  HTTP REST
    ▼
Spring Boot (localhost:8080)
    │
    ▼
PostgreSQL (실제 메뉴·주문 데이터)
```

### 실제 등록한 설정 (`claude_desktop_config.json`)

```json
"nunchi-kiosk": {
  "command": "/Users/hyodongg/Desktop/workspace/capstone_ai/venv/bin/python",
  "args": ["-m", "kiosk_mcp.mcp_server"],
  "cwd": "/Users/hyodongg/Desktop/workspace/capstone_ai",
  "env": {
    "MCP_TRANSPORT": "stdio",
    "PYTHONPATH": "/Users/hyodongg/Desktop/workspace/capstone_ai",
    "SPRING_BASE_URL": "http://localhost:8080"
  }
}
```

- `MCP_TRANSPORT=stdio` → Claude Desktop용 stdio 모드로 서버 기동
- `SPRING_BASE_URL` → 로컬에서 실행 중인 Spring 서버에 연결
- `venv/bin/python` → 프로젝트 가상환경의 파이썬 직접 지정

### 동작 확인

등록 후 Claude Desktop에서:

```
"오늘 잘 팔리는 메뉴 3개 추천해줘"
```

→ Claude가 `tool_get_top_menus(limit=3)` 호출  
→ MCP 서버가 Spring `/api/menus/top` 호출  
→ 실제 DB 판매 데이터 기반 추천 반환

```
"비건 메뉴 중에 5000원 이하짜리 알려줘"
```

→ `tool_filter_menus(vegetarian_type="VEGAN", max_price=5000)` 호출  
→ Spring `/api/menus/filter` 파라미터 전달 → 실제 필터 결과 반환

---

## 5. 개발 및 배포 환경 분리

| 환경 | Spring | FastAPI | MCP 서버 |
|------|--------|---------|---------|
| **로컬 개발** | IntelliJ 직접 실행 | VS Code 직접 실행 | 터미널 직접 실행 |
| **배포** | Docker Compose | Docker Compose | 동일 이미지, 다른 커맨드 |

```yaml
# docker-compose.yml 개념
services:
  spring: ...
  fastapi:
    image: capstone-ai
    command: uvicorn app.main:app
  mcp:
    image: capstone-ai          # FastAPI와 동일 이미지
    command: python -m kiosk_mcp.mcp_server
    environment:
      MCP_TRANSPORT: sse        # 배포에서는 SSE
```

환경 분리는 `.env.local`(로컬) / `.env`(배포) 파일로만 관리한다.

---

## 6. 핵심 성과

### 기술 성과

- **이중 접근 구조 실현**: 동일한 MCP 서버를 키오스크(SSE) + Claude Desktop(stdio) 양쪽에서 동시 접근 가능
- **14개 MCP Tool 구현**: 메뉴 조회부터 주문·결제·세션 종료까지 전체 주문 플로우를 Tool로 커버
- **17개 필터 파라미터**: 칼로리, 가격, 알레르기, 채식 유형, 층, 식당명 등 복합 조건 필터링
- **LangGraph 에이전트 그래프**: 의도 분류 → 에이전트 분기 → 눈치 감지 → 추천 흐름 자동화
- **계층 분리**: Tool 로직 / MCP 진입점 / Adapter / Domain을 명확히 분리해 테스트·재사용 용이

### 시연 임팩트

- Claude Desktop에서 자연어 한 마디로 실제 DB 데이터 기반 주문 시연 가능
- 매장 키오스크(음성 주문) + 외부 Claude Desktop(채팅 주문) 동시 지원

### 기술 스택

`FastAPI` `FastMCP` `LangGraph` `OpenAI API` `Spring Boot` `PostgreSQL`  
`Docker` `AWS EC2` `GitHub Actions (CI/CD)`
