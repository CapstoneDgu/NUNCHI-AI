# 초기 세팅 진행 보고

---

## ✅ Step 1 완료 — core/ (공통 기반)

```text
core/
├── __init__.py
├── config.py       ← 환경변수 관리 (SPRING_BASE_URL, OPENAI_API_KEY 등)
└── exceptions.py   ← 공통 예외 정의 (KioskError, SpringApiError 등)
```

`core/`는 프로젝트 전역 공통 기반. 어느 계층에서도 참조하되, 다른 계층에는 의존하지 않는다.

- `config.py`: `.env`를 읽어 설정값 관리. Spring의 `@ConfigurationProperties`와 같은 역할
- `exceptions.py`: `KioskError` 베이스에서 `SpringApiError`, `OrderNotConfirmedError` 등 계층별 예외 분기

---

## ✅ Step 2 완료 — domain/ (데이터 모델)

```text
domain/
├── __init__.py
├── session.py      ← SessionMode, SessionStatus, SessionResult
├── menu.py         ← Category, MenuSummary, MenuDetail, OptionGroup, Option
├── cart.py         ← CartItem(item_id 포함), CartResponse
├── order.py        ← OrderStatus, OrderResult
└── payment.py      ← PaymentMethod, PaymentStatus, PaymentResult
```

Spring 응답 구조를 Python 타입으로 정의한 Pydantic 모델.
Java의 `record` + `@Valid`처럼 타입 선언만 하면 자동 검증/변환된다.

---

## ✅ Step 3 완료 — adapter/ (외부 연동 계층)

```text
adapter/
├── __init__.py
├── ports.py            ← SpringPort 추상 인터페이스 (Java interface와 같은 역할)
├── spring_adapter.py   ← HTTPX 기반 Spring HTTP 연동 구현체
├── openai_adapter.py   ← OpenAI 연동 골격 (transcribe, chat, speak)
└── factory.py          ← 싱글턴 Adapter 인스턴스 생성 함수
```

Spring의 `WebClient`와 같은 역할. 외부 API 변경이 생겨도 adapter 안에서만 수정한다.

- `spring_adapter.py`: Spring 공통 응답 `{ code, msg, data }` 파싱 + 예외 변환이 핵심
- `factory.py`: `get_spring_adapter()`로 FastAPI `Depends`에 주입해서 사용

---

## ✅ Step 4 완료 — mcp/ (MCP Tool 골격)

```text
mcp/
├── __init__.py
├── server.py               ← MCP 서버 등록 진입점 (골격)
└── tools/
    ├── __init__.py
    ├── session_tools.py    ← create_session, complete_session
    ├── menu_tools.py       ← get_categories, get_menus, get_menu_detail
    ├── cart_tools.py       ← add_cart_item, get_cart, update_cart_item, remove_cart_item
    ├── order_tools.py      ← confirm_order
    └── payment_tools.py    ← request_payment
```

`mcp/`는 LLM(AI)이 호출하는 함수들을 정의하는 곳.
Spring의 `@RestController`가 HTTP 요청을 받는 것처럼, MCP Tool은 LLM의 function call 요청을 받는 입구다.

각 Tool은 얇게 유지하고 실제 HTTP 호출은 `SpringAdapter`에 위임한다.

---

## ✅ Step 5, 6 완료 — service/, app/ (비즈니스 로직 + FastAPI 진입점)

```text
service/
├── __init__.py
├── agent_service.py    ← LLM + Tool 체이닝 실행 (골격)
└── voice_pipeline.py   ← STT → Agent → TTS 파이프라인 (골격)

app/
├── __init__.py
├── main.py             ← FastAPI 앱, /health, 예외 핸들러, 라우터 등록
└── api/
    ├── __init__.py
    └── voice.py        ← 음성 처리 API 라우터 (골격)
```

### service/ 의 역할

`service/`는 **비즈니스 로직이 들어가는 계층**이다.
Spring의 `@Service`와 같은 역할.

- `agent_service.py`: LLM에 메시지와 Tool 스키마를 전달하고, Tool 호출 루프를 관리
- `voice_pipeline.py`: STT → AgentService → TTS 흐름을 조합하는 파이프라인

### app/ 의 역할

`app/`은 **HTTP 요청을 받는 가장 바깥쪽 계층**이다.
Spring의 `@RestController` + `main()` 진입점과 같은 역할.

- `main.py`: FastAPI 앱 생성, 라우터 등록, 공통 예외 핸들러 등록
- `api/voice.py`: 음성 API 라우터. 입력 파싱과 응답 반환만 담당하고 로직은 Service에 위임

---

## 완성된 전체 폴더 구조

```text
capstone_ai/
├── app/
│   ├── __init__.py
│   ├── main.py             ← FastAPI 앱 진입점, /health
│   └── api/
│       ├── __init__.py
│       └── voice.py
├── service/
│   ├── __init__.py
│   ├── agent_service.py
│   └── voice_pipeline.py
├── adapter/
│   ├── __init__.py
│   ├── ports.py
│   ├── factory.py
│   ├── openai_adapter.py
│   └── spring_adapter.py
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
├── domain/
│   ├── __init__.py
│   ├── session.py
│   ├── menu.py
│   ├── cart.py
│   ├── order.py
│   └── payment.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── exceptions.py
├── .env.example
└── requirements.txt
```

---

## 서버 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에서 SPRING_BASE_URL, OPENAI_API_KEY 수정

# 3. 서버 실행
uvicorn app.main:app --reload

# 4. 확인
GET http://localhost:8000/health  →  {"status": "ok"}
```

---

## 다음 단계

1. `spring_adapter.py`로 실제 Spring API 호출 연결 및 테스트
2. MCP Tool 함수 내부 로직 구현 (session → menu → cart → order → payment)
3. `agent_service.py` LLM + Tool 체이닝 구현
4. `voice_pipeline.py` 음성 파이프라인 연결
