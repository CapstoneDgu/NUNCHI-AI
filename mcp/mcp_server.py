"""FastMCP 서버 — nunchi-kiosk

독립 프로세스로 실행되며, LangGraph 에이전트와 Claude Desktop 등
외부 MCP 클라이언트에서 Tool을 직접 호출할 수 있다.

실행: python -m mcp.mcp_server
포트: 8090 (MCP_SERVER_PORT 환경변수로 변경 가능)
"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastmcp import FastMCP

from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from domain.payment import PaymentMethod
from mcp.tools.cart_tools import add_cart_item, get_cart, remove_cart_item, update_cart_item
from mcp.tools.menu_tools import filter_menus, get_categories, get_menu_detail, get_menus, get_top_menus
from mcp.tools.order_tools import confirm_order
from mcp.tools.payment_tools import request_payment
from mcp.tools.session_tools import complete_session, save_tool_log

_settings = get_settings()
_spring = SpringAdapter(_settings)

mcp_app = FastMCP("nunchi-kiosk")


# ─── 메뉴 / 카테고리 Tool ────────────────────────────────────────────────────

@mcp_app.tool()
async def tool_get_categories() -> str:
    """카테고리 목록을 조회한다."""
    return json.dumps(
        [c.model_dump() for c in await get_categories(_spring)],
        ensure_ascii=False,
    )


@mcp_app.tool()
async def tool_get_menus(category_id: Optional[int] = None) -> str:
    """메뉴 목록을 조회한다. category_id를 주면 해당 카테고리만 반환한다."""
    return json.dumps(
        [m.model_dump() for m in await get_menus(_spring, category_id)],
        ensure_ascii=False,
    )


@mcp_app.tool()
async def tool_get_top_menus(limit: int = 5) -> str:
    """오늘 판매량 기준 인기 메뉴 목록을 반환한다. limit으로 개수를 조절한다."""
    return json.dumps(
        [m.model_dump() for m in await get_top_menus(_spring, limit)],
        ensure_ascii=False,
    )


@mcp_app.tool()
async def tool_get_menu_detail(menu_id: int) -> str:
    """메뉴 상세 정보와 옵션을 조회한다. 장바구니 담기 전 반드시 호출해야 한다."""
    return json.dumps(
        (await get_menu_detail(_spring, menu_id)).model_dump(),
        ensure_ascii=False,
    )


@mcp_app.tool()
async def tool_filter_menus(
    max_calorie: Optional[int] = None,
    min_calorie: Optional[int] = None,
    min_protein: Optional[float] = None,
    max_sodium: Optional[float] = None,
    max_spicy_level: Optional[int] = None,
    min_spicy_level: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    temperature_type: Optional[str] = None,
    vegetarian_type: Optional[str] = None,
    season: Optional[str] = None,
    category_id: Optional[int] = None,
    exclude_allergies: Optional[str] = None,
    limit: Optional[int] = None,
) -> str:
    """조건에 맞는 메뉴를 필터링해 반환한다. 파라미터는 모두 Optional.

    - max_calorie / min_calorie: 칼로리 범위 (kcal)
    - min_protein: 단백질 하한 (g)
    - max_sodium: 나트륨 상한 (mg)
    - max_spicy_level / min_spicy_level: 매운맛 범위 0~5
    - min_price / max_price: 가격 범위 (원)
    - temperature_type: HOT | COLD
    - vegetarian_type: VEGAN | VEGETARIAN | NONE
    - season: SPRING | SUMMER | FALL | WINTER | ALL
    - category_id: 카테고리 ID
    - exclude_allergies: 제외할 알레르기 콤마 구분 영문 enum
      (MILK, EGG, WHEAT, SOY, PEANUT, WALNUT, PINE, SHRIMP, CRAB, SQUID, CLAM, BEEF, PORK, CHICKEN, PEACH, TOMATO, BUCKWHEAT)
    - limit: 반환할 최대 메뉴 수 (추천은 보통 3~5 권장)
    """
    kwargs = {k: v for k, v in {
        "max_calorie": max_calorie, "min_calorie": min_calorie,
        "min_protein": min_protein, "max_sodium": max_sodium,
        "max_spicy_level": max_spicy_level, "min_spicy_level": min_spicy_level,
        "min_price": min_price, "max_price": max_price,
        "temperature_type": temperature_type, "vegetarian_type": vegetarian_type,
        "season": season, "category_id": category_id,
        "exclude_allergies": exclude_allergies, "limit": limit,
    }.items() if v is not None}
    return json.dumps(
        [m.model_dump() for m in await filter_menus(_spring, **kwargs)],
        ensure_ascii=False,
    )


# ─── 장바구니 Tool ────────────────────────────────────────────────────────────

@mcp_app.tool()
async def tool_add_cart_item(session_id: int, menu_id: int, quantity: int, option_ids: list[int]) -> str:
    """장바구니에 메뉴를 담는다. 옵션 없으면 option_ids는 빈 배열로 전달한다."""
    result = json.dumps(
        (await add_cart_item(_spring, session_id, menu_id, quantity, option_ids)).model_dump(),
        ensure_ascii=False,
    )
    await save_tool_log(
        _spring, session_id, "add_to_cart",
        json.dumps({"menu_id": menu_id, "quantity": quantity, "option_ids": option_ids}),
        result,
    )
    return result


@mcp_app.tool()
async def tool_get_cart(session_id: int) -> str:
    """현재 장바구니 전체를 조회한다."""
    return json.dumps(
        (await get_cart(_spring, session_id)).model_dump(),
        ensure_ascii=False,
    )


@mcp_app.tool()
async def tool_update_cart_item(session_id: int, item_id: str, quantity: int) -> str:
    """장바구니 아이템 수량을 수정한다. item_id는 장바구니 조회 결과의 item_id(UUID)다."""
    result = json.dumps(
        (await update_cart_item(_spring, session_id, item_id, quantity)).model_dump(),
        ensure_ascii=False,
    )
    await save_tool_log(
        _spring, session_id, "update_cart_item",
        json.dumps({"item_id": item_id, "quantity": quantity}),
        result,
    )
    return result


@mcp_app.tool()
async def tool_remove_cart_item(session_id: int, item_id: str) -> str:
    """장바구니 아이템을 삭제한다. item_id는 장바구니 조회 결과의 item_id(UUID)다."""
    result = json.dumps(
        (await remove_cart_item(_spring, session_id, item_id)).model_dump(),
        ensure_ascii=False,
    )
    await save_tool_log(
        _spring, session_id, "remove_cart_item",
        json.dumps({"item_id": item_id}),
        result,
    )
    return result


# ─── 주문 / 결제 / 세션 Tool ──────────────────────────────────────────────────

@mcp_app.tool()
async def tool_confirm_order(session_id: int) -> str:
    """장바구니를 주문으로 확정한다. 결제 전 반드시 호출해야 한다."""
    result = json.dumps(
        (await confirm_order(_spring, session_id)).model_dump(),
        ensure_ascii=False,
    )
    await save_tool_log(_spring, session_id, "confirm_order", "{}", result)
    return result


@mcp_app.tool()
async def tool_request_payment(session_id: int, order_id: int, method: str) -> str:
    """결제를 요청한다. method는 IC_CARD / VEIN_AUTH 중 하나다."""
    try:
        payment_method = PaymentMethod(method)
    except ValueError:
        return f"지원하지 않는 결제 수단입니다: {method}. IC_CARD 또는 VEIN_AUTH 중 하나를 선택해주세요."
    result = json.dumps(
        (await request_payment(_spring, order_id, payment_method)).model_dump(),
        ensure_ascii=False,
    )
    await save_tool_log(
        _spring, session_id, "request_payment",
        json.dumps({"order_id": order_id, "method": method}),
        result,
    )
    return result


@mcp_app.tool()
async def tool_complete_session(session_id: int) -> str:
    """주문 세션을 종료한다. 결제 완료 후 호출한다."""
    result = json.dumps(await complete_session(_spring, session_id), ensure_ascii=False)
    await save_tool_log(_spring, session_id, "complete_session", "{}", result)
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_SERVER_PORT", "8090"))
    uvicorn.run(mcp_app.sse_app(), host="0.0.0.0", port=port)
