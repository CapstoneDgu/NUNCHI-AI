"""주문 API 라우터

요청 파싱과 응답 반환만 담당한다. 비즈니스 로직은 OrderService에 위임한다.
"""

from fastapi import APIRouter, Depends

from adapter.factory import get_order_service
from domain.api_response import ApiErrorResponse
from domain.order_request import (
    ChatOrderRequest,
    ChatOrderResponse,
    StartOrderRequest,
    StartOrderResponse,
)
from service.order_service import OrderService

router = APIRouter(prefix="/order", tags=["order"])


@router.post(
    "/start",
    response_model=StartOrderResponse,
    status_code=201,
    summary="주문 세션 시작",
    description=(
        "새 주문 세션을 생성하고 첫 안내 문구를 반환합니다.\n\n"
        "이 API는 대화형 주문의 시작점입니다.\n"
        "- `session_id`는 이후 `/api/order/chat` 호출에 반드시 사용합니다.\n"
        "- `mode`로 아바타형 주문 흐름과 일반 주문 흐름을 구분할 수 있습니다.\n"
        "- 현재 첫 인사 메시지는 고정 문구로 빠르게 반환됩니다."
    ),
    response_description="생성된 주문 세션 정보와 첫 안내 메시지입니다.",
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": "세션 생성 과정에서 애플리케이션 레벨 오류가 발생한 경우입니다.",
        },
        422: {
            "description": "요청 본문 형식이 잘못되었거나 필수 필드가 누락된 경우입니다.",
        },
        502: {
            "model": ApiErrorResponse,
            "description": "연동 중인 Spring 백엔드 호출에 실패한 경우입니다.",
        },
    },
)
async def start_order(
    body: StartOrderRequest,
    service: OrderService = Depends(get_order_service),
) -> StartOrderResponse:
    """주문 세션을 시작하고 첫 인사 메시지를 반환한다."""
    return await service.start(mode=body.mode, language=body.language, order_type=body.order_type)


@router.post(
    "/chat",
    response_model=ChatOrderResponse,
    summary="주문 대화 처리",
    description=(
        "사용자 발화를 AI 주문 엔진에 전달하고 자연어 응답을 반환합니다.\n\n"
        "처리 흐름은 다음과 같습니다.\n"
        "1. 사용자 메시지를 세션 대화 로그에 저장합니다.\n"
        "2. LangGraph 기반 주문 그래프가 현재 세션 상태를 복원합니다.\n"
        "3. 의도 분류, 추천, 주문, 결제 관련 흐름을 거쳐 응답을 생성합니다.\n"
        "4. 생성된 AI 응답을 다시 세션 로그에 저장합니다.\n\n"
        "`nunchi_signal`은 프론트엔드에서 감지한 망설임/침묵 신호를 넘길 때 사용합니다."
    ),
    response_description="세션 ID와 AI의 자연어 응답입니다.",
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": "주문 처리 흐름에서 비즈니스 오류가 발생한 경우입니다.",
        },
        422: {
            "description": "세션 ID, 텍스트, 모드 등 요청값 검증에 실패한 경우입니다.",
        },
        502: {
            "model": ApiErrorResponse,
            "description": "Spring 백엔드 연동 실패 또는 타임아웃이 발생한 경우입니다.",
        },
    },
)
async def chat_order(
    body: ChatOrderRequest,
    service: OrderService = Depends(get_order_service),
) -> ChatOrderResponse:
    """사용자 발화를 AI에게 전달하고 응답을 반환한다."""
    return await service.handle_chat(
        session_id=body.session_id,
        text=body.text,
        nunchi_signal=body.nunchi_signal,
        mode=body.mode,
    )
