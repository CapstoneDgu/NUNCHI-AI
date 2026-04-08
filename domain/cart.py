from pydantic import BaseModel, ConfigDict, Field


class CartItemOption(BaseModel):
    """장바구니 아이템에 선택된 옵션"""

    model_config = ConfigDict(populate_by_name=True)

    option_id: int = Field(alias="optionId")
    option_name: str = Field(alias="optionName")
    extra_price: int = Field(alias="extraPrice")


class CartItem(BaseModel):
    """장바구니 개별 아이템"""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(alias="itemId")          # UUID — 수량 수정/삭제 시 필요
    menu_id: int = Field(alias="menuId")
    menu_name: str = Field(alias="menuName")
    unit_price: int = Field(alias="unitPrice")
    quantity: int
    item_total: int = Field(alias="itemTotal")
    options: list[CartItemOption] = Field(default_factory=list)


class CartResponse(BaseModel):
    """GET /api/orders/cart/{sessionId} 응답"""

    model_config = ConfigDict(populate_by_name=True)

    session_id: int = Field(alias="sessionId")
    items: list[CartItem] = Field(default_factory=list)
    total_amount: int = Field(alias="totalAmount")
