from __future__ import annotations

import logging
from typing import Optional

from pydantic import ValidationError

from adapter.spring_adapter import SpringAdapter
from core.exceptions import SpringApiError
from domain.menu import Category, FilterMenuResult, MenuDetail, MenuSummary, TopMenuSummary


async def get_categories(spring: SpringAdapter) -> list[Category]:
    """카테고리 목록 조회 — GET /api/menus/categories"""
    data = await spring.get("/api/menus/categories")
    try:
        return [Category.model_validate(item) for item in data]
    except ValidationError as exc:
        raise SpringApiError("카테고리 응답 스키마 불일치", status_code=502) from exc


async def get_menus(spring: SpringAdapter, category_id: Optional[int] = None) -> list[MenuSummary]:
    """메뉴 목록 조회 — GET /api/menus?categoryId={id}"""
    params = {"categoryId": category_id} if category_id is not None else None
    data = await spring.get("/api/menus", params=params)
    try:
        return [MenuSummary.model_validate(item) for item in data]
    except ValidationError as exc:
        raise SpringApiError("메뉴 목록 응답 스키마 불일치", status_code=502) from exc


async def get_top_menus(spring: SpringAdapter, limit: int = 5) -> list[TopMenuSummary]:
    """오늘 판매량 기준 인기 메뉴 조회 — GET /api/menus/top?limit={limit}"""
    data = await spring.get("/api/menus/top", params={"limit": limit})
    try:
        return [TopMenuSummary.model_validate(item) for item in data]
    except ValidationError as exc:
        raise SpringApiError("인기 메뉴 응답 스키마 불일치", status_code=502) from exc


async def filter_menus(
    spring: SpringAdapter,
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
    restaurant_name: Optional[str] = None,
    floor: Optional[int] = None,
) -> list[FilterMenuResult]:
    """메뉴 필터 조회 — GET /api/menus/filter

    - restaurant_name: 식당명 필터. 지정 시 해당 식당 메뉴 + 공용 메뉴(floor/restaurantName=null) 포함.
      예) restaurant_name="한식당" → 한식당 메뉴 + 음료·추가메뉴 포함
    - floor: 층 필터. 지정 시 해당 층 메뉴 + 공용 메뉴(floor/restaurantName=null) 포함.
      예) floor=2 → 2층 식당 메뉴 + 음료·추가메뉴 포함
    - 공용 메뉴(음료, 추가메뉴)는 floor=null, restaurantName=null 로 내려옴.
    """
    params: dict = {}
    if max_calorie is not None:
        params["maxCalorie"] = max_calorie
    if min_calorie is not None:
        params["minCalorie"] = min_calorie
    if min_protein is not None:
        params["minProtein"] = min_protein
    if max_sodium is not None:
        params["maxSodium"] = max_sodium
    if max_spicy_level is not None:
        params["maxSpicyLevel"] = max_spicy_level
    if min_spicy_level is not None:
        params["minSpicyLevel"] = min_spicy_level
    if min_price is not None:
        params["minPrice"] = min_price
    if max_price is not None:
        params["maxPrice"] = max_price
    if temperature_type is not None:
        params["temperatureType"] = temperature_type
    if vegetarian_type is not None:
        params["vegetarianType"] = vegetarian_type
    if season is not None:
        params["season"] = season
    if category_id is not None:
        params["categoryId"] = category_id
    if exclude_allergies is not None:
        params["excludeAllergies"] = exclude_allergies
    if limit is not None:
        params["limit"] = limit
    if restaurant_name is not None:
        params["restaurantName"] = restaurant_name
    if floor is not None:
        params["floor"] = floor

    data = await spring.get("/api/menus/filter", params=params if params else None)
    try:
        return [FilterMenuResult.model_validate(item) for item in data]
    except ValidationError as exc:
        raise SpringApiError("필터 메뉴 응답 스키마 불일치", status_code=502) from exc


async def get_menu_detail(spring: SpringAdapter, menu_id: int) -> MenuDetail:
    """메뉴 상세 + 옵션 조회 — GET /api/menus/{menuId}"""
    data = await spring.get(f"/api/menus/{menu_id}")
    try:
        return MenuDetail.model_validate(data)
    except ValidationError as exc:
        logging.error(f"[메뉴 상세 파싱 오류] data={data} | {exc}")
        raise SpringApiError("메뉴 상세 응답 스키마 불일치", status_code=502) from exc


async def search_menus(spring: SpringAdapter, name: str) -> list[MenuSummary]:
    """메뉴명 키워드 검색 — GET /api/menus/search?name={name}"""
    data = await spring.get("/api/menus/search", params={"name": name})
    try:
        return [MenuSummary.model_validate(item) for item in data]
    except ValidationError as exc:
        raise SpringApiError("메뉴 검색 응답 스키마 불일치", status_code=502) from exc
