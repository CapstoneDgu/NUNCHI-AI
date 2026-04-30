from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from domain.cart import CartItem, CartItemOption


class OrderStatus(str, Enum):
    pending   = "PENDING"
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class OrderItem(BaseModel):
    """주문 확정 응답의 개별 아이템"""

    model_config = ConfigDict(populate_by_name=True)

    order_item_id: int   = Field(alias="orderItemId")
    menu_id:       int   = Field(alias="menuId")
    menu_name:     str   = Field(alias="menuName")
    unit_price:    int   = Field(alias="unitPrice")
    quantity:      int
    item_total:    int   = Field(alias="itemTotal")
    options:       list[CartItemOption] = Field(default_factory=list)


class OrderResult(BaseModel):
    """POST /api/orders/confirm 응답"""

    model_config = ConfigDict(populate_by_name=True)

    order_id:     int         = Field(alias="orderId")
    session_id:   int         = Field(alias="sessionId")
    total_amount: int         = Field(alias="totalAmount")
    order_status: OrderStatus = Field(alias="orderStatus")
    items:        list[OrderItem] = Field(default_factory=list)
