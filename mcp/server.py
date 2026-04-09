from __future__ import annotations

"""MCP Tool 레지스트리

LangGraph 노드에 주입할 LangChain Tool 목록을 용도별로 생성한다.
기존 mcp/tools/*.py 함수들은 spring: SpringAdapter를 직접 받는 구조여서,
팩토리 함수로 감싸 세션 컨텍스트를 클로저에 주입한 뒤 @tool로 변환한다.
"""

import json
from typing import Optional

from langchain_core.tools import tool

from adapter.spring_adapter import SpringAdapter
from mcp.tools.cart_tools import (
    add_cart_item,
    get_cart,
    remove_cart_item,
    update_cart_item,
)
from mcp.tools.menu_tools import get_categories, get_menu_detail, get_menus
from mcp.tools.order_tools import confirm_order
from mcp.tools.payment_tools import request_payment
from mcp.tools.session_tools import complete_session


def make_order_tools(spring: SpringAdapter, session_id: int) -> list:
    """주문/장바구니 관련 Tool 목록 생성"""

    @tool
    async def tool_get_categories() -> str:
        """카테고리 목록을 조회한다."""
        result = await get_categories(spring)
        return json.dumps([c.model_dump() for c in result], ensure_ascii=False)

    @tool
    async def tool_get_menus(category_id: Optional[int] = None) -> str:
        """메뉴 목록을 조회한다. category_id를 주면 해당 카테고리만 필터링한다."""
        result = await get_menus(spring, category_id)
        return json.dumps([m.model_dump() for m in result], ensure_ascii=False)

    @tool
    async def tool_get_menu_detail(menu_id: int) -> str:
        """메뉴 상세 정보와 옵션을 조회한다. 장바구니 담기 전 반드시 호출해야 한다."""
        result = await get_menu_detail(spring, menu_id)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_add_cart_item(menu_id: int, quantity: int, option_ids: list[int]) -> str:
        """장바구니에 메뉴를 담는다. 옵션 없으면 option_ids는 빈 배열로 전달한다."""
        result = await add_cart_item(spring, session_id, menu_id, quantity, option_ids)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_get_cart() -> str:
        """현재 장바구니 전체를 조회한다."""
        result = await get_cart(spring, session_id)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_update_cart_item(item_id: str, quantity: int) -> str:
        """장바구니 아이템 수량을 수정한다. item_id는 장바구니 조회 결과의 item_id(UUID)다."""
        result = await update_cart_item(spring, session_id, item_id, quantity)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_remove_cart_item(item_id: str) -> str:
        """장바구니 아이템을 삭제한다. item_id는 장바구니 조회 결과의 item_id(UUID)다."""
        result = await remove_cart_item(spring, session_id, item_id)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    return [
        tool_get_categories,
        tool_get_menus,
        tool_get_menu_detail,
        tool_add_cart_item,
        tool_get_cart,
        tool_update_cart_item,
        tool_remove_cart_item,
    ]


def make_payment_tools(spring: SpringAdapter, session_id: int) -> list:
    """결제 관련 Tool 목록 생성"""

    @tool
    async def tool_confirm_order() -> str:
        """장바구니를 주문으로 확정한다. 결제 전 반드시 호출해야 한다."""
        result = await confirm_order(spring, session_id)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_request_payment(order_id: int, method: str) -> str:
        """결제를 요청한다. method는 IC_CARD / VEIN_AUTH 중 하나다."""
        from domain.payment import PaymentMethod
        result = await request_payment(spring, order_id, PaymentMethod(method))
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def tool_complete_session() -> str:
        """주문 세션을 종료한다. 결제 완료 후 호출한다."""
        result = await complete_session(spring, session_id)
        return json.dumps(result, ensure_ascii=False)

    return [
        tool_confirm_order,
        tool_request_payment,
        tool_complete_session,
    ]


def make_recommend_tools(spring: SpringAdapter) -> list:
    """추천 관련 Tool 목록 생성"""

    @tool
    async def tool_get_top_menus() -> str:
        """오늘 가장 많이 팔린 인기 메뉴 목록을 반환한다."""
        # TODO: Spring 인기 메뉴 API 연동 (get_top_menus 구현 후 교체)
        result = await get_menus(spring)
        return json.dumps([m.model_dump() for m in result[:5]], ensure_ascii=False)

    @tool
    async def tool_get_menus_by_category(category_id: int) -> str:
        """특정 카테고리의 메뉴 목록을 반환한다."""
        result = await get_menus(spring, category_id)
        return json.dumps([m.model_dump() for m in result], ensure_ascii=False)

    @tool
    async def tool_get_menu_detail_recommend(menu_id: int) -> str:
        """추천할 메뉴의 상세 정보를 조회한다."""
        result = await get_menu_detail(spring, menu_id)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    return [
        tool_get_top_menus,
        tool_get_menus_by_category,
        tool_get_menu_detail_recommend,
    ]
