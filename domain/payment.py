from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PaymentMethod(str, Enum):
    ic_card = "IC_CARD"
    kakao_pay = "KAKAO_PAY"
    naver_pay = "NAVER_PAY"


class PaymentStatus(str, Enum):
    pending = "PENDING"
    success = "SUCCESS"
    fail = "FAIL"


class PaymentResult(BaseModel):
    """POST /api/payments 응답"""

    payment_id: int
    order_id: int
    method: PaymentMethod
    status: PaymentStatus
    created_at: datetime
