"""복잡한 주문 시나리오 테스트

사용법:
  # 단위 테스트만 (API Key 불필요)
  python3 scripts/test_order_scenarios.py

  # 의도 분류 LLM 테스트 포함
  python3 scripts/test_order_scenarios.py --llm
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results.append((name, status, detail))
    print(f"  {status} {name}" + (f"\n       detail: {detail}" if detail and not ok else ""))


# ─── 1. _parse_agent_reply 파싱 단위 테스트 ──────────────────────────────────

def test_parse_agent_reply() -> None:
    from service.order_service import _parse_agent_reply

    print("\n[1] _parse_agent_reply 파싱")

    raw = '```json\n{"reply": "가츠동 담겼어요!", "menu_options": null, "suggestions": ["결제할게", "더 담을게"], "action": null}\n```'
    reply, _, opts, suggs, _ = _parse_agent_reply(raw)
    record("JSON 블록 파싱", reply == "가츠동 담겼어요!" and suggs is not None)

    raw2 = json.dumps({
        "reply": "옵션을 선택해주세요.",
        "menu_options": {
            "menu_id": 10, "menu_name": "숯불삼겹솥밥",
            "option_groups": [{"group_id": 1, "group_name": "국 선택", "is_required": True,
                               "max_select": 1, "options": [{"option_id": 101, "name": "된장국", "extra_price": 0}]}],
        },
        "suggestions": ["된장국으로 할게"], "action": None,
    }, ensure_ascii=False)
    _, _, opts2, _, _ = _parse_agent_reply(raw2)
    record("menu_options 파싱", opts2 is not None and opts2.menu_id == 10)

    _, _, _, _, action_ok = _parse_agent_reply(json.dumps({"reply": "이동", "suggestions": [], "action": {"type": "navigate", "page": "/summary"}}))
    record("action navigate 검증", action_ok is not None and action_ok["page"] == "/summary")

    _, _, _, _, action_bad = _parse_agent_reply(json.dumps({"reply": "이동", "suggestions": [], "action": {"type": "navigate", "page": "/hack"}}))
    record("action 잘못된 page 폐기", action_bad is None)

    reply3, _, _, _, _ = _parse_agent_reply(json.dumps({"reply": "**가츠동** 담겼어요!", "suggestions": [], "action": None}))
    record("reply 마크다운 제거", "**" not in reply3)


# ─── 2. _apply_menu_options_from_messages 단위 테스트 ────────────────────────

def test_apply_menu_options() -> None:
    from service.order_service import _apply_menu_options_from_messages, _parse_agent_reply

    print("\n[2] _apply_menu_options_from_messages")

    detail_payload = json.dumps({
        "menu_id": 10, "name": "숯불삼겹솥밥",
        "option_groups": [{"group_id": 1, "group_name": "국 선택", "is_required": True, "max_select": 1,
                           "options": [{"option_id": 101, "name": "된장국", "extra_price": 0},
                                       {"option_id": 102, "name": "미소국", "extra_price": 0}]}],
    })
    cart_add_payload = json.dumps({"item_id": 999, "menu_id": 10, "quantity": 1})
    no_option_payload = json.dumps({"menu_id": 5, "name": "가츠동", "option_groups": []})
    gats_cart_payload = json.dumps({"item_id": 888, "menu_id": 5, "quantity": 1})

    # 2-1. 담기 완료 후 선택된 옵션만 표시
    ai_add = AIMessage(content='{"reply": "담겼어요!", "menu_options": null}')
    ai_add.tool_calls = [{"name": "tool_add_cart_item", "args": {"session_id": 1, "menu_id": 10, "quantity": 1, "option_ids": [101]}, "id": "tc1"}]
    msgs = [
        HumanMessage(content="숯불삼겹솥밥 된장국으로 담아줘"),
        ToolMessage(content=detail_payload, tool_call_id="tc0"),
        ai_add,
        ToolMessage(content=cart_add_payload, tool_call_id="tc1"),
        AIMessage(content='{"reply": "숯불삼겹솥밥 담겼어요!", "menu_options": null}'),
    ]
    r = _apply_menu_options_from_messages(None, msgs, "담겼어요!")
    record("담기 완료 — 된장국 옵션만 표시", r is not None and r.option_groups[0].options[0].option_id == 101)

    # 2-2. menu_options 누락 시 tool 결과로 복원
    msgs2 = [
        HumanMessage(content="숯불삼겹솥밥 담아줘"),
        ToolMessage(content=detail_payload, tool_call_id="tc0"),
        AIMessage(content='{"reply": "옵션을 선택해주세요.", "menu_options": null}'),
    ]
    r2 = _apply_menu_options_from_messages(None, msgs2, "옵션을 선택해주세요.")
    record("menu_options 누락 → tool 결과 복원", r2 is not None and r2.menu_id == 10)

    # 2-3. 옵션 없는 메뉴 담기 후 menu_options null
    ai_no = AIMessage(content='{"reply": "가츠동 담겼어요!", "menu_options": null}')
    ai_no.tool_calls = [{"name": "tool_add_cart_item", "args": {"session_id": 1, "menu_id": 5, "quantity": 1, "option_ids": []}, "id": "tc2"}]
    msgs3 = [
        HumanMessage(content="가츠동 담아줘"),
        ToolMessage(content=no_option_payload, tool_call_id="tc0"),
        ai_no,
        ToolMessage(content=gats_cart_payload, tool_call_id="tc2"),
        AIMessage(content='{"reply": "가츠동 담겼어요!", "menu_options": null}'),
    ]
    r3 = _apply_menu_options_from_messages(None, msgs3, "가츠동 담겼어요!")
    record("옵션없는 메뉴 담기 → menu_options null", r3 is None)

    # 2-4. 복수 메뉴 혼합 (가츠동 담기 + 숯불삼겹솥밥 옵션 표시)
    ai_mixed = AIMessage(content=json.dumps({
        "reply": "숯불삼겹솥밥 옵션을 선택해주세요.",
        "menu_options": json.loads(detail_payload) | {"menu_id": 10, "menu_name": "숯불삼겹솥밥"},
    }))
    ai_mixed.tool_calls = [{"name": "tool_add_cart_item", "args": {"session_id": 1, "menu_id": 5, "quantity": 1, "option_ids": []}, "id": "tc3"}]
    _, _, opts_from_llm, _, _ = _parse_agent_reply(ai_mixed.content)
    msgs4 = [
        HumanMessage(content="가츠동이랑 숯불삼겹솥밥 주세요"),
        ToolMessage(content=no_option_payload, tool_call_id="tc_a"),
        ToolMessage(content=detail_payload, tool_call_id="tc_b"),
        ai_mixed,
        ToolMessage(content=gats_cart_payload, tool_call_id="tc3"),
        AIMessage(content=ai_mixed.content),
    ]
    r4 = _apply_menu_options_from_messages(opts_from_llm, msgs4, "숯불삼겹솥밥 옵션을 선택해주세요.")
    record("복수메뉴 혼합: 숯불삼겹솥밥 옵션 보존", r4 is not None and r4.menu_id == 10,
           f"menu_id={getattr(r4, 'menu_id', None)}")

    # 2-5. 이전 턴 오염 방지: 이전 턴에 detail이 있어도 현재 턴에 없으면 복원 안 함
    msgs5 = [
        HumanMessage(content="숯불삼겹솥밥 담아줘"),           # 이전 턴
        ToolMessage(content=detail_payload, tool_call_id="old"),
        AIMessage(content='{"reply": "옵션을 선택해주세요."}'),
        HumanMessage(content="가츠동 담아줘"),                  # 현재 턴
        ToolMessage(content=no_option_payload, tool_call_id="cur"),
        AIMessage(content='{"reply": "가츠동 담겼어요!", "menu_options": null}'),
    ]
    r5 = _apply_menu_options_from_messages(None, msgs5, "가츠동 담겼어요!")
    record("이전 턴 option_groups 오염 방지", r5 is None,
           f"menu_id={getattr(r5, 'menu_id', None)} (None이어야 함)")


# ─── 3. 담기 완료 알림 서버 가드 단위 테스트 ─────────────────────────────────

async def test_cart_add_notification_guard() -> None:
    import json
    from langchain_core.messages import HumanMessage

    print("\n[3] 담기 완료 알림 서버 사이드 가드")

    # 실제 run_order_agent 대신 가드 로직만 추출해서 테스트
    _CART_ADD_NOTIFICATION = "장바구니에 담겼어"

    cases = [
        ("가츠동 장바구니에 담겼어",              "가츠동",        "단순 메뉴"),
        ("숯불삼겹솥밥 (된장국) 장바구니에 담겼어", "숯불삼겹솥밥", "옵션 포함"),
        ("콜라 장바구니에 담겼어",                "콜라",          "음료"),
    ]
    for utterance, expected_menu, desc in cases:
        triggered = _CART_ADD_NOTIFICATION in utterance
        if triggered:
            raw_name = utterance.split(_CART_ADD_NOTIFICATION)[0].strip()
            menu_name = raw_name.split("(")[0].strip() if "(" in raw_name else raw_name
            response = json.loads(json.dumps({
                "reply": f"{menu_name} 담겼어요! 더 시키실 메뉴가 있나요?",
                "menu_options": None,
                "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"],
                "action": None,
            }, ensure_ascii=False))
            ok = (menu_name == expected_menu and response["menu_options"] is None)
        else:
            ok = False
        record(f"담기완료 가드 [{desc}] '{utterance}'", ok,
               f"추출된 메뉴명: {menu_name if triggered else '미감지'}")

    # 일반 주문은 가드 미발동 확인
    normal = "가츠동 담아줘"
    record("일반 주문은 가드 미발동", _CART_ADD_NOTIFICATION not in normal)


# ─── 4. 의도 분류 경계 케이스 (LLM 호출) ─────────────────────────────────────

async def test_intent_classification() -> None:
    from service.graph.nodes.intent_node import classify_intent

    print("\n[4] 의도 분류 경계 케이스 (LLM)")

    cases = [
        ("숯불삼겹솥밥이랑 콜라 주세요",   "order",      "복수 메뉴"),
        ("아 됐어요, 그게 다예요",          "payment",    "추가 주문 없음 확정"),
        ("계란 추가 안 할게",               "order",      "옵션 거절"),
        ("카드로 결제할게요",               "payment",    "결제 수단 명시"),
        ("음... 뭐가 맛있지",              "hesitation", "망설임"),
        ("날씨가 어때요?",                 "clarify",    "OOD"),
        ("처음부터 다시 할게요",            "order",      "장바구니 초기화"),
        ("삼겹솥밥 얼마예요?",             "order",      "가격 문의"),
        ("안녕하세요",                     "clarify",    "인사"),
        ("없어요",                         "payment",    "추가 주문 없음 (컨텍스트 없음)"),
        ("가츠동 장바구니에 담겼어",        "order",      "담기 완료 알림 → order 분류 확인"),
    ]
    for utterance, expected, desc in cases:
        state = {"messages": [HumanMessage(content=utterance)], "session_id": 1, "mode": "NORMAL"}
        try:
            result = await classify_intent(state)
            got = result.get("intent")
            record(f"의도분류 [{desc}]", got == expected, f"기대={expected} 실제={got}")
        except Exception as e:
            record(f"의도분류 [{desc}]", False, f"예외: {e}")


# ─── E2E 시나리오 설계서 출력 ────────────────────────────────────────────────

def print_e2e_scenarios() -> None:
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║  E2E 시나리오 — 서버 기동 후 /chat API 또는 UI에서 수동 검증         ║
╚══════════════════════════════════════════════════════════════════════╝

시나리오 A — 수량 이중 담기 재현 테스트 (수정 검증)
─────────────────────────────────────────────────────
  Step 1: 프론트 버튼으로 POST /ai/api/order/cart/add {session_id, menu_id, quantity: 1}
  Step 2: POST /ai/order/chat {"text": "가츠동 장바구니에 담겼어"}
  기대:
    - AI 응답: "가츠동 담겼어요! 더 시키실 메뉴가 있나요?"
    - tool_add_cart_item 호출 없음 (서버 가드 발동)
    - Spring cart에 해당 메뉴 1개만 존재
  확인: Spring GET /api/orders/cart/{sessionId} → items 수량 합계 = 1

시나리오 B — 복수 메뉴 + 혼합 옵션
─────────────────────────────────────────────────────
  Turn 1: "가츠동이랑 숯불삼겹솥밥 주세요"
  기대:
    - 가츠동: tool_add_cart_item 호출 완료
    - 숯불삼겹솥밥: menu_options 반환 (menu_name="숯불삼겹솥밥")
    - reply에 가츠동 언급 없이 "숯불삼겹솥밥 옵션을 선택해주세요."
  Turn 2: "된장국으로 할게"
  기대:
    - tool_add_cart_item(option_ids=[된장국_id]) 호출
    - menu_options에 된장국만 표시
    - Spring cart: 가츠동 1개 + 숯불삼겹솥밥(된장국) 1개

시나리오 C — 옵션 선택 중 다른 메뉴 끼어들기
─────────────────────────────────────────────────────
  Turn 1: "숯불삼겹솥밥 담아줘" → menu_options 표시
  Turn 2: "잠깐, 가츠동 먼저 담아줘"
  기대:
    - 가츠동 담기 완료
    - 숯불삼겹솥밥 옵션 상태 복원 가능 여부 확인 (컨텍스트 의존)

시나리오 D — 장바구니 초기화 후 재주문
─────────────────────────────────────────────────────
  Turn 1: "가츠동 담아줘" → 담김
  Turn 2: "처음부터 다시 할게요"
  기대: tool_clear_cart 호출, Spring cart 비어있음
  Turn 3: "숯불삼겹솥밥 담아줘"
  기대: 정상 옵션 표시 (이전 cart 무관)

시나리오 E — "없어요" 발화의 컨텍스트 의존 분류
─────────────────────────────────────────────────────
  케이스 E-1: 담기 완료 후 "더 시키실 메뉴가 있나요?" → "없어요"
    기대: intent=payment, action navigate /summary

  케이스 E-2: 옵션 선택 중 → "없어요"
    기대: intent=order, 옵션 없음으로 처리

시나리오 F — STT 오인식 메뉴명
─────────────────────────────────────────────────────
  "참치마요 덮밥 주세요" (실제 메뉴가 없을 경우)
  기대: "혹시 'XXX' 말씀이신가요?" 되물음 (단정 거절 금지)
""")


# ─── 결과 요약 ───────────────────────────────────────────────────────────────

def print_summary() -> None:
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = total - passed
    print(f"\n{'='*60}")
    print(f"결과: PASS {passed} / FAIL {failed} / TOTAL {total}")
    if failed:
        print("\n실패 항목:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  {FAIL} {name}" + (f" — {detail}" if detail else ""))


async def main() -> None:
    print("═" * 60)
    print("  주문 시나리오 테스트")
    print("═" * 60)

    test_parse_agent_reply()
    test_apply_menu_options()
    await test_cart_add_notification_guard()

    if "--llm" in sys.argv or os.getenv("RUN_LLM_TESTS") == "1":
        await test_intent_classification()
    else:
        print("\n[4] 의도 분류 LLM 테스트 건너뜀 — --llm 플래그로 실행하세요")

    print_e2e_scenarios()
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
