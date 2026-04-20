from __future__ import annotations

import logging

from pydantic import ValidationError

from adapter.spring_adapter import SpringAdapter
from core.exceptions import SpringApiError
from domain.order import OrderResult


async def confirm_order(spring: SpringAdapter, session_id: int) -> OrderResult:
    """주문 확정 — POST /api/orders/confirm"""
    data = await spring.post("/api/orders/confirm", {"sessionId": session_id})
    try:
        return OrderResult.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[주문 확정 파싱 오류] data={data} | {exc}")
        raise SpringApiError("주문 확정 응답 스키마 불일치", status_code=502) from exc
