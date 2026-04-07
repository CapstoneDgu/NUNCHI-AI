from adapter.spring_adapter import SpringAdapter
from domain.payment import PaymentMethod, PaymentResult


async def request_payment(
    spring: SpringAdapter,
    order_id: int,
    method: PaymentMethod,
) -> PaymentResult:
    """결제 요청 — POST /api/payments

    PENDING 상태 결제를 생성한다.
    confirm_order로 orderId를 받은 뒤에만 호출 가능하다.

    Args:
        method: IC_CARD / KAKAO_PAY / NAVER_PAY

    Returns:
        PaymentResult — payment_id 포함 (상태 조회 시 필요)
    """
    body = {"orderId": order_id, "method": method.value}
    data = await spring.post("/api/payments", body)
    return PaymentResult(**data)
