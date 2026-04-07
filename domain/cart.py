from pydantic import BaseModel


class CartItemOption(BaseModel):
    """장바구니 아이템에 선택된 옵션"""

    option_id: int
    option_name: str
    extra_price: int


class CartItem(BaseModel):
    """장바구니 개별 아이템"""

    item_id: str          # UUID — 수량 수정/삭제 시 필요
    menu_id: int
    menu_name: str
    unit_price: int
    quantity: int
    item_total: int
    options: list[CartItemOption] = []


class CartResponse(BaseModel):
    """GET /api/orders/cart/{sessionId} 응답"""

    session_id: int
    items: list[CartItem]
    total_amount: int
