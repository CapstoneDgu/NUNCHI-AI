from __future__ import annotations

"""주문 API 요청/응답 Pydantic 모델"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.session import SessionMode


class StartOrderRequest(BaseModel):
    """POST /api/order/start 요청"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "AVATAR",
                "language": "ko",
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
                "reply": "부담 없이 드시기 좋은 메뉴로는 아이스 아메리카노와 치킨 샌드위치를 추천드릴게요.",
            }
        }
    )

    session_id: int = Field(
        description="응답이 생성된 주문 세션 ID입니다.",
        examples=[101],
    )
    reply: str = Field(
        description="AI가 생성한 자연어 응답입니다. 프론트엔드에서는 이 값을 그대로 출력하거나 TTS 입력으로 사용할 수 있습니다.",
        examples=["부담 없이 드시기 좋은 메뉴로는 아이스 아메리카노와 치킨 샌드위치를 추천드릴게요."],
    )
