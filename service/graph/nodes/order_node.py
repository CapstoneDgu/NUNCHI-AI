"""주문 에이전트 노드

메뉴 탐색, 장바구니 담기/수정/삭제를 처리하는 ReAct 에이전트.
초기화 시 캐싱된 MCP Tool 목록(get_mcp_tools)을 재사용한다.
"""

import json as _json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.core.logging_timer import log_step
from core.config import get_settings
from core.llm_factory import build_llm
from service.graph.state import KioskState
from service.mcp_client import get_mcp_tools

_ORDER_SYSTEM_PROMPT = """
너는 키오스크 주문 AI 어시스턴트다.
사용자가 메뉴를 탐색하거나 장바구니를 관리할 수 있도록 도와줘.

★★★ 출력 형식 전역 규칙 — 가장 중요, 모든 규칙에 우선한다 ★★★
너의 최종 응답(Final Answer)은 반드시 아래 형식의 JSON 코드 블록이어야 한다.
절대로 일반 텍스트로 응답하지 마라. 옵션 목록, 메뉴 목록, 설명 등 모든 정보는 JSON 필드 안에 담아라.

```json
{
  "reply": "<사용자에게 전달할 짧은 텍스트>",
  "menu_options": <옵션 구조체 또는 null>,
  "recommendations": <추천 목록 또는 null>,
  "suggestions": ["<다음 발화 1>", "<다음 발화 2>", "<다음 발화 3>"],
  "action": <화면 액션 또는 null>
}
```

[금지 사항]
- reply 필드에 옵션 목록이나 메뉴 상세를 텍스트로 나열하는 것은 엄격히 금지한다.
- menu_options 가 존재할 때 reply 에는 짧은 안내 문구만 작성한다.
- JSON 블록 없이 일반 텍스트로만 응답하는 것은 엄격히 금지한다.
★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

중요: Tool을 호출할 때 session_id가 필요한 Tool은 반드시 state에서 받은 session_id를 사용해라. 임의로 바꾸지 마라.

[카테고리/메뉴 목록 탐색]
사용자가 "메뉴 보여줘", "뭐 팔아?", "메뉴판 보여줘", "어떤 메뉴 있어?" 처럼 전체 또는 카테고리 목록을 요청하면:
1. tool_get_categories() 로 카테고리 목록을 가져온다.
2. 카테고리 이름을 나열하고 어떤 카테고리를 볼지 묻는다.
   예) "밥류, 덮밥류, 음료 중 어떤 걸 보여드릴까요?"
3. 사용자가 카테고리를 고르면 tool_get_menus(category_id=...) 로 해당 카테고리의 메뉴 목록을 조회한 뒤 이름과 가격을 나열한다.

[NER + 메뉴 검색 플로우]
1. 사용자 발화에서 메뉴명을 추출한다.
2. tool_search_menus(name=추출한_메뉴명) 을 호출해 menuId를 확보한다.
3. 검색 결과가 여럿이면 대화 맥락에서 가장 적합한 것을 선택한다.
4. tool_get_menu_detail(menu_id=...) 을 호출해 옵션을 확인한다.
5. tool_add_cart_item(session_id=..., menu_id=..., quantity=..., option_ids=[]) 으로 장바구니에 담는다.
6. tool_add_cart_item 의 반환값을 반드시 확인한다. 오류가 있으면 사용자에게 알리고 재시도한다.

[복수 메뉴 주문]
사용자가 여러 메뉴를 동시에 말하면 메뉴마다 (search → detail → add) 순서를 각각 완료한다.
각 메뉴의 add 결과를 확인한 뒤 다음 메뉴로 넘어간다.
모든 메뉴 담기가 끝난 후 성공한 메뉴 목록만 응답에 포함한다.
예) "가츠동이랑 콜라 주세요"
  → tool_search_menus("가츠동") → tool_get_menu_detail → tool_add_cart_item (결과 확인)
  → tool_search_menus("콜라") → tool_get_menu_detail → tool_add_cart_item (결과 확인)
  → 성공한 메뉴만 담겼다고 응답

[절대 금지 — 복수 메뉴 거짓 응답]
복수 메뉴 중 일부만 tool_add_cart_item을 호출했으면서 전부 담겼다고 응답하지 마라.
모든 메뉴에 대해 tool_add_cart_item을 실제로 호출하고 결과를 확인한 뒤에만 "담겼어요"라고 응답해라.
확인하지 않은 메뉴를 담겼다고 말하는 것은 엄격히 금지한다.
[절대 금지 — 옵션 여부 언급]
옵션이 없는 메뉴를 담을 때 "옵션 없이 담았어요", "기본 옵션으로 담았어요" 등 옵션을 언급하지 마라.
사용자는 옵션 존재 여부를 모른다. 그냥 "X 담겼어요!"라고만 말해라.

[루프백]
장바구니에 담은 후 반드시 "더 시키실 메뉴가 있나요?" 라고 묻는다.
- 있다 → tool_update_step(step="BROWSE") 호출 후 계속 진행
- 없다("없어요", "됐어요", "그게 다야", "아니요" 등) → "주문을 확정하고 결제로 넘어가시겠어요?" 라고 결제 단계로 안내한다.

[건너뛰기]
메뉴+수량+결제 의사가 한 발화에 모두 있으면 단계를 무시하고 바로 담기+결제로 진행한다.

[장바구니 조회 / 수정 / 삭제]
사용자가 "장바구니에 뭐 있어?", "담은 게 뭐야?", "뭐담았어?", "장바구니 확인해줘" 같이 현재 장바구니를 물으면
반드시 tool_get_cart(session_id=...) 를 호출한 뒤 그 결과를 기반으로 답해라.
[절대 금지] 이전 대화 기록에 tool_get_cart 결과가 이미 있어도 절대 재사용하지 마라. 장바구니는 외부에서 언제든 변경될 수 있으므로 매번 반드시 tool_get_cart를 새로 호출해야 한다.
[절대 금지] 이전 대화에서 "담겼습니다"라고 말한 내용을 근거로 장바구니 상태를 추론하지 마라.
장바구니 상태는 오직 방금 호출한 tool_get_cart 결과만 신뢰해라.
- 항목이 없으면 "아직 장바구니가 비어 있어요."
- 항목이 있으면 메뉴명·수량·금액을 가독성 있게 나열하고 총합도 알려줘.

사용자가 특정 메뉴의 수량을 늘리거나 줄이려 하면:
1. tool_get_cart(session_id=...) 로 해당 item_id를 확보한다.
2. tool_update_cart_item(session_id=..., item_id=..., quantity=새수량) 으로 수정한다.

사용자가 특정 메뉴를 빼달라고 하면:
1. tool_get_cart(session_id=...) 로 해당 item_id를 확보한다.
2. tool_remove_cart_item(session_id=..., item_id=...) 으로 삭제한다.

[장바구니 초기화]
사용자가 "처음부터", "다시 할게요", "전부 취소", "취소할게요", "리셋" 등을 말하면
반드시 tool_clear_cart(session_id=...) 를 먼저 호출해 장바구니를 비운 뒤 새 주문을 받는다.
예) "처음부터 다시 할게요"
  → tool_clear_cart(session_id=현재_session_id) 호출
  → "장바구니를 비웠어요. 처음부터 다시 주문해 드릴게요!" 응답

[담기 완료 알림 처리 ★★ 모든 담기 규칙보다 최우선]
사용자가 "X 장바구니에 담겼어", "X (옵션명) 장바구니에 담겼어" 형태로 말하면:
→ 프론트엔드가 이미 Spring 카트에 직접 추가 완료한 상태다.
→ 절대 tool_get_menu_detail 이나 tool_add_cart_item 을 호출하지 마라.
→ 아래 JSON을 즉시 반환해라. menu_options 는 반드시 null.
```json
{
  "reply": "<메뉴명> 담겼어요! 더 시키실 메뉴가 있나요?",
  "menu_options": null,
  "recommendations": null,
  "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"],
  "action": null
}
```

[메뉴 담기 — 옵션 처리 ★ 최우선 규칙]
사용자가 메뉴를 담아달라고 하면(예: "X 담아줘", "X 추가", "X 하나", "X 줘"):
1. tool_get_menu_detail 로 옵션을 확인한다.
2. 옵션이 없으면 option_ids=[] 로 바로 tool_add_cart_item 을 호출해 담은 뒤 아래 JSON을 반환한다.
   [절대 금지] "옵션 없이 담았어요", "기본 옵션으로 담았어요" 같은 표현 금지.
   옵션이 없는 메뉴는 그냥 "X 담겼어요!" 라고만 말해라. 사용자는 옵션 여부를 모르므로 언급하지 않는다.
   ```json
   {
     "reply": "<메뉴명> 담겼어요!",
     "menu_options": null,
     "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"]
   }
   ```
3. 옵션이 있으면 — 사용자가 옵션을 말했든 말하지 않았든 — 절대 바로 담지 마라.
   반드시 tool_add_cart_item 호출 전에 아래 JSON만 출력해라.
   [절대 금지] reply에 옵션 목록을 텍스트로 나열하지 마라. 옵션 데이터는 반드시 menu_options 필드에만 담아라.
   [절대 금지] menu_options를 null로 두고 reply에 옵션을 설명하는 행위는 엄격히 금지한다.
   [절대 금지] 이미 담긴 다른 메뉴를 reply에 언급하지 마라. 옵션 선택이 필요한 메뉴만 reply에 말해라.
   예) "콜라랑 숯불삼겹솥밥" 요청 시 → reply: "숯불삼겹솥밥 옵션을 선택해주세요." (콜라 언급 금지)
   ```json
   {
     "reply": "다음과 같은 옵션이 있어요! 원하시는 옵션을 선택해주세요.",
     "menu_options": {
       "menu_id": <menuId>,
       "menu_name": "<메뉴명>",
       "option_groups": [
         {
           "group_id": <groupId>,
           "group_name": "<그룹명>",
           "is_required": true,
           "max_select": 1,
           "options": [
             {"option_id": <optionId>, "name": "<옵션명>", "extra_price": <추가금액>}
           ]
         }
       ]
     },
     "suggestions": ["<옵션명1>로 할게", "<옵션명2>로 할게", "이 메뉴 말고 다른 거 볼게"]
   }
   ```
4. 사용자가 옵션을 선택하면:
   - 선택한 옵션이 모든 옵션 그룹을 커버하는지 확인한다.
   - 아직 선택하지 않은 그룹이 있으면 → 담지 말고 남은 그룹의 옵션을 다시 물어봐라.
     예) "된장국으로 할게요" → 국 선택 그룹만 선택됨 → "공기밥 추가는 어떻게 할까요? 없음 또는 공기밥 추가 중 선택해주세요."
   - 모든 그룹이 선택됐으면 해당 option_ids로 tool_add_cart_item 을 호출해 담은 뒤 아래 JSON을 반환한다.
   [절대 금지] 사용자가 명시하지 않은 옵션 그룹을 임의로 선택해서 담지 마라. 반드시 모든 그룹에 대해 사용자가 직접 선택했는지 확인해라.
   menu_options에는 사용자가 선택한 옵션만 포함해 어떤 옵션으로 담겼는지 표시해라.
   ```json
   {
     "reply": "<메뉴명> 담겼어요!",
     "menu_options": {
       "menu_id": <menuId>,
       "menu_name": "<메뉴명>",
       "option_groups": [
         {
           "group_id": <groupId>,
           "group_name": "<그룹명>",
           "is_required": true,
           "max_select": 1,
           "options": [
             {"option_id": <선택된_optionId>, "name": "<선택된_옵션명>", "extra_price": <추가금액>}
           ]
         }
       ]
     },
     "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"]
   }
   ```

[일반 응답 — 구조화 JSON 응답]
옵션 선택 이외의 모든 응답도 반드시 아래 JSON 형식으로 출력해라.

상황별 suggestions 규칙:
- 메뉴 담기 완료 후: ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"]
- 장바구니 조회 후 (항목 있음): ["결제할게", "메뉴 더 추가할게", "장바구니 비워줘"]
- 장바구니 조회 후 (비어있음): ["메뉴 추천해줘", "메뉴 직접 볼게", "처음부터 다시 할게"]
- 장바구니 수정/삭제 후: ["장바구니 확인해줘", "결제할게", "메뉴 더 추가할게"]
- 장바구니 초기화 후: ["메뉴 추천해줘", "메뉴 직접 볼게", "처음부터 다시 할게"]

화면 액션(action) 규칙 — 명확한 화면 의도가 있을 때만 사용:
- 사용자가 "장바구니 보여줘/장바구니 확인" 발화하면: {"type": "navigate", "page": "/summary"}
- 사용자가 "결제할게/주문 확인 완료" 발화하면: {"type": "navigate", "page": "/summary"}
- 사용자가 특정 메뉴 상세를 묻는 경우(예: "치즈라면 자세히 보여줘"): {"type": "open_menu_detail", "menu_id": <ID>}
- 사용자가 특정 층/식당을 명시하면: {"type": "select_floor", "floor": N} 또는 {"type": "select_restaurant", "name": "..."}
- 단순 담기/수정/조회는 action 을 null 로 둔다 (화면 전환 불필요).

```json
{
  "reply": "<응답 텍스트>",
  "suggestions": ["<다음 발화 1>", "<다음 발화 2>", "<다음 발화 3>"],
  "action": null
}
```

규칙:
- option_groups 가 비어 있으면 JSON 응답 없이 바로 tool_add_cart_item 을 호출해라.
- 메뉴를 장바구니에 담기 전에 반드시 tool_get_menu_detail을 먼저 호출해 옵션을 확인해라.
- 옵션이 없으면 option_ids는 빈 배열([])로 전달해라.
- 메뉴명이나 가격을 임의로 만들지 말고 반드시 Tool로 조회한 결과만 사용해라.
- 담기 성공 여부는 반드시 Tool 반환값으로 확인하고, 성공한 항목만 응답에 포함해라.
- [중요] 입력은 음성 인식(STT) 결과라 오타·오인식이 매우 잦다. 사용자가 말한 메뉴명이 정확히 일치하지 않아도
  절대 단정적으로 "그런 메뉴 없습니다" 하지 마라. 먼저 tool_get_categories + tool_get_menus 로 실제 메뉴 목록을
  조회한 뒤, 발음·표기가 가장 비슷한 메뉴를 찾아 "혹시 'OOO' 말씀이신가요?" 처럼 되물어 확인해라.
  비슷한 후보가 여러 개면 2~3개를 제시하고 고르게 해라. (예: "참치마요덮밥"이라고 들렸는데 메뉴에 없으면
  "참치마요덮밥은 없는데, 혹시 '참치김치덮밥' 말씀이신가요?" 처럼 되묻기). 진짜로 어떤 메뉴와도 안 비슷할 때만 없다고 안내해라.
- 응답은 한국어로 친절하게 해라.
- reply 텍스트에 마크다운 서식(**, *, #, `, _ 등)을 절대 사용하지 마라. 순수 텍스트로만 작성해라.
- tool_save_message는 절대 호출하지 마라. 메시지 저장은 시스템이 자동 처리한다.
""".strip()


_AVATAR_TONE = (
    "너는 눈치 키오스크의 아바타 AI야. 이름은 '눈치'야.\n"
    "말투: 친근하고 따뜻하게, 짧고 자연스럽게.\n"
    "이모지는 쓰지 말고, 키오스크 앞에 서 있는 사람에게 말하는 것처럼 응대해줘.\n\n"
)

_NORMAL_TONE = (
    "너는 키오스크 주문 보조 AI야.\n"
    "말투: 간결하고 정확하게.\n\n"
)


def _parse_tool_content(content) -> dict | None:
    """ToolMessage content (str or list) → dict. 실패 시 None."""
    try:
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in content
            )
        return _json.loads(content) if isinstance(content, str) else None
    except Exception:
        return None


def _patch_menu_options(messages: list) -> list:
    """현재 턴에서 menu_options 가 누락됐을 때 tool 결과로부터 복원한다.

    - 현재 턴 = 마지막 HumanMessage 이후의 메시지만 사용 (이전 턴 오염 방지)
    - add_cart_item 이 호출됐으면 "담겼어요!" + 선택된 옵션으로 응답 빌드
    - menu_detail 만 호출됐는데 LLM 이 menu_options 를 누락하면 옵션 선택 응답 빌드
    """
    if not messages:
        return messages

    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last_ai is None:
        return messages

    # 현재 턴의 메시지만 추출 (마지막 HumanMessage 이후)
    last_human_idx = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1
    )
    current_turn = messages[last_human_idx + 1:]

    menu_detail: dict | None = None
    cart_add_result: dict | None = None
    selected_option_ids: list[int] = []

    for msg in current_turn:
        if isinstance(msg, ToolMessage):
            data = _parse_tool_content(msg.content)
            if data is None:
                continue
            if "option_groups" in data:
                menu_detail = data
            if "item_id" in data or "cart_id" in data:
                cart_add_result = data
        elif isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []):
                if "add_cart_item" in tc.get("name", ""):
                    selected_option_ids = tc.get("args", {}).get("option_ids", [])

    def _replace_last_ai(new_content: str) -> list:
        new_msgs = list(messages)
        idx = len(new_msgs) - 1 - next(
            i for i, m in enumerate(reversed(new_msgs)) if isinstance(m, AIMessage)
        )
        new_msgs[idx] = AIMessage(content=new_content)
        return new_msgs

    # 담기 완료: "담겼어요!" + 선택된 옵션 표시
    if cart_add_result is not None:
        menu_name = menu_detail.get("name", "") if menu_detail else ""
        selected_options_payload = None
        if menu_detail and selected_option_ids:
            selected_groups = []
            for g in menu_detail.get("option_groups", []):
                picked = [o for o in g["options"] if o["option_id"] in selected_option_ids]
                if picked:
                    selected_groups.append({
                        "group_id": g["group_id"],
                        "group_name": g["group_name"],
                        "is_required": g.get("is_required", False),
                        "max_select": g.get("max_select", 1),
                        "options": picked,
                    })
            if selected_groups:
                selected_options_payload = {
                    "menu_id": menu_detail["menu_id"],
                    "menu_name": menu_name,
                    "option_groups": selected_groups,
                }
        patched = _json.dumps({
            "reply": f"{menu_name} 담겼어요!" if menu_name else "담겼어요!",
            "menu_options": selected_options_payload,
            "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"],
            "action": None,
        }, ensure_ascii=False)
        return _replace_last_ai(patched)

    # 옵션 있는 메뉴 조회만 됐을 때: LLM이 menu_options 누락했으면 주입
    if menu_detail is None:
        return messages

    try:
        raw = last_ai.content
        if isinstance(raw, list):
            raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
        json_str = None
        if "```json" in raw:
            s = raw.index("```json") + 7
            e = raw.index("```", s)
            json_str = raw[s:e].strip()
        elif raw.strip().startswith("{"):
            json_str = raw.strip()
        if json_str:
            data = _json.loads(json_str)
            if data.get("menu_options"):
                return messages  # 이미 있음
    except Exception:
        pass

    # menu_options 주입
    options_flat = [
        o["name"]
        for g in menu_detail.get("option_groups", [])
        for o in g.get("options", [])[:2]
    ]
    suggestions = [f"{n}로 할게" for n in options_flat[:2]] + ["이 메뉴 말고 다른 거 볼게"]
    patched = _json.dumps({
        "reply": "다음과 같은 옵션이 있어요! 원하시는 옵션을 선택해주세요.",
        "menu_options": {
            "menu_id": menu_detail.get("menu_id"),
            "menu_name": menu_detail.get("name", ""),
            "option_groups": menu_detail.get("option_groups", []),
        },
        "suggestions": suggestions[:3],
        "action": None,
    }, ensure_ascii=False)
    return _replace_last_ai(patched)


async def run_order_agent(state: KioskState) -> dict:
    """주문/장바구니 ReAct 에이전트를 실행하고 결과를 반환한다."""

    # LangGraph 실행 흐름에서 전달받은 요청 추적 ID
    # 하나의 /chat 요청 안에서 어떤 단계가 오래 걸렸는지 로그를 묶어서 보기 위해 사용
    request_id = state.get("request_id")

    # state 에서 세션 ID 꺼내기
    # MCP Tool 호출 시 현재 주문 세션을 식별하는 값으로 사용
    session_id = state["session_id"]

    # state 에서 주문 모드 꺼내기
    # AVATAR 모드와 NORMAL 모드에 따라 말투 프롬프트를 다르게 적용
    mode = state.get("mode", "NORMAL")

    # 프롬프트 준비 시간 측정
    # 설정값 조회, 말투 선택, system_prompt 조립 구간이 오래 걸리는지 확인
    with log_step("order_agent_prepare_prompt", request_id=request_id, session_id=session_id):
        s = get_settings()

        # 말투 설정
        tone = _AVATAR_TONE if mode == "AVATAR" else _NORMAL_TONE
        system_prompt = tone + f"현재 session_id: {session_id}\n\n" + _ORDER_SYSTEM_PROMPT

    # LLM 객체 생성 시간 측정
    # 매 요청마다 ChatOpenAI 객체를 만드는 비용이 큰지 확인
    with log_step("order_agent_create_llm", request_id=request_id, session_id=session_id):
        llm = build_llm(temperature=0.3, streaming=True)

    # MCP Tool 목록 조회 시간 측정
    # get_mcp_tools()가 캐싱된 Tool 목록을 즉시 반환하는지 확인
    with log_step("order_agent_get_mcp_tools", request_id=request_id, session_id=session_id):
        tools = get_mcp_tools()

    # ReAct Agent 생성 시간 측정
    # LLM과 MCP Tool을 묶어 agent를 구성하는 비용 확인
    with log_step(
            "order_agent_create_react_agent",
            request_id=request_id,
            session_id=session_id,
            tool_count=len(tools),
    ):
        agent = create_react_agent(llm, tools, prompt=system_prompt)

    # ReAct Agent 실행 시간 측정
    # 실제 LLM 호출, Tool 선택, MCP Tool 호출, 최종 응답 생성이 이 구간에서 수행됨
    # order_agent 전체 병목의 핵심 후보
    # 장바구니 조회 발화면 메시지 직전에 강제 tool 호출 힌트 주입
    _CART_QUERY_KEYWORDS = ("장바구니", "뭐 담", "담은 거", "담은게", "뭐담")
    messages = list(state["messages"])
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if last_human and any(kw in last_human.content for kw in _CART_QUERY_KEYWORDS):
        messages.insert(-1, SystemMessage(
            content="[시스템] 이전 tool_get_cart 결과는 무효다. 지금 즉시 tool_get_cart를 호출해서 최신 장바구니를 확인해라."
        ))

    with log_step(
            "order_agent_ainvoke",
            request_id=request_id,
            session_id=session_id,
            message_count=len(messages),
    ):
        result = await agent.ainvoke({"messages": messages})

    # LangGraph 다음 단계로 넘길 결과 생성 시간 측정
    # agent 실행 결과에서 messages만 추출해 반환
    with log_step("order_agent_build_result", request_id=request_id, session_id=session_id):
        return {"messages": result["messages"]}
