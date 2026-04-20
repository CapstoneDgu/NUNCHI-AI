# Spring DB 구조 변경 반영 계획

---

## 변경 범위 요약

Spring DB 구조 및 API 스펙이 업데이트됨에 따라 FastAPI 쪽 도메인 모델, MCP Tool, AI 추천 로직을 맞춰 수정한다.

---

## 1. `domain/menu.py` — 대폭 확장 (가장 큰 변경)

### 1-1. `Nutrition` 서브모델 신규 추가

Spring `MenuDetailResponse.nutrition` 응답 구조에 맞게 Pydantic 모델 추가.

```python
class Nutrition(BaseModel):
    calorie: int
    protein: float
    carbohydrate: float
    fat: float
    sodium: int
    sugar: float
    trans_fat: float = Field(alias="transFat")
    cholesterol: int
    dietary_fiber: float = Field(alias="dietaryFiber")
```

### 1-2. `OptionGroup`에 필드 추가

Spring DB에 `is_required`, `max_select` 컬럼이 있음. 현재 모델에 누락.

```python
class OptionGroup(BaseModel):
    group_id: int = Field(alias="groupId")
    group_name: str = Field(alias="groupName")
    is_required: bool = Field(alias="isRequired")
    max_select: int = Field(alias="maxSelect")
    options: list[Option] = Field(default_factory=list)
```

### 1-3. `MenuDetail`에 신규 필드 추가

AI 추천 시나리오에서 핵심적으로 사용하는 필드들.

```python
class MenuDetail(BaseModel):
    # 기존 필드 유지
    menu_id: int
    name: str
    price: int
    is_sold_out: bool
    image_url: Optional[str]
    option_groups: list[OptionGroup]
    # 신규 추가
    nutrition: Optional[Nutrition] = None
    allergies: list[str] = Field(default_factory=list)   # ["WHEAT", "SOY", ...]
    spicy_level: int = Field(default=0, alias="spicyLevel")
    temperature_type: str = Field(default="HOT", alias="temperatureType")   # HOT/COLD/BOTH
    vegetarian_type: str = Field(default="NONE", alias="vegetarianType")    # NONE/VEGETARIAN/VEGAN
    season_recommended: str = Field(default="ALL", alias="seasonRecommended")
    origin_info: Optional[str] = Field(default=None, alias="originInfo")
```

### 1-4. `MenuSummary`에 AI 필터링용 필드 추가

GET /api/menus 목록 응답에도 spicyLevel, temperatureType 등이 포함될 수 있음.
Spring 팀과 협의해 목록 응답에 추천 필터 필드를 포함하도록 요청한다.
추가될 필드:

```python
class MenuSummary(BaseModel):
    # 기존 유지
    menu_id: int
    name: str
    price: int
    is_sold_out: bool
    # 신규 추가 (Spring 목록 API 응답에 포함 요청)
    spicy_level: int = Field(default=0, alias="spicyLevel")
    temperature_type: str = Field(default="HOT", alias="temperatureType")
    vegetarian_type: str = Field(default="NONE", alias="vegetarianType")
    season_recommended: str = Field(default="ALL", alias="seasonRecommended")
    allergies: list[str] = Field(default_factory=list)
    calorie: Optional[int] = None   # 목록에서 칼로리만 바로 노출
```

> Spring 팀 요청 필요: GET /api/menus 목록 응답에 spicyLevel, temperatureType, vegetarianType, seasonRecommended, allergies, calorie 포함

---

## 2. `domain/order.py` — OrderStatus 수정

DB 스펙: `PENDING / COMPLETED / CANCELLED`
현재 코드: `CONFIRMED / COMPLETED / CANCELLED` → `CONFIRMED`가 잘못됨.

```python
class OrderStatus(str, Enum):
    pending   = "PENDING"     # CONFIRMED → PENDING 으로 교체
    completed = "COMPLETED"
    cancelled = "CANCELLED"
```

---

## 3. `domain/payment.py` — PaymentStatus 수정

DB 스펙: `PENDING / SUCCESS / FAILED`
현재 코드: `fail = "FAIL"` → `"FAILED"` 로 변경.

```python
class PaymentStatus(str, Enum):
    pending = "PENDING"
    success = "SUCCESS"
    failed  = "FAILED"   # FAIL → FAILED
```

---

## 4. `domain/session.py` — SessionStatus 수정

DB 스펙: `ACTIVE / COMPLETED / EXPIRED`
현재 코드: EXPIRED 누락.

```python
class SessionStatus(str, Enum):
    active    = "ACTIVE"
    completed = "COMPLETED"
    expired   = "EXPIRED"   # 신규 추가
```

---

## 5. `domain/conversation.py` — 필드명 확인

현재 코드는 `text` 필드 사용. DB 컬럼명은 `content`.
Spring API 응답 JSON 필드명이 `content`로 변경됐는지 Spring 팀에 확인 후 반영.

변경 예시 (Spring 확인 후):
```python
class ConversationMessage(BaseModel):
    message_id: int = Field(alias="messageId")
    session_id: int = Field(alias="sessionId")
    role: str
    content: str   # text → content 로 변경
    created_at: datetime = Field(alias="createdAt")
```

---

## 6. `service/graph/nodes/recommend_node.py` — 시스템 프롬프트 확장

새 필드(영양정보, 알레르기, 매운맛, 채식, 계절, 온도)를 활용하는 추천 지침 추가.

```python
_RECOMMEND_SYSTEM_PROMPT = """
너는 키오스크 메뉴 추천 AI 어시스턴트다.
실제 메뉴 데이터를 기반으로 사용자에게 메뉴를 추천해줘.

규칙:
- 반드시 Tool로 조회한 실제 메뉴 데이터를 기반으로 추천해라. 임의로 메뉴를 만들지 마라.
- 추천할 때는 메뉴명과 가격을 함께 알려줘라.
- 추천 이유를 간단히 덧붙여줘라. (예: "오늘 가장 많이 팔린 메뉴예요")
- 추천 후 "장바구니에 담아드릴까요?" 로 자연스럽게 주문으로 유도해라.
- 응답은 한국어로 친절하고 간결하게 해라.

사용자 발화 → 활용 필드 매핑:
- "칼로리 낮은 거" → nutrition.calorie 낮은 순 필터
- "매운 거 / 안 매운 거" → spicyLevel 높음/0 필터
- "알레르기 있어" → allergies 제외 필터
- "채식 / 비건" → vegetarianType = VEGETARIAN / VEGAN 필터
- "따뜻한 거 / 시원한 거" → temperatureType = HOT / COLD 필터
- "여름 메뉴 / 봄 메뉴" → seasonRecommended 필터
- "단백질 많은 거" → nutrition.protein 높은 순 필터
- "나트륨 낮은 거" → nutrition.sodium 낮은 순 필터
""".strip()
```

---

## 작업 순서

| 순서 | 파일 | 작업 내용 |
|------|------|----------|
| 1 | `domain/menu.py` | Nutrition 모델 추가, OptionGroup/MenuDetail/MenuSummary 확장 |
| 2 | `domain/order.py` | OrderStatus.confirmed → pending 수정 |
| 3 | `domain/payment.py` | PaymentStatus.fail → failed 수정 |
| 4 | `domain/session.py` | SessionStatus.expired 추가 |
| 5 | `domain/conversation.py` | Spring 확인 후 content 필드 반영 |
| 6 | `service/graph/nodes/recommend_node.py` | 시스템 프롬프트 확장 |

---

## Spring 팀 확인 필요 사항

- [ ] GET /api/menus 목록 응답에 spicyLevel, temperatureType, vegetarianType, seasonRecommended, allergies, calorie 포함 요청
- [ ] POST /api/sessions/{sessionId}/messages 응답에서 `text` 필드명이 `content`로 변경됐는지 확인

---

## 나중에 할 것 (미구현 사항)

### 1. 결제 성공/실패 처리 Tool 추가

Spring API는 있는데 FastAPI에 연결이 안 된 상태.

| 작업 | 파일 | 내용 |
|------|------|------|
| 함수 추가 | `mcp/tools/payment_tools.py` | `payment_success(spring, payment_id)` — PATCH /api/payments/{id}/success |
| 함수 추가 | `mcp/tools/payment_tools.py` | `payment_fail(spring, payment_id)` — PATCH /api/payments/{id}/fail |
| Tool 등록 | `mcp/server.py` | `make_payment_tools`에 `tool_payment_success`, `tool_payment_fail` 추가 |
| 프롬프트 수정 | `service/graph/nodes/payment_node.py` | 결제 순서에 success/fail 처리 단계 추가 |

현재 결제 흐름: `confirm_order` → `request_payment` → `complete_session`
수정 후 흐름: `confirm_order` → `request_payment` → 하드웨어 대기 → `payment_success/fail` → `complete_session`

### 2. 주문 취소 Tool 추가

"주문 취소해줘" 발화 처리 불가 상태.

| 작업 | 파일 | 내용 |
|------|------|------|
| 함수 추가 | `mcp/tools/order_tools.py` | `cancel_order(spring, order_id)` — PATCH /api/orders/{orderId}/cancel |
| Tool 등록 | `mcp/server.py` | `make_order_tools`에 `tool_cancel_order` 추가 |

### 3. MenuSummary에 단백질/나트륨/지방 필드 추가

Spring GET /api/menus 응답에 protein, sodium, fat 추가 요청 후 반영.

| 작업 | 파일 | 내용 |
|------|------|------|
| Spring 요청 | - | GET /api/menus 응답에 protein, sodium, fat 포함 요청 |
| 모델 수정 | `domain/menu.py` | MenuSummary에 protein, sodium, fat 필드 추가 |
