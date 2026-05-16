"""장바구니 직접 조작 API

프론트엔드의 "메뉴담기" 버튼 클릭 전용 엔드포인트.
LLM을 경유하지 않고 Spring 장바구니 API를 직접 호출한다.
"""

from fastapi import APIRouter, Depends

from adapter.factory import get_spring_adapter
from adapter.spring_adapter import SpringAdapter
from domain.api_response import ApiErrorResponse
from domain.cart import CartResponse
from domain.order_request import AddCartItemRequest
from kiosk_mcp.tools.cart_tools import add_cart_item, get_cart

router = APIRouter(prefix="/order/cart", tags=["cart"])


def _get_spring() -> SpringAdapter:
    return get_spring_adapter()


@router.post(
    "/add",
    response_model=CartResponse,
    status_code=200,
    summary="메뉴 장바구니 담기",
    description=(
        "추천 카드의 '메뉴담기' 버튼 클릭 시 호출하는 전용 엔드포인트입니다.\n\n"
        "LLM을 거치지 않고 Spring 장바구니 API를 직접 호출합니다. "
        "`menu_id`는 `/api/order/chat` 응답의 `recommendations[].menu_id` 값을 그대로 사용합니다.\n\n"
        "옵션이 없는 메뉴는 `option_ids`를 빈 배열로 전달합니다. "
        "옵션이 있는 메뉴는 chat을 통해 옵션 선택 UI를 거친 뒤 이 엔드포인트를 호출합니다."
    ),
    response_description="담기 후 갱신된 장바구니 전체 상태입니다.",
    responses={
        502: {
            "model": ApiErrorResponse,
            "description": "Spring 장바구니 API 호출에 실패한 경우입니다.",
        },
    },
)
async def add_to_cart(
    body: AddCartItemRequest,
    spring: SpringAdapter = Depends(_get_spring),
) -> CartResponse:
    """메뉴를 장바구니에 담고 갱신된 장바구니를 반환한다."""
    return await add_cart_item(
        spring=spring,
        session_id=body.session_id,
        menu_id=body.menu_id,
        quantity=body.quantity,
        option_ids=body.option_ids,
    )


@router.get(
    "/{session_id}",
    response_model=CartResponse,
    summary="장바구니 조회",
    description=(
        "현재 세션의 장바구니 전체 내용을 조회합니다.\n\n"
        "프론트엔드에서 장바구니 UI를 직접 렌더링할 때 사용합니다. "
        "AI 대화 없이 현재 담긴 항목·수량·금액을 즉시 확인할 수 있습니다."
    ),
    response_description="현재 장바구니 항목 목록과 총 금액입니다.",
    responses={
        502: {
            "model": ApiErrorResponse,
            "description": "Spring 장바구니 API 호출에 실패한 경우입니다.",
        },
    },
)
async def get_cart_items(
    session_id: int,
    spring: SpringAdapter = Depends(_get_spring),
) -> CartResponse:
    """세션의 장바구니 전체를 조회해 반환한다."""
    return await get_cart(spring=spring, session_id=session_id)
