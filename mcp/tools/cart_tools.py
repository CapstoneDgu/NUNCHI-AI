from adapter.spring_adapter import SpringAdapter
from domain.cart import CartResponse


async def add_cart_item(
    spring: SpringAdapter,
    session_id: int,
    menu_id: int,
    quantity: int,
    option_ids: list[int],
) -> CartResponse:
    """장바구니 담기 — POST /api/orders/cart/items

    Args:
        option_ids: 선택 옵션 없으면 빈 배열 [] 전달 (null 불가)

    Returns:
        CartResponse — items 안의 item_id(UUID)를 보관해야 수정/삭제 가능
    """
    body = {
        "sessionId": session_id,
        "menuId": menu_id,
        "quantity": quantity,
        "optionIds": option_ids,
    }
    data = await spring.post("/api/orders/cart/items", body)
    return CartResponse(**data)


async def get_cart(spring: SpringAdapter, session_id: int) -> CartResponse:
    """장바구니 전체 조회 — GET /api/orders/cart/{sessionId}"""
    data = await spring.get(f"/api/orders/cart/{session_id}")
    return CartResponse(**data)


async def update_cart_item(
    spring: SpringAdapter,
    session_id: int,
    item_id: str,
    quantity: int,
) -> dict:
    """장바구니 수량 수정 — PUT /api/orders/cart/{sessionId}/items/{itemId}"""
    return await spring.put(
        f"/api/orders/cart/{session_id}/items/{item_id}",
        {"quantity": quantity},
    )


async def remove_cart_item(spring: SpringAdapter, session_id: int, item_id: str) -> dict:
    """장바구니 아이템 삭제 — DELETE /api/orders/cart/{sessionId}/items/{itemId}"""
    return await spring.delete(f"/api/orders/cart/{session_id}/items/{item_id}")
