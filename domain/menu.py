from pydantic import BaseModel


class Category(BaseModel):
    """GET /api/menus/categories 응답 항목"""

    category_id: int
    name: str


class Option(BaseModel):
    """메뉴 옵션 단일 항목"""

    option_id: int
    name: str
    extra_price: int


class OptionGroup(BaseModel):
    """메뉴 옵션 그룹"""

    group_id: int
    group_name: str
    options: list[Option]


class MenuSummary(BaseModel):
    """GET /api/menus 응답 항목 (목록용)"""

    menu_id: int
    name: str
    price: int
    is_sold_out: bool


class MenuDetail(BaseModel):
    """GET /api/menus/{menuId} 응답 (상세 + 옵션)"""

    menu_id: int
    name: str
    price: int
    is_sold_out: bool
    image_url: str | None = None
    option_groups: list[OptionGroup] = []
