# 초기 폴더 구조 세팅 계획

> 목표: Spring 연동을 바로 시작할 수 있는 FastAPI 최소 골격 구성

---

## 생성할 파일 전체 목록

```text
capstone_ai/
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── api/
│       ├── __init__.py
│       └── voice.py
│
├── service/
│   ├── __init__.py
│   ├── agent_service.py
│   └── voice_pipeline.py
│
├── adapter/
│   ├── __init__.py
│   ├── ports.py
│   ├── factory.py
│   ├── openai_adapter.py
│   └── spring_adapter.py
│
├── mcp/
│   ├── __init__.py
│   ├── server.py
│   └── tools/
│       ├── __init__.py
│       ├── session_tools.py
│       ├── menu_tools.py
│       ├── cart_tools.py
│       ├── order_tools.py
│       └── payment_tools.py
│
├── domain/
│   ├── __init__.py
│   ├── session.py
│   ├── menu.py
│   ├── cart.py
│   ├── order.py
│   └── payment.py
│
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── exceptions.py
│
├── .env.example
└── requirements.txt
```

---

## 작업 순서

### Step 1. core/ — 기반부터

**`core/config.py`**
- `pydantic-settings` 기반 `Settings` 클래스
- `SPRING_BASE_URL`, `SPRING_TIMEOUT`, `OPENAI_API_KEY` 포함
- `get_settings()` 함수로 싱글턴 반환

**`core/exceptions.py`**
- `KioskError` (베이스)
- `SpringApiError`, `SpringApiTimeoutError`
- `OrderNotConfirmedError`, `PaymentAlreadyExistsError`
- `SttError`, `TtsError`, `AgentLoopLimitError`

---

### Step 2. domain/ — Spring 응답 기준 Pydantic 모델

**`domain/session.py`**
- `SessionMode` Enum: `NORMAL`, `AVATAR`
- `SessionStatus` Enum: `ACTIVE`, `COMPLETED`
- `SessionResult` 모델: `session_id`, `mode`, `status`, `language`, `created_at`

**`domain/menu.py`**
- `Option` 모델: `option_id`, `name`, `extra_price`
- `OptionGroup` 모델: `group_id`, `group_name`, `options`
- `MenuSummary` 모델: `menu_id`, `name`, `price`, `is_sold_out`
- `MenuDetail` 모델: `MenuSummary` 확장 + `image_url`, `option_groups`
- `Category` 모델: `category_id`, `name`

**`domain/cart.py`**
- `CartItemOption` 모델: `option_id`, `option_name`, `extra_price`
- `CartItem` 모델: `item_id`, `menu_id`, `menu_name`, `unit_price`, `quantity`, `item_total`, `options`
- `CartResponse` 모델: `session_id`, `items`, `total_amount`

**`domain/order.py`**
- `OrderStatus` Enum: `COMPLETED`, `CANCELLED`
- `OrderResult` 모델: `order_id`, `session_id`, `total_amount`, `order_status`, `items`

**`domain/payment.py`**
- `PaymentMethod` Enum: `IC_CARD`, `KAKAO_PAY`, `NAVER_PAY`
- `PaymentStatus` Enum: `PENDING`, `SUCCESS`, `FAIL`
- `PaymentResult` 모델: `payment_id`, `order_id`, `method`, `status`, `created_at`

---

### Step 3. adapter/ — Spring 연동 핵심

**`adapter/ports.py`**
- `SpringPort` 추상 인터페이스 (ABC)
- `get`, `post`, `put`, `patch`, `delete` 추상 메서드 정의

**`adapter/spring_adapter.py`**
- `SpringAdapter(SpringPort)` 구현
- HTTPX `AsyncClient` 기반 비동기 HTTP 클라이언트
- `SPRING_BASE_URL`, `SPRING_TIMEOUT`은 `Settings`에서 주입
- Spring 공통 응답 `{ code, msg, data }` 파싱 내부 처리
- `code`가 비정상이면 `SpringApiError`로 변환
- 타임아웃은 `SpringApiTimeoutError`로 변환

**`adapter/openai_adapter.py`**
- 골격만 작성 (메서드 시그니처 + `pass`)
- `transcribe`, `chat`, `speak` 메서드

**`adapter/factory.py`**
- `get_spring_adapter()` 의존성 주입 함수
- FastAPI `Depends`와 연결되는 팩토리

---

### Step 4. mcp/tools/ — Tool 골격 (Spring Adapter 주입 구조만)

각 Tool 파일은 함수 시그니처와 docstring만 작성. 내부 로직은 다음 단계에서 채운다.

**`mcp/tools/session_tools.py`** — `create_session`, `complete_session`
**`mcp/tools/menu_tools.py`** — `get_categories`, `get_menus`, `get_menu_detail`
**`mcp/tools/cart_tools.py`** — `add_cart_item`, `get_cart`, `update_cart_item`, `remove_cart_item`
**`mcp/tools/order_tools.py`** — `confirm_order`
**`mcp/tools/payment_tools.py`** — `request_payment`

**`mcp/server.py`**
- MCP 서버 등록 진입점 골격만 작성

---

### Step 5. service/ — 골격만

**`service/agent_service.py`** — LLM Tool 실행 흐름 골격 (pass)
**`service/voice_pipeline.py`** — STT → Agent → TTS 파이프라인 골격 (pass)

---

### Step 6. app/ — FastAPI 앱

**`app/main.py`**
- `FastAPI()` 앱 생성
- `lifespan`으로 AsyncClient 수명 관리
- `/health` 엔드포인트
- `app/api/` 라우터 등록

**`app/api/voice.py`**
- 라우터 골격만 (`/api/voice` prefix)

---

### Step 7. 설정 파일

**`.env.example`**
```
SPRING_BASE_URL=http://localhost:8080
SPRING_TIMEOUT=5
OPENAI_API_KEY=sk-...
```

**`requirements.txt`**
```
fastapi
uvicorn[standard]
httpx
openai
pydantic
pydantic-settings
python-dotenv
```

---

## 완료 기준

- `uvicorn app.main:app --reload` 실행 시 서버 기동
- `GET /health` → `{"status": "ok"}` 응답
- 각 폴더에 `__init__.py` 존재, import 에러 없음
- `spring_adapter.py`가 실제 HTTPX 클라이언트를 들고 있음
- domain 모델이 Spring 응답 구조와 일치함

---

## 다음 단계 (이번 세팅 이후)

1. `spring_adapter.py` 실제 Spring API 호출 연결
2. MCP Tool 함수 내부 로직 구현
3. `agent_service.py` LLM + Tool 체이닝 구현
4. 음성 파이프라인 연결
