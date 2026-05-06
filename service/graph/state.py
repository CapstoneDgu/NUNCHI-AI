from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class KioskState(TypedDict):
    messages: Annotated[list, add_messages]  # 대화 히스토리 (자동 누적)
    session_id: int
    mode: str                                # "AVATAR" 또는 "NORMAL"
    current_step: Optional[str]              # "BROWSE" / "SELECT" / "CONFIGURE" / "CHECKOUT" / None
    intent: Optional[str]                    # 분류된 의도 (order/payment/recommend/hesitation)
    order_id: Optional[int]                  # confirm_order 후 채워짐
    payment_id: Optional[int]               # request_payment 후 채워짐
    nunchi_signal: Optional[str]             # 눈치 신호 종류 (silence/hesitation/repeat_browse)
    recommended_menu_ids: list[int]          # 추천된 메뉴 ID 목록
