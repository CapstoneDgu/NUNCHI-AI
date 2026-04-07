from adapter.spring_adapter import SpringAdapter
from domain.order import OrderResult


async def confirm_order(spring: SpringAdapter, session_id: int) -> OrderResult:
    """주문 확정 — POST /api/orders/confirm

    Redis 장바구니를 DB 주문으로 저장한다.
    확정 후 Redis 장바구니는 자동 삭제된다.

    Returns:
        OrderResult — order_id를 보관해야 request_payment 호출 가능
    """
    data = await spring.post("/api/orders/confirm", {"sessionId": session_id})
    return OrderResult(**data)
