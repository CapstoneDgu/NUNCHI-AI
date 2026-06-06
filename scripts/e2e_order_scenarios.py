"""E2E 주문 시나리오 테스트 (서버 실행 중 필요)

실행:
  python3 scripts/e2e_order_scenarios.py

대상 서버:
  FastAPI  http://localhost:8000
  Spring   http://localhost:8080
"""

import asyncio
import json
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

AI_BASE   = "http://localhost:8000"
SPRING    = "http://localhost:8080"
TIMEOUT   = 30.0

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️ "

results: list[dict] = []

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

async def start_session(client: httpx.AsyncClient) -> int:
    r = await client.post(f"{AI_BASE}/ai/order/start", json={
        "mode": "NORMAL", "language": "ko", "order_type": "DINE_IN"
    })
    r.raise_for_status()
    return r.json()["session_id"]


async def chat(client: httpx.AsyncClient, session_id: int, text: str, mode: str = "NORMAL") -> dict:
    r = await client.post(f"{AI_BASE}/ai/order/chat", json={
        "session_id": session_id, "text": text, "mode": mode
    }, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


async def cart_add_direct(client: httpx.AsyncClient, session_id: int, menu_id: int,
                          quantity: int = 1, option_ids: list[int] | None = None) -> dict:
    """프론트 버튼 클릭 — FastAPI cart/add 엔드포인트 직접 호출."""
    r = await client.post(f"{AI_BASE}/ai/api/order/cart/add", json={
        "session_id": session_id, "menu_id": menu_id,
        "quantity": quantity, "option_ids": option_ids or []
    })
    r.raise_for_status()
    return r.json()


async def spring_cart(client: httpx.AsyncClient, session_id: int) -> dict:
    """Spring cart 상태를 직접 조회한다."""
    r = await client.get(f"{SPRING}/api/orders/cart/{session_id}")
    r.raise_for_status()
    return r.json()


def check(name: str, ok: bool, detail: str = "", data: dict | None = None) -> None:
    status = PASS if ok else FAIL
    results.append({"name": name, "ok": ok, "detail": detail})
    print(f"  {status} {name}")
    if detail:
        prefix = "       " if ok else "  >>>  "
        print(f"{prefix}{detail}")
    if not ok and data:
        print(f"         응답 dump: {json.dumps(data, ensure_ascii=False)[:300]}")


def reply_has_nested_json(reply: str) -> bool:
    """reply 텍스트 안에 JSON 구조가 중첩됐는지 감지한다."""
    if not reply:
        return False
    return (
        '"reply"' in reply
        or '```json' in reply
        or reply.strip().startswith("{")
    )

# ─── 시나리오 1: 이중 담기 재현 ──────────────────────────────────────────────
# 추천 받기 → 프론트가 cart/add 직접 호출(1개) → AI에 "X 장바구니에 담겼어" 알림
# → AI가 tool_add_cart_item 또 호출하면 Spring cart에 2개가 되는 버그

async def scenario_1_double_add(client: httpx.AsyncClient) -> None:
    print("\n" + "─" * 60)
    print("시나리오 1: 이중 담기 재현 (cart/add + 담겼어 알림)")
    print("─" * 60)

    sid = await start_session(client)
    print(f"  {INFO} session_id={sid}")

    # 1-a. 추천 받기
    rec_resp = await chat(client, sid, "인기 메뉴 추천해줘")
    recs = rec_resp.get("recommendations") or []
    print(f"  {INFO} 추천 메뉴 수: {len(recs)}")

    if not recs:
        check("1-a 추천 메뉴 수신", False, "recommendations 없음 — 시나리오 중단")
        return

    menu = recs[0]
    menu_id   = menu["menu_id"]
    menu_name = menu["name"]
    print(f"  {INFO} 선택 메뉴: {menu_name} (id={menu_id})")

    check("1-a 추천 메뉴 수신", True, f"menu={menu_name}")

    # 1-b. 프론트 버튼으로 cart/add 직접 호출
    await cart_add_direct(client, sid, menu_id, quantity=1)
    cart_before = await spring_cart(client, sid)
    cart_data_before = cart_before.get("data", cart_before)
    items_before = cart_data_before.get("items", [])
    qty_before = sum(i["quantity"] for i in items_before if i.get("menuId") == menu_id or i.get("menu_id") == menu_id)
    print(f"  {INFO} cart/add 직후 해당 메뉴 수량: {qty_before}")
    check("1-b cart/add 직후 수량=1", qty_before == 1, f"수량={qty_before}")

    # 1-c. AI에 담기 완료 알림 전송 (이게 기존 버그 유발 지점)
    notif_resp = await chat(client, sid, f"{menu_name} 장바구니에 담겼어")
    notif_reply = notif_resp.get("reply", "")
    notif_menu_opts = notif_resp.get("menu_options")
    print(f"  {INFO} AI 알림 응답: {notif_reply[:80]}")

    check("1-c 알림 응답 menu_options=null", notif_menu_opts is None,
          f"menu_options={notif_menu_opts}")
    check("1-c 알림 응답에 '담겼어요' 포함",
          "담겼어요" in notif_reply or "담겼" in notif_reply,
          f"reply={notif_reply[:80]}")

    # 1-d. Spring cart 재확인 — 수량이 1이어야 함 (2면 이중 담기 버그 재현)
    cart_after = await spring_cart(client, sid)
    cart_data_after = cart_after.get("data", cart_after)
    items_after = cart_data_after.get("items", [])
    qty_after = sum(i["quantity"] for i in items_after
                    if i.get("menuId") == menu_id or i.get("menu_id") == menu_id)
    print(f"  {INFO} 알림 전송 후 Spring cart 수량: {qty_after}")
    check("1-d Spring cart 최종 수량=1 (이중 담기 없음)", qty_after == 1,
          f"수량={qty_after} — 2이면 이중 담기 버그",
          notif_resp)

    # 1-e. reply 안에 JSON 중첩 여부
    nested = reply_has_nested_json(notif_reply)
    check("1-e reply에 JSON 중첩 없음", not nested,
          f"reply={notif_reply[:120]}" if nested else "")


# ─── 시나리오 2: reply 안에 reply/JSON 중첩 ───────────────────────────────────
# 옵션 선택 후 담기 완료 응답에서 reply 필드에 JSON이 그대로 노출되는지 검증

async def scenario_2_reply_nesting(client: httpx.AsyncClient) -> None:
    print("\n" + "─" * 60)
    print("시나리오 2: reply 안에 reply/JSON 중첩 검증")
    print("─" * 60)

    sid = await start_session(client)
    print(f"  {INFO} session_id={sid}")

    # 정확한 메뉴명으로 직접 호출해 menu_options 유도
    search_terms = ["숯불삼겹솥밥 담아줘", "데리야끼치킨솥밥 담아줘", "낙지삼겹솥밥 담아줘"]
    resp = None
    used_term = ""
    for term in search_terms:
        resp = await chat(client, sid, term)
        if resp.get("menu_options"):
            used_term = term
            break

    print(f"  {INFO} 검색어: '{used_term}', menu_options: {resp.get('menu_options') is not None if resp else False}")

    if resp and resp.get("menu_options"):
        opts = resp["menu_options"]
        option_groups = opts.get("option_groups", [])
        print(f"  {INFO} 옵션 그룹 수: {len(option_groups)}")
        check("2-a 옵션 있는 메뉴 발견", True, f"menu={opts.get('menu_name')}")

        # 첫 번째 옵션 선택
        if option_groups and option_groups[0].get("options"):
            first_opt = option_groups[0]["options"][0]
            opt_name  = first_opt.get("name", "기본")
            print(f"  {INFO} 옵션 선택: {opt_name}")
            add_resp = await chat(client, sid, f"{opt_name}로 할게")

            add_reply = add_resp.get("reply", "")
            add_menu_opts = add_resp.get("menu_options")

            # reply 중첩 검사
            nested = reply_has_nested_json(add_reply)
            check("2-b 옵션 선택 후 reply에 JSON 중첩 없음", not nested,
                  f"reply={add_reply[:200]}" if nested else f"reply={add_reply[:80]}")

            # 담겼어요 응답인지 or 추가 옵션 선택 요청인지
            if "담겼어요" in add_reply or "담겼" in add_reply:
                check("2-c 담기 완료 응답 형식 정상", True, add_reply[:80])
                # 담기 완료인데 menu_options가 전체 옵션 목록이면 버그
                if add_menu_opts and len(add_menu_opts.get("option_groups", [])) > 0:
                    all_opts = add_menu_opts["option_groups"][0].get("options", [])
                    is_filtered = len(all_opts) == 1
                    check("2-d 담기 완료 시 menu_options는 선택된 옵션만", is_filtered,
                          f"옵션 수={len(all_opts)} (1이어야 함)", add_resp)
            else:
                print(f"  {INFO} 추가 옵션 선택 필요: {add_reply[:80]}")
                check("2-c 추가 옵션 응답 (menu_options 있음)", add_menu_opts is not None,
                      f"menu_options={add_menu_opts}")
        else:
            check("2-a 옵션 그룹 파싱", False, "option_groups 비어있음")
    else:
        reply_txt = resp.get("reply", "") if resp else ""
        nested = reply_has_nested_json(reply_txt)
        check("2-a 옵션 메뉴 검색 (메뉴 없음 케이스)", True,
              f"옵션 없는 응답 — reply 중첩: {nested}, reply={reply_txt[:80]}")
        check("2-b reply에 JSON 중첩 없음", not nested,
              f"reply={reply_txt[:200]}" if nested else "")


# ─── 시나리오 3: 이전 턴 옵션 오염 ───────────────────────────────────────────
# 메뉴A 옵션 대화 중단 → 다른 대화 → 다시 메뉴B 담기
# 이때 메뉴A의 옵션이 menu_options에 나오는지 검증

async def scenario_3_stale_option_pollution(client: httpx.AsyncClient) -> None:
    print("\n" + "─" * 60)
    print("시나리오 3: 이전 턴 옵션 오염 검증")
    print("─" * 60)

    sid = await start_session(client)
    print(f"  {INFO} session_id={sid}")

    # 3-a. 옵션 있는 메뉴 A를 먼저 탐색 (담지 않고 대화만) — 정확한 메뉴명 사용
    search_terms_a = ["숯불삼겹솥밥 담아줘", "데리야끼치킨솥밥 담아줘", "낙지삼겹솥밥 담아줘"]
    resp_a = None
    menu_a_name = ""
    for term in search_terms_a:
        resp_a = await chat(client, sid, term)
        if resp_a.get("menu_options"):
            menu_a_name = resp_a["menu_options"].get("menu_name", term)
            break

    if not (resp_a and resp_a.get("menu_options")):
        check("3-a 메뉴A 옵션 대화", False, "옵션 있는 메뉴를 찾지 못함 — 시나리오 스킵")
        return

    menu_a_opts = resp_a["menu_options"]
    check("3-a 메뉴A 옵션 표시", True, f"menu_a={menu_a_name}, 옵션그룹={len(menu_a_opts.get('option_groups',[]))}")
    print(f"  {INFO} 메뉴A '{menu_a_name}' 옵션 대화 중단 — 다른 대화로 전환")

    # 3-b. 옵션 선택하지 않고 완전히 다른 대화 (추천 요청)
    pivot_resp = await chat(client, sid, "인기 메뉴 추천해줘")
    pivot_menu_opts = pivot_resp.get("menu_options")
    check("3-b 추천 요청 시 메뉴A 옵션 미노출",
          pivot_menu_opts is None,
          f"menu_options={pivot_menu_opts.get('menu_name') if pivot_menu_opts else None}")

    # 3-c. 옵션 없는 메뉴 B 담기
    resp_b = await chat(client, sid, "콜라 담아줘")
    b_reply = resp_b.get("reply", "")
    b_menu_opts = resp_b.get("menu_options")
    print(f"  {INFO} 콜라 담기 응답: {b_reply[:80]}")

    if b_menu_opts:
        # 메뉴A의 옵션이 오염됐는지 확인
        polluted = b_menu_opts.get("menu_name") == menu_a_name
        check("3-c 콜라 담기 시 메뉴A 옵션 미오염",
              not polluted,
              f"오염됨! menu_options.menu_name={b_menu_opts.get('menu_name')} (메뉴A={menu_a_name})")
    else:
        check("3-c 콜라 담기 후 menu_options=null (오염 없음)", True)

    # 3-d. 메뉴B가 정상 담겼는지 Spring 확인
    cart_data = await spring_cart(client, sid)
    items = (cart_data.get("data") or cart_data).get("items", [])
    has_cola = any("콜라" in (i.get("menuName") or i.get("menu_name", "")) for i in items)
    has_menu_a = any(menu_a_name in (i.get("menuName") or i.get("menu_name", "")) for i in items)
    check("3-d 장바구니에 콜라만 있고 메뉴A 미담김",
          has_cola and not has_menu_a,
          f"콜라={has_cola}, 메뉴A={has_menu_a}, items={[i.get('menuName') or i.get('menu_name') for i in items]}")


# ─── 시나리오 4: 복수 메뉴 + 혼합 옵션 ───────────────────────────────────────
# "콜라랑 솥밥 주세요" — 옵션없는 메뉴 + 옵션있는 메뉴 동시 요청

async def scenario_4_multi_menu_mixed_options(client: httpx.AsyncClient) -> None:
    print("\n" + "─" * 60)
    print("시나리오 4: 복수 메뉴 + 혼합 옵션 (옵션없는 + 옵션있는)")
    print("─" * 60)

    sid = await start_session(client)
    print(f"  {INFO} session_id={sid}")

    # "콜라랑 솥밥" 동시 요청 — 콜라는 옵션 없음, 솥밥은 옵션 있음
    resp = await chat(client, sid, "콜라랑 삼겹솥밥 주세요")
    reply    = resp.get("reply", "")
    menu_opts = resp.get("menu_options")
    recs      = resp.get("recommendations")

    print(f"  {INFO} reply: {reply[:100]}")
    print(f"  {INFO} menu_options: {menu_opts.get('menu_name') if menu_opts else None}")

    # 이 턴에서 가능한 올바른 상태:
    # A) 콜라 담기 완료 + 솥밥 옵션 표시 → menu_options 있음
    # B) 두 메뉴 모두 옵션 없으면 둘 다 담김
    # C) 솥밥 메뉴 없음 → 되묻기

    check("4-a reply에 JSON 중첩 없음", not reply_has_nested_json(reply),
          f"reply={reply[:200]}" if reply_has_nested_json(reply) else "")

    cart_data = await spring_cart(client, sid)
    items = (cart_data.get("data") or cart_data).get("items", [])
    item_names = [i.get("menuName") or i.get("menu_name", "") for i in items]
    print(f"  {INFO} Spring cart 현황: {item_names}")

    if menu_opts:
        opt_menu_name = menu_opts.get("menu_name", "")
        check("4-b 옵션있는 메뉴 옵션 표시됨", bool(opt_menu_name),
              f"menu_name={opt_menu_name}")
        # 콜라는 이미 담겨있어야 함
        has_cola = any("콜라" in n for n in item_names)
        check("4-c 옵션없는 메뉴(콜라)는 이미 담김", has_cola,
              f"cart items={item_names}")

        # 옵션 선택 — 모든 그룹을 순서대로 선택 (최대 3 그룹)
        if menu_opts.get("option_groups"):
            cur_resp = {"menu_options": menu_opts, "reply": ""}
            for round_i in range(3):
                cur_opts = cur_resp.get("menu_options")
                if not cur_opts or not cur_opts.get("option_groups"):
                    break
                first_opt = cur_opts["option_groups"][0]["options"][0]
                opt_name  = first_opt.get("name", "기본")
                # "없음" 옵션은 "X으로 할게" 대신 "X 없이 해줘" 표현 사용 (intent 오분류 방지)
                if opt_name == "없음":
                    utterance = f"{cur_opts['option_groups'][0]['group_name']} 없이 해줘"
                else:
                    utterance = f"{opt_name}로 할게"
                print(f"  {INFO} 옵션 선택 round {round_i+1}: '{utterance}'")
                cur_resp = await chat(client, sid, utterance)
                cur_reply = cur_resp.get("reply", "")
                check(f"4-d round{round_i+1} reply 정상", not reply_has_nested_json(cur_reply),
                      f"reply={cur_reply[:200]}" if reply_has_nested_json(cur_reply) else f"reply={cur_reply[:80]}")
                if "담겼어요" in cur_reply or cur_resp.get("menu_options") is None:
                    break  # 모든 옵션 선택 완료 → 담기 완료

            cart2 = await spring_cart(client, sid)
            items2 = (cart2.get("data") or cart2).get("items", [])
            names2 = [i.get("menuName") or i.get("menu_name", "") for i in items2]
            print(f"  {INFO} 전체 옵션 선택 후 cart: {names2}")
            check("4-e 옵션 선택 후 두 메뉴 모두 담김", len(items2) >= 2,
                  f"items={names2}")
    else:
        # 둘 다 옵션 없거나 메뉴 미발견
        check("4-b 두 메뉴 모두 처리됨 (옵션 없는 케이스)",
              "담겼어요" in reply or len(items) > 0,
              f"reply={reply[:80]}, cart={item_names}")


# ─── 시나리오 5: 장바구니 초기화 + 재주문 + step 전이 ────────────────────────

async def scenario_5_cart_reset_and_reorder(client: httpx.AsyncClient) -> None:
    print("\n" + "─" * 60)
    print("시나리오 5: 장바구니 초기화 + 재주문 + step 전이")
    print("─" * 60)

    sid = await start_session(client)
    print(f"  {INFO} session_id={sid}")

    # 5-a. 메뉴 하나 담기
    resp_add = await chat(client, sid, "콜라 담아줘")
    add_reply = resp_add.get("reply", "")
    print(f"  {INFO} 콜라 담기: {add_reply[:60]}")

    cart0 = await spring_cart(client, sid)
    items0 = (cart0.get("data") or cart0).get("items", [])
    check("5-a 콜라 담기 후 cart 1개 이상", len(items0) >= 1,
          f"items={[i.get('menuName') or i.get('menu_name') for i in items0]}")

    # 5-b. 처음부터 다시 (장바구니 초기화)
    resp_reset = await chat(client, sid, "처음부터 다시 할게요")
    reset_reply = resp_reset.get("reply", "")
    print(f"  {INFO} 초기화 응답: {reset_reply[:80]}")
    check("5-b 초기화 응답 형식 정상", not reply_has_nested_json(reset_reply),
          f"reply={reset_reply[:200]}" if reply_has_nested_json(reset_reply) else "")

    cart1 = await spring_cart(client, sid)
    items1 = (cart1.get("data") or cart1).get("items", [])
    check("5-c Spring cart 초기화 확인", len(items1) == 0,
          f"남은 items={[i.get('menuName') or i.get('menu_name') for i in items1]}")

    # 5-c. 재주문
    resp_re = await chat(client, sid, "인기 메뉴 추천해줘")
    re_recs = resp_re.get("recommendations") or []
    re_reply = resp_re.get("reply", "")
    check("5-d 재주문 추천 응답 정상", not reply_has_nested_json(re_reply),
          f"reply={re_reply[:200]}" if reply_has_nested_json(re_reply) else f"reply={re_reply[:80]}")
    print(f"  {INFO} 재추천 수: {len(re_recs)}, reply: {re_reply[:60]}")

    # 5-d. current_step 확인
    step = resp_re.get("current_step")
    print(f"  {INFO} current_step: {step}")
    check("5-e current_step 유효값", step in ("BROWSE", "SELECT", "CONFIGURE", "CHECKOUT", None),
          f"step={step}")

    # 5-e. 결제 의도 발화 후 step=CHECKOUT
    resp_pay = await chat(client, sid, "결제할게요")
    pay_reply = resp_pay.get("reply", "")
    pay_action = resp_pay.get("action")
    pay_step   = resp_pay.get("current_step")
    print(f"  {INFO} 결제 응답: {pay_reply[:60]}, action={pay_action}, step={pay_step}")
    check("5-f 결제 의도 → navigate action", pay_action is not None and pay_action.get("type") == "navigate",
          f"action={pay_action}")
    check("5-g reply에 JSON 중첩 없음", not reply_has_nested_json(pay_reply),
          f"reply={pay_reply[:200]}" if reply_has_nested_json(pay_reply) else "")


# ─── 메인 ────────────────────────────────────────────────────────────────────

def print_summary() -> None:
    total  = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    print(f"\n{'═'*60}")
    print(f"  최종 결과: PASS {passed} / FAIL {failed} / TOTAL {total}")
    print(f"{'═'*60}")
    if failed:
        print("\n실패 항목:")
        for r in results:
            if not r["ok"]:
                print(f"  {FAIL} {r['name']}")
                if r["detail"]:
                    print(f"       {r['detail'][:200]}")


async def main() -> None:
    print("═" * 60)
    print("  E2E 주문 시나리오 테스트")
    print("═" * 60)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 서버 헬스체크
        try:
            ai_ok  = (await client.get(f"{AI_BASE}/health")).json().get("status") == "ok"
            sp_ok  = (await client.get(f"{SPRING}/actuator/health", timeout=5)).status_code < 400
        except Exception:
            ai_ok, sp_ok = False, False

        print(f"  FastAPI: {'🟢' if ai_ok else '🔴'}, Spring: {'🟢' if sp_ok else '🔴'}")
        if not ai_ok:
            print("  FastAPI 서버 없음 — 종료")
            return

        await scenario_1_double_add(client)
        await scenario_2_reply_nesting(client)
        await scenario_3_stale_option_pollution(client)
        await scenario_4_multi_menu_mixed_options(client)
        await scenario_5_cart_reset_and_reorder(client)

    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
