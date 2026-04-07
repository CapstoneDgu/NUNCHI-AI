from adapter.spring_adapter import SpringAdapter
from domain.menu import Category, MenuDetail, MenuSummary


async def get_categories(spring: SpringAdapter) -> list[Category]:
    """카테고리 목록 조회 — GET /api/menus/categories"""
    data = await spring.get("/api/menus/categories")
    return [Category(**item) for item in data]


async def get_menus(spring: SpringAdapter, category_id: int | None = None) -> list[MenuSummary]:
    """메뉴 목록 조회 — GET /api/menus?categoryId={id}

    Args:
        category_id: 카테고리 ID (없으면 전체 조회)
    """
    params = {"categoryId": category_id} if category_id is not None else None
    data = await spring.get("/api/menus", params=params)
    return [MenuSummary(**item) for item in data]


async def get_menu_detail(spring: SpringAdapter, menu_id: int) -> MenuDetail:
    """메뉴 상세 + 옵션 조회 — GET /api/menus/{menuId}

    장바구니 담기 전에 반드시 호출해서 optionGroups를 확인해야 한다.
    """
    data = await spring.get(f"/api/menus/{menu_id}")
    return MenuDetail(**data)
