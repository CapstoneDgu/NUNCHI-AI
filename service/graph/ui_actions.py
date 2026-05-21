"""UI 액션 명세 — LangGraph 응답에 담아 프론트로 보내는 단일 화면 명령.

프론트(NUNCHI) 의 common/ai-action.js 가 받아 dispatch 한다.
LLM 이 응답 JSON 의 "action" 키로 채우거나, 노드가 직접 state["action"] 에 세팅한다.

규칙:
- 단일 액션 (배열 X). 한 응답당 한 화면 명령.
- 알 수 없는 type 은 frontend 가 무시 (warn 만).
- 검증 실패 시 None 으로 폐기 (서비스 흐름 안 깨지게).
"""

from __future__ import annotations

import logging
from typing import Optional


# ─── 허용된 action.type 목록 ──────────────────────────────────────────────
NAVIGATE             = "navigate"
SELECT_FLOOR         = "select_floor"
SELECT_RESTAURANT    = "select_restaurant"
HIGHLIGHT_MENU       = "highlight_menu"
OPEN_MENU_DETAIL     = "open_menu_detail"
CLOSE_OVERLAY        = "close_overlay"
SELECT_PAYMENT_METHOD = "select_payment_method"

VALID_TYPES = {
    NAVIGATE,
    SELECT_FLOOR,
    SELECT_RESTAURANT,
    HIGHLIGHT_MENU,
    OPEN_MENU_DETAIL,
    CLOSE_OVERLAY,
    SELECT_PAYMENT_METHOD,
}

# 페이지 화이트리스트 (navigate)
VALID_PAGES = {"/menu", "/summary", "/payment", "/barcode", "/complete", "/fail", "/start"}

# 결제 수단 화이트리스트
VALID_PAYMENT_METHODS = {"ic", "vein", "barcode"}


# ─── 헬퍼 생성자 — 노드가 직접 호출해 state["action"] 채울 때 사용 ──
def navigate(page: str) -> dict:
    return {"type": NAVIGATE, "page": page}


def select_floor(floor: int) -> dict:
    return {"type": SELECT_FLOOR, "floor": int(floor)}


def select_restaurant(name: str) -> dict:
    return {"type": SELECT_RESTAURANT, "name": str(name)}


def highlight_menu(menu_id: int) -> dict:
    return {"type": HIGHLIGHT_MENU, "menu_id": int(menu_id)}


def open_menu_detail(menu_id: int) -> dict:
    return {"type": OPEN_MENU_DETAIL, "menu_id": int(menu_id)}


def close_overlay() -> dict:
    return {"type": CLOSE_OVERLAY}


def select_payment_method(method: str) -> dict:
    return {"type": SELECT_PAYMENT_METHOD, "method": str(method)}


# ─── 검증 — LLM 이 만든 dict 가 유효한지 확인 ─────────────────────────────
def validate(action: Optional[dict]) -> Optional[dict]:
    """LLM 이 생성한 action dict 를 검증한다.

    유효하지 않으면 None 반환 (응답에 포함 안 시킴).
    """
    if not isinstance(action, dict):
        return None

    action_type = action.get("type")
    if action_type not in VALID_TYPES:
        logging.warning(f"[ui_actions] 알 수 없는 action.type: {action_type}")
        return None

    # type 별 페이로드 검증
    if action_type == NAVIGATE:
        page = action.get("page")
        if page not in VALID_PAGES:
            logging.warning(f"[ui_actions] navigate page 불일치: {page}")
            return None
        return {"type": NAVIGATE, "page": page}

    if action_type == SELECT_FLOOR:
        try:
            floor = int(action.get("floor"))
        except (TypeError, ValueError):
            return None
        if floor not in (1, 2, 3):
            return None
        return {"type": SELECT_FLOOR, "floor": floor}

    if action_type == SELECT_RESTAURANT:
        name = action.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        return {"type": SELECT_RESTAURANT, "name": name.strip()}

    if action_type in (HIGHLIGHT_MENU, OPEN_MENU_DETAIL):
        try:
            menu_id = int(action.get("menu_id"))
        except (TypeError, ValueError):
            return None
        return {"type": action_type, "menu_id": menu_id}

    if action_type == CLOSE_OVERLAY:
        return {"type": CLOSE_OVERLAY}

    if action_type == SELECT_PAYMENT_METHOD:
        method = action.get("method")
        if method not in VALID_PAYMENT_METHODS:
            return None
        return {"type": SELECT_PAYMENT_METHOD, "method": method}

    return None
