from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Category(BaseModel):
    """GET /api/menus/categories 응답 항목"""

    model_config = ConfigDict(populate_by_name=True)

    category_id: int = Field(alias="categoryId")
    name: str


class Option(BaseModel):
    """메뉴 옵션 단일 항목"""

    model_config = ConfigDict(populate_by_name=True)

    option_id: int = Field(alias="optionId")
    name: str
    extra_price: int = Field(alias="extraPrice")


class OptionGroup(BaseModel):
    """메뉴 옵션 그룹"""

    model_config = ConfigDict(populate_by_name=True)

    group_id: int = Field(alias="groupId")
    group_name: str = Field(alias="groupName")
    options: list[Option] = Field(default_factory=list)


class MenuSummary(BaseModel):
    """GET /api/menus 응답 항목 (목록용)"""

    model_config = ConfigDict(populate_by_name=True)

    menu_id: int = Field(alias="menuId")
    name: str
    price: int
    is_sold_out: bool = Field(alias="isSoldOut")


class MenuDetail(BaseModel):
    """GET /api/menus/{menuId} 응답 (상세 + 옵션)"""

    model_config = ConfigDict(populate_by_name=True)

    menu_id: int = Field(alias="menuId")
    name: str
    price: int
    is_sold_out: bool = Field(alias="isSoldOut")
    image_url: Optional[str] = Field(default=None, alias="imageUrl")
    option_groups: list[OptionGroup] = Field(default_factory=list, alias="optionGroups")
