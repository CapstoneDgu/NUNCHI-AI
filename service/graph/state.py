from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class KioskState(TypedDict):
    messages: Annotated[list, add_messages]  # 대화 히스토리 (자동 누적)
    session_id: int
    intent: str | None                       # 분류된 의도 (order/payment/recommend/hesitation)
    order_id: int | None                     # confirm_order 후 채워짐
    payment_id: int | None                   # request_payment 후 채워짐
    nunchi_signal: str | None                # 눈치 신호 종류 (silence/hesitation/repeat_browse)
    recommended_menu_ids: list[int]          # 추천된 메뉴 ID 목록
