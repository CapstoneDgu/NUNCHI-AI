from __future__ import annotations

import logging

from pydantic import ValidationError

from adapter.spring_adapter import SpringAdapter
from core.exceptions import SpringApiError
from domain.payment import PaymentMethod, PaymentResult


async def request_payment(
    spring: SpringAdapter,
    order_id: int,
    method: PaymentMethod,
) -> PaymentResult:
    """결제 요청 — POST /api/payments"""
    body = {"orderId": order_id, "method": method.value}
    data = await spring.post("/api/payments", body)
    try:
        return PaymentResult.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[결제 파싱 오류] data={data} | {exc}")
        raise SpringApiError("결제 응답 스키마 불일치", status_code=502) from exc
