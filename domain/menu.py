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
    is_required: bool = Field(alias="isRequired")
    max_select: int = Field(alias="maxSelect")
    options: list[Option] = Field(default_factory=list)


class Nutrition(BaseModel):
    """메뉴 영양정보"""

    model_config = ConfigDict(populate_by_name=True)

    calorie: int
    protein: float
    carbohydrate: float
    fat: float
    sodium: int
    sugar: float
    trans_fat: float = Field(alias="transFat")
    cholesterol: int
    dietary_fiber: float = Field(alias="dietaryFiber")


class MenuSummary(BaseModel):
    """GET /api/menus 응답 항목 (목록용 + AI 추천 필터 필드 포함)"""

    model_config = ConfigDict(populate_by_name=True)

    menu_id: int = Field(alias="menuId")
    name: str
    price: int
    is_sold_out: bool = Field(alias="isSoldOut")
    spicy_level: int = Field(default=0, alias="spicyLevel")
    temperature_type: str = Field(default="HOT", alias="temperatureType")
    vegetarian_type: str = Field(default="NONE", alias="vegetarianType")
    season_recommended: str = Field(default="ALL", alias="seasonRecommended")
    allergies: list[str] = Field(default_factory=list)
    calorie: Optional[int] = None


class TopMenuSummary(BaseModel):
    """GET /api/menus/top 응답 항목 (오늘 판매량 포함)"""

    model_config = ConfigDict(populate_by_name=True)

    menu_id: int = Field(alias="menuId")
    name: str
    price: int
    quantity_sold: int = Field(alias="quantitySold")
    is_sold_out: bool = Field(alias="isSoldOut")


class MenuDetail(BaseModel):
    """GET /api/menus/{menuId} 응답 (상세 + 옵션 + 영양 + 알레르기)"""

    model_config = ConfigDict(populate_by_name=True)

    menu_id: int = Field(alias="menuId")
    name: str
    price: int
    is_sold_out: bool = Field(alias="isSoldOut")
    image_url: Optional[str] = Field(default=None, alias="imageUrl")
    option_groups: list[OptionGroup] = Field(default_factory=list, alias="optionGroups")
    nutrition: Optional[Nutrition] = None
    allergies: list[str] = Field(default_factory=list)
    spicy_level: int = Field(default=0, alias="spicyLevel")
    temperature_type: str = Field(default="HOT", alias="temperatureType")
    vegetarian_type: str = Field(default="NONE", alias="vegetarianType")
    season_recommended: str = Field(default="ALL", alias="seasonRecommended")
    origin_info: Optional[str] = Field(default=None, alias="originInfo")
