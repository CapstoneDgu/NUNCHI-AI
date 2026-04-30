# NUNCHI KIOSK — FastAPI 코딩 컨벤션

## 주석 규칙
- `# 정적 응답 매핑`, `# 세션 상태 정리`, `# 결제 실패 분기`처럼 **짧은 명사형**으로 작성
- 코드만 봐도 알 수 있는 내용은 주석으로 설명하지 않음
- 구현 의도나 예외 케이스가 드러나지 않는 부분에만 최소한으로 작성
- 긴 설명이 필요하면 주석보다 함수 분리와 이름 개선을 우선한다

---

## 기본 원칙
- 타입 힌트를 기본으로 작성한다
- 비즈니스 로직은 Router가 아니라 Service에 둔다
- 외부 API 연동은 Adapter 계층으로 분리한다
- 하드코딩보다 설정값, 상수, 모델을 우선 사용한다
- 한 함수는 한 가지 책임만 갖도록 유지한다
- 추측 구현보다 확정된 API 계약 기준 구현을 우선한다

---

## Pydantic 모델

### 공통 원칙
- 요청과 응답은 Pydantic 모델로 명확히 분리한다
- `dict`를 직접 주고받기보다 `BaseModel`을 우선 사용한다
- 필드명은 Python 표준에 맞게 `snake_case`를 사용한다
- 검증은 `Field`, `Annotated`, validator로 처리한다
- 중첩 구조가 있으면 하위 모델을 별도 클래스로 분리한다

### Request 모델
- 입력값 검증 규칙은 모델 내부에 둔다
- 단순 문자열도 길이, 범위, 필수 여부를 가능한 한 명시한다

### Response 모델
- 응답 스키마를 명시적으로 정의한다
- 외부 시스템 응답을 그대로 반환하지 말고, 필요한 형태로 변환해서 반환한다
- 변환 로직이 반복되면 `from_domain`, `from_result` 같은 클래스 메서드로 정리한다

```python
from pydantic import BaseModel, Field


class MenuQueryRequest(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=50)


class MenuResponse(BaseModel):
    menu_id: int
    name: str
    price: int

    @classmethod
    def from_result(cls, data: dict) -> "MenuResponse":
        return cls(
            menu_id=data["menu_id"],
            name=data["name"],
            price=data["price"],
        )
```

---

## Domain 모델
- `domain/`은 순수 데이터 모델 중심으로 유지한다
- 도메인 모델에는 외부 API 호출 로직을 넣지 않는다
- 메뉴, 주문, 결제, 세션처럼 핵심 개념을 타입으로 분리한다
- 상태 값은 문자열 남발보다 `Enum`을 우선 사용한다

```python
from enum import Enum
from pydantic import BaseModel


class OrderStatus(str, Enum):
    pending = "PENDING"
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class OrderResult(BaseModel):
    order_id: int
    status: OrderStatus
    total_price: int
```

---

## Router
- Router는 요청 입구 역할만 담당한다
- 입력 파싱, 응답 반환, 예외 변환까지만 처리한다
- 비즈니스 판단은 Service로 위임한다
- 엔드포인트별 `response_model`을 명시한다
- 파일 업로드, 쿼리 파라미터, 바디 모델을 혼합할 때도 시그니처를 명확히 유지한다

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/menus", tags=["menus"])


@router.get("", response_model=list[MenuResponse])
async def get_menus(category: str | None = None) -> list[MenuResponse]:
    return await menu_service.get_menus(category)
```

---

## Service
- 비즈니스 로직은 `service/`에 둔다
- 하나의 서비스는 하나의 도메인 책임에 집중한다
- Service는 Router보다 상위 개념이고, Adapter보다 도메인에 가깝다
- 외부 시스템 조합, 상태 판단, 추천 흐름, Tool 체이닝은 Service에서 처리한다
- Service 메서드는 입력과 반환 타입을 명확히 적는다

예시:
- `MenuService`: 메뉴 조회, 검색, 추천용 데이터 구성
- `AgentService`: LLM 호출 루프, Tool 실행
- `VoicePipeline`: STT → Agent → TTS 파이프라인 조합

---

## Adapter
- OpenAI, Spring, 센서, 외부 결제 같은 연동 코드는 `adapter/`에 둔다
- Adapter는 외부 계약에 맞추는 계층이다
- 외부 응답 형식 변화가 생기면 우선 Adapter에서 흡수한다
- 타임아웃, 인증 헤더, 예외 변환은 Adapter 책임으로 본다
- Service는 가능하면 Adapter의 인터페이스만 의존한다

예시:
- `OpenAIAdapter`
- `SpringAdapter`
- `VeinSensorAdapter`

---

## MCP Tool
- Tool 함수는 가능한 한 얇게 유지한다
- Tool은 입력 검증 후 Service 또는 Adapter 호출만 수행한다
- Tool 이름은 동사 중심으로 명확하게 작성한다
- Tool 스키마와 실제 함수 시그니처는 항상 일치해야 한다
- Tool 결과는 LLM이 해석하기 쉽게 단순하고 일관된 구조로 반환한다

예시:
- `get_top_menus`
- `get_menu_detail`
- `confirm_order`
- `process_card_payment`

---

## 예외 처리
- 공통 예외 클래스를 정의하고, 계층별로 필요한 예외를 분리한다
- 외부 API 오류를 그대로 노출하지 말고 의미 있는 예외로 변환한다
- FastAPI 전역 예외 핸들러에서 일관된 응답 구조로 반환한다
- 정상 흐름 제어를 예외에 의존하지 않는다

권장 예시:
- `KioskError`
- `SpringApiError`
- `SpringApiTimeoutError`
- `SttError`
- `TtsError`
- `AgentLoopLimitError`

---

## 응답 규칙
- 성공 응답은 가능한 한 `response_model` 기준으로 고정한다
- 에러 응답은 공통 구조를 유지한다
- 바이너리 응답, 스트리밍 응답은 예외적으로 명시한다
- 외부 시스템 원본 응답을 그대로 전달하지 않는다

권장 예시:
```python
class ErrorResponse(BaseModel):
    code: str
    message: str
```

---

## 비동기 규칙
- I/O 작업은 `async` / `await`를 사용한다
- 네트워크 호출, 파일 업로드 처리, WebSocket 송수신은 비동기 기준으로 작성한다
- CPU 바운드 작업이 길면 직접 Router에서 처리하지 않는다
- 블로킹 코드가 필요하면 영향 범위를 분리한다

---

## 설정 관리
- 환경변수는 `pydantic-settings`로 관리한다
- API Key, Base URL, Timeout, 모드 전환 값은 설정 클래스로 모은다
- 코드 내에 민감 정보나 URL을 하드코딩하지 않는다
- 개발용 stub 여부도 설정값으로 제어한다

---

## 네이밍

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일 | 소문자 + 언더스코어 | `spring_adapter.py` |
| Router 파일 | 도메인명 기준 | `voice.py`, `menus.py` |
| Service 클래스 | `도메인명Service` | `MenuService`, `AgentService` |
| Adapter 클래스 | `대상명Adapter` | `OpenAIAdapter`, `SpringAdapter` |
| 요청 모델 | `동작/대상 + Request` | `VoiceProcessRequest` |
| 응답 모델 | `대상 + Response` | `MenuResponse` |
| 결과 모델 | `대상 + Result` | `OrderResult` |
| 예외 클래스 | 의미 중심 + `Error` | `SpringApiError` |
| 상수 | 대문자 스네이크 | `SYSTEM_PROMPT` |
| Enum | 단수형 명사 | `OrderStatus` |

---

## Git 그라운드룰

커밋 메시지, 브랜치명, 이슈 제목, PR 제목은 아래 포맷을 따른다.

- 커밋: `[Feat] 회원가입 기능 구현`
- 브랜치: `feat/#1/sign-up`
- 이슈 제목: `[Feat] 회원가입 기능 구현`
- PR 제목: `[Feat] 회원가입 기능 구현`

### 규칙
- 브랜치는 `타입/이슈번호/기능명-kebab-case` 형식을 사용한다
- 커밋, 이슈, PR 제목의 타입 표기는 대괄호 형식을 사용한다
- 타입은 프로젝트 전반에서 일관되게 유지한다

### 타입 예시
- `[Feat]`
- `[Fix]`
- `[Refactor]`
- `[Docs]`
- `[Chore]`

### 적용 원칙
- 커밋 생성 시 항상 이 포맷을 사용한다
- 브랜치 생성 시 이슈 번호와 기능명을 함께 적는다
- 이슈 제목과 PR 제목도 같은 규칙으로 맞춘다

### 목적
- 팀 그라운드룰로 정해진 컨벤션을 일관되게 유지하기 위함

---

## 폴더 구조 원칙

```text
app/
  main.py
  api/
service/
adapter/
mcp/
  tools/
domain/
core/
```

- `app/`: FastAPI 앱, 라우터
- `service/`: 비즈니스 로직, 파이프라인
- `adapter/`: 외부 시스템 연동
- `mcp/`: MCP 서버, Tool 정의
- `domain/`: 도메인 모델
- `core/`: 설정, 예외, 공통 코드

---

## 금지 사항
- Router에서 직접 외부 API를 호출하지 않음
- Service에서 FastAPI Request 객체에 직접 의존하지 않음
- 의미 없는 `dict` 중첩 응답을 남발하지 않음
- 메뉴, 가격, 결제 상태를 임의 문자열로 하드코딩하지 않음
- 민감 정보, 결제 정보, 생체인증 값을 로그에 남기지 않음
