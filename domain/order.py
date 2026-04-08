from enum import Enum

from pydantic import BaseModel

from domain.cart import CartItem


class OrderStatus(str, Enum):
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class OrderResult(BaseModel):
    """POST /api/orders/confirm 응답"""

    order_id: int
    session_id: int
    total_amount: int
    order_status: OrderStatus
    items: list[CartItem]
