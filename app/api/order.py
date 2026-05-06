"""주문 API 라우터

요청 파싱과 응답 반환만 담당한다. 비즈니스 로직은 OrderService에 위임한다.
"""

from fastapi import APIRouter, Depends

from adapter.factory import get_order_service
from domain.order_request import (
    ChatOrderRequest,
    ChatOrderResponse,
    StartOrderRequest,
    StartOrderResponse,
)
from service.order_service import OrderService

router = APIRouter(prefix="/api/order", tags=["order"])


@router.post("/start", response_model=StartOrderResponse, status_code=201)
async def start_order(
    body: StartOrderRequest,
    service: OrderService = Depends(get_order_service),
) -> StartOrderResponse:
    """주문 세션을 시작하고 첫 인사 메시지를 반환한다."""
    return await service.start(mode=body.mode, language=body.language)


@router.post("/chat", response_model=ChatOrderResponse)
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
