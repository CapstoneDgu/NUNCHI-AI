from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class KioskState(TypedDict):
    messages: Annotated[list, add_messages]  # 대화 히스토리 (자동 누적)
    session_id: int
    mode: str                                # "AVATAR" 또는 "NORMAL"
    current_step: Optional[str]              # "BROWSE" / "SELECT" / "CONFIGURE" / "CHECKOUT" / None
    intent: Optional[str]                    # 분류된 의도 (order/payment/recommend/hesitation/clarify/greeting)
    order_id: Optional[int]                  # confirm_order 후 채워짐
    payment_id: Optional[int]               # request_payment 후 채워짐
    nunchi_signal: Optional[str]             # 눈치 신호 종류 (silence/hesitation/repeat_browse)
    recommended_menu_ids: list[int]          # 추천된 메뉴 ID 목록
    request_id: Optional[str]
    # 프론트가 받아 화면을 직접 컨트롤하는 단일 액션. 노드가 필요 시 채움.
    # 예) {"type": "navigate", "page": "/summary"}
    #     {"type": "highlight_menu", "menu_id": 22}
    #     {"type": "select_floor", "floor": 1}
    #     {"type": "select_payment_method", "method": "barcode"}
    action: Optional[dict]
