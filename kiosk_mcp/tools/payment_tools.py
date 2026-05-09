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


async def pay_by_barcode(
    spring: SpringAdapter,
    order_id: int,
    barcode_value: str,
) -> PaymentResult:
    """바코드 결제 요청 — POST /api/payments/barcode
    선행 조건: confirm_order로 주문 확정이 완료된 상태여야 한다.
    """
    body = {"orderId": order_id, "barcodeValue": barcode_value}
    data = await spring.post("/api/payments/barcode", body)
    try:
        return PaymentResult.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[바코드 결제 파싱 오류] data={data} | {exc}")
        raise SpringApiError("바코드 결제 응답 스키마 불일치", status_code=502) from exc


async def confirm_payment_success(
    spring: SpringAdapter,
    payment_id: int,
) -> PaymentResult:
    """결제 성공 처리 — PATCH /api/payments/{paymentId}/success
    IC_CARD / VEIN_AUTH 단말기 승인 완료 후 호출한다.
    PENDING 상태인 paymentId에만 동작하며, 이미 처리된 결제는 400 반환.
    """
    data = await spring.patch(f"/api/payments/{payment_id}/success")
    try:
        return PaymentResult.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[결제 성공 처리 파싱 오류] data={data} | {exc}")
        raise SpringApiError("결제 성공 응답 스키마 불일치", status_code=502) from exc


async def fail_payment(
    spring: SpringAdapter,
    payment_id: int,
) -> PaymentResult:
    """결제 실패 처리 — PATCH /api/payments/{paymentId}/fail
    단말기 승인 실패 또는 사용자 취소 시 호출한다.
    PENDING 상태인 paymentId에만 동작하며, 이미 처리된 결제는 400 반환.
    """
    data = await spring.patch(f"/api/payments/{payment_id}/fail")
    try:
        return PaymentResult.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[결제 실패 처리 파싱 오류] data={data} | {exc}")
        raise SpringApiError("결제 실패 응답 스키마 불일치", status_code=502) from exc
