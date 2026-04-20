from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PaymentMethod(str, Enum):
    ic_card   = "IC_CARD"
    vein_auth = "VEIN_AUTH"


class PaymentStatus(str, Enum):
    pending = "PENDING"
    success = "SUCCESS"
    fail    = "FAIL"


class PaymentResult(BaseModel):
    """POST /api/payments 응답"""

    model_config = ConfigDict(populate_by_name=True)

    payment_id: int = Field(alias="paymentId")
    order_id:   int = Field(alias="orderId")
    method:     PaymentMethod
    status:     PaymentStatus
    created_at: datetime = Field(alias="createdAt")
