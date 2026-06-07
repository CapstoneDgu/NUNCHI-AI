from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from adapter.spring_adapter import SpringAdapter
from core.exceptions import SpringApiError
from domain.cart import CartResponse

# 동시 담기 요청으로 Spring 세션 락 획득에 실패하면 409(CART_LOCK_ACQUIRE_FAILED)를 반환한다.
# Spring 측 확인 결과 락 획득 실패 시 카트에는 아무 변경도 가해지지 않으므로(멱등) 안전하게 재시도 가능하다.
# 단, Spring 쪽 락 대기 자체가 최대 약 3초이므로 재시도는 1회·짧은 대기로 제한한다 (3초 응답 목표 고려).
_CART_LOCK_CONFLICT_STATUS = 409
_CART_LOCK_RETRY_DELAY_SEC = 0.3


async def add_cart_item(
    spring: SpringAdapter,
    session_id: int,
    menu_id: int,
    quantity: int,
    option_ids: list[int],
) -> CartResponse:
    """장바구니 담기 — POST /api/orders/cart/items"""
    body = {
        "sessionId": session_id,
        "menuId": menu_id,
        "quantity": quantity,
        "optionIds": option_ids,
    }
    try:
        data = await spring.post("/api/orders/cart/items", body)
    except SpringApiError as exc:
        if exc.status_code != _CART_LOCK_CONFLICT_STATUS:
            raise
        logging.warning(
            "[장바구니 담기 락 충돌] session_id=%s menu_id=%s — %.1f초 후 재시도",
            session_id, menu_id, _CART_LOCK_RETRY_DELAY_SEC,
        )
        await asyncio.sleep(_CART_LOCK_RETRY_DELAY_SEC)
        data = await spring.post("/api/orders/cart/items", body)

    try:
        return CartResponse.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[장바구니 담기 파싱 오류] data={data} | {exc}")
        raise SpringApiError("장바구니 담기 응답 스키마 불일치", status_code=502) from exc


async def get_cart(spring: SpringAdapter, session_id: int) -> CartResponse:
    """장바구니 전체 조회 — GET /api/orders/cart/{sessionId}"""
    data = await spring.get(f"/api/orders/cart/{session_id}")
    try:
        return CartResponse.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[장바구니 조회 파싱 오류] data={data} | {exc}")
        raise SpringApiError("장바구니 조회 응답 스키마 불일치", status_code=502) from exc


async def update_cart_item(
    spring: SpringAdapter,
    session_id: int,
    item_id: str,
    quantity: int,
) -> CartResponse:
    """장바구니 수량 수정 — PUT /api/orders/cart/{sessionId}/items/{itemId}"""
    data = await spring.put(
        f"/api/orders/cart/{session_id}/items/{item_id}",
        {"quantity": quantity},
    )
    try:
        return CartResponse.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[장바구니 수정 파싱 오류] data={data} | {exc}")
        raise SpringApiError("장바구니 수정 응답 스키마 불일치", status_code=502) from exc


async def remove_cart_item(spring: SpringAdapter, session_id: int, item_id: str) -> CartResponse:
    """장바구니 아이템 삭제 — DELETE /api/orders/cart/{sessionId}/items/{itemId}"""
    data = await spring.delete(f"/api/orders/cart/{session_id}/items/{item_id}")
    try:
        return CartResponse.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[장바구니 삭제 파싱 오류] data={data} | {exc}")
        raise SpringApiError("장바구니 삭제 응답 스키마 불일치", status_code=502) from exc


async def clear_cart(spring: SpringAdapter, session_id: int) -> dict:
    """장바구니 전체 초기화 — DELETE /api/orders/cart/{sessionId}"""
    return await spring.delete(f"/api/orders/cart/{session_id}")
