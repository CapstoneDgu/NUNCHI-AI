from __future__ import annotations

"""주문 API 요청/응답 Pydantic 모델"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.session import OrderType, SessionMode


class RecommendedMenu(BaseModel):
    """추천 메뉴 카드 단위 정보 — 프론트엔드 UI 렌더링용"""

    menu_id: int
    name: str
    price: int
    image_url: Optional[str] = None
    restaurant_name: Optional[str] = None
    floor: Optional[int] = None
    quantity_sold: Optional[int] = None


class MenuOptionItem(BaseModel):
    """옵션 단일 항목 — 프론트엔드 옵션 선택 UI용"""

    option_id: int
    name: str
    extra_price: int


class MenuOptionGroup(BaseModel):
    """옵션 그룹 — 하나의 선택 카테고리 (예: 온도, 사이즈)"""

    group_id: int
    group_name: str
    is_required: bool
    max_select: int
    options: list[MenuOptionItem]


class MenuOptionsResponse(BaseModel):
    """메뉴 옵션 선택 단계 구조화 응답 — 프론트엔드 옵션 선택 UI 렌더링용"""

    menu_id: int
    menu_name: str
    option_groups: list[MenuOptionGroup]


class StartOrderRequest(BaseModel):
    """POST /api/order/start 요청"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "AVATAR",
                "language": "ko",
                "order_type": "DINE_IN",
            }
        }
    )

    mode: SessionMode = Field(
        default=SessionMode.avatar,
        description=(
            "주문 세션 모드입니다. "
            "`AVATAR`는 아바타 기반 대화형 주문, "
            "`NORMAL`은 일반 키오스크 주문 흐름입니다."
        ),
        examples=["AVATAR"],
    )
    language: str = Field(
        default="ko",
        description="세션에서 사용할 언어 코드입니다. 현재 기본값은 한국어(`ko`)입니다.",
        examples=["ko"],
    )
    order_type: OrderType = Field(
        default=OrderType.dine_in,
        description="주문 유형입니다. `DINE_IN`은 매장 식사, `TAKEOUT`은 포장입니다.",
        examples=["DINE_IN"],
    )


class StartOrderResponse(BaseModel):
    """POST /api/order/start 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 101,
                "greeting": "안녕하세요! 무엇을 도와드릴까요? 메뉴를 추천해드릴까요, 아니면 직접 골라보시겠어요?",
            }
        }
    )

    session_id: int = Field(
        description="생성된 주문 세션 ID입니다. 이후 `/api/order/chat` 호출에 그대로 사용합니다.",
        examples=[101],
    )
    greeting: str = Field(
        description="세션 시작 직후 사용자에게 보여줄 첫 안내 메시지입니다.",
        examples=["안녕하세요! 무엇을 도와드릴까요? 메뉴를 추천해드릴까요, 아니면 직접 골라보시겠어요?"],
    )


class ChatOrderRequest(BaseModel):
    """POST /api/order/chat 요청"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 101,
                "text": "매운 거 말고 추천해줘",
                "nunchi_signal": "hesitation",
                "mode": "AVATAR",
            }
        }
    )

    session_id: int = Field(
        description="대화 대상 주문 세션 ID입니다. `/api/order/start`에서 받은 값을 사용합니다.",
        examples=[101],
    )
    text: str = Field(
        description="사용자 발화 또는 텍스트 입력 내용입니다. AI가 이 문장을 기반으로 주문 대화를 진행합니다.",
        examples=["아이스 아메리카노 하나랑 샌드위치 추천해줘"],
    )
    nunchi_signal: Optional[str] = Field(
        default=None,
        description=(
            "프론트엔드에서 감지한 눈치 신호입니다. "
            "예: `silence`, `hesitation`, `repeat_browse`. "
            "값이 없으면 일반 대화 흐름으로 처리됩니다."
        ),
        examples=["hesitation"],
    )
    mode: SessionMode = Field(
        default=SessionMode.avatar,
        description="현재 세션의 UI 모드입니다. `AVATAR` 또는 `NORMAL` 값을 사용합니다.",
        examples=["AVATAR"],
    )


class ChatOrderResponse(BaseModel):
    """POST /api/order/chat 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 101,
                "reply": "오늘 인기 메뉴를 추천해 드릴게요!",
                "current_step": "BROWSE",
                "recommendations": [
                    {
                        "menu_id": 13,
                        "name": "일식카레덮밥",
                        "price": 7000,
                        "image_url": "/images/menu/덮밥류/일식카레덮밥.png",
                        "restaurant_name": "쇼앤누들",
                        "floor": 1,
                        "quantity_sold": 50,
                    }
                ],
                "menu_options": None,
                "suggestions": ["다른 메뉴도 추천해줘", "장바구니 확인해줘", "결제할게"],
            }
        }
    )

    session_id: int = Field(
        description="응답이 생성된 주문 세션 ID입니다.",
        examples=[101],
    )
    reply: str = Field(
        description="AI 안내 멘트. TTS 또는 아바타 대사로 사용한다.",
        examples=["오늘 인기 메뉴를 추천해 드릴게요!"],
    )
    current_step: Optional[str] = Field(
        default=None,
        description="현재 주문 단계. BROWSE / SELECT / CONFIGURE / CHECKOUT 중 하나. 단계 UI 동기화에 사용한다.",
        examples=["BROWSE"],
    )
    recommendations: Optional[list[RecommendedMenu]] = Field(
        default=None,
        description="추천 메뉴 카드 목록. 추천 응답일 때만 포함되며 최대 3개. 프론트엔드 카드 렌더링에 사용한다.",
    )
    menu_options: Optional[MenuOptionsResponse] = Field(
        default=None,
        description="메뉴 옵션 선택 정보. CONFIGURE 단계에서 옵션이 있는 메뉴를 선택했을 때만 포함된다. 프론트엔드 옵션 선택 UI에 사용한다.",
    )
    suggestions: Optional[list[str]] = Field(
        default=None,
        description="다음 발화 추천 문구 최대 3개. 프론트엔드 퀵바 버튼 렌더링에 사용한다. 버튼 클릭 시 해당 문자열을 text로 그대로 전달한다.",
        examples=[["다른 메뉴도 추천해줘", "장바구니 확인해줘", "결제할게"]],
    )


class AddCartItemRequest(BaseModel):
    """POST /ai/api/order/cart/add 요청 — 메뉴담기 버튼 클릭 전용"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 101,
                "menu_id": 13,
                "quantity": 1,
                "option_ids": [],
            }
        }
    )

    session_id: int = Field(ge=1, description="주문 세션 ID", examples=[101])
    menu_id: int = Field(ge=1, description="담을 메뉴 ID", examples=[13])
    quantity: int = Field(default=1, ge=1, description="수량", examples=[1])
    option_ids: list[int] = Field(default_factory=list, description="선택한 옵션 ID 목록. 없으면 빈 배열.", examples=[[]])
