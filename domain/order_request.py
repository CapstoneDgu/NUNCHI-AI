"""주문 API 요청/응답 Pydantic 모델"""

from pydantic import BaseModel

from domain.session import SessionMode


class StartOrderRequest(BaseModel):
    """POST /api/order/start 요청"""
    mode: SessionMode = SessionMode.avatar
    language: str = "ko"


class StartOrderResponse(BaseModel):
    """POST /api/order/start 응답"""
    session_id: int
    greeting: str


class ChatOrderRequest(BaseModel):
    """POST /api/order/chat 요청"""
    session_id: int
    text: str
    nunchi_signal: str | None = None  # React에서 전달하는 눈치 신호 (선택)


class ChatOrderResponse(BaseModel):
    """POST /api/order/chat 응답"""
    session_id: int
    reply: str
