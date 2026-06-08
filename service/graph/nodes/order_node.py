"""주문 에이전트 노드

메뉴 탐색, 장바구니 담기/수정/삭제를 처리하는 ReAct 에이전트.
초기화 시 캐싱된 MCP Tool 목록(get_mcp_tools)을 재사용한다.
"""

import json as _json
import logging
import re as _re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.core.logging_timer import log_step
from adapter.factory import get_spring_adapter
from core.llm_factory import build_llm
from kiosk_mcp.tools.cart_tools import get_cart
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
- JSON 블록 없이 일반 텍스트로만 응답하는 것은 엄격히 금지한다.
- (★원칙2) reply 필드에 옵션 목록·메뉴 상세를 텍스트로 나열하지 마라. menu_options 가 있을 때는
  reply 에 짧은 안내 문구만 작성해라.

[★원칙1 — 확인되지 않은 것을 사실처럼 말하지 마라] 모든 상황에 공통 적용되는 최우선 원칙. 이후 "(★원칙1)" 표시는 이 규칙을 가리킨다.
- 메뉴를 담을 때: 대상 메뉴 전부에 대해 tool_add_cart_item 을 실제로 호출하고 성공 결과를 확인한
  항목만 "담겼어요"라고 말해라. 일부만 호출했으면서 전부 담겼다고 답하는 것은 절대 금지한다.
- 장바구니 상태를 답할 때: 직전 대화의 tool_get_cart 결과나 "담겼습니다"라는 발언이 있었더라도
  그것을 근거로 추론하지 마라. 장바구니는 외부에서 언제든 바뀔 수 있으므로 매번 새로 tool_get_cart 를
  호출해 그 결과만 신뢰해라.
- 메뉴명·가격·옵션 등 모든 사실 정보는 반드시 Tool 조회 결과만 사용하고 임의로 만들지 마라.

[★원칙2 — reply 에는 메뉴/옵션 상세를 나열하지 말고 구조화 필드에만 담아라] 이후 "(★원칙2)" 표시는 이 규칙을 가리킨다.
- 옵션 목록·옵션 그룹 정보는 reply 에 텍스트로 풀어 쓰지 말고 menu_options 필드에만 담아라.
  menu_options 를 null 로 둔 채 reply 에서 옵션을 설명하는 것도 금지한다.
- 옵션이 없는 메뉴를 담을 때 "옵션 없이 담았어요", "기본 옵션으로 담았어요" 같은 표현도 금지한다.
  사용자는 옵션 존재 여부를 모르므로 그냥 "X 담겼어요!"라고만 말해라.
★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

중요: Tool을 호출할 때 session_id가 필요한 Tool은 반드시 state에서 받은 session_id를 사용해라. 임의로 바꾸지 마라.

[카테고리/메뉴 목록 탐색]
사용자가 "메뉴 보여줘", "뭐 팔아?", "메뉴판 보여줘", "어떤 메뉴 있어?" 처럼 전체 또는 카테고리 목록을 요청하면:
1. tool_get_categories() 로 카테고리 목록을 가져온다.
2. 카테고리 이름을 나열하고 어떤 카테고리를 볼지 묻는다.
   예) "밥류, 덮밥류, 음료 중 어떤 걸 보여드릴까요?"
3. 사용자가 카테고리를 고르면 tool_get_menus(category_id=...) 로 해당 카테고리의 메뉴 목록을 조회한 뒤 이름과 가격을 나열한다.

[카테고리 + "아무거나" 요청 — 인기 메뉴로 바로 담기] ★ 아래 NER 검색 플로우보다 먼저 적용
사용자가 "면류 아무거나", "밥류 아무거나 줘", "음료 아무거나 담아줘" 처럼 구체적인 메뉴명 없이
카테고리만 말하고 "아무거나/암거나/뭐든/그냥"이라고 하면, 메뉴명을 추출해 검색하는 대신
아래 절차로 그 카테고리 안의 인기 메뉴를 직접 찾아 바로 담아라. 어떤 메뉴를 원하는지
되묻지 마라 — "아무거나"는 "AI가 대신 골라달라"는 뜻이다.

1. tool_get_categories() 로 카테고리 목록을 확인하고, 발화 속 카테고리명과 정확히 일치하는
   category_id를 찾는다. (예: "면류"→면류 카테고리, "밥류"→밥류 카테고리. 비슷한 이름의
   다른 카테고리와 헷갈리지 마라. 카테고리를 특정할 수 없으면 전체 인기 메뉴 중에서 고른다.)
2. tool_get_menus(category_id=...) 로 그 카테고리에 속한 menu_id 목록을 확보한다.
3. tool_get_top_menus(limit=10) 으로 오늘 판매량 순위를 가져온 뒤, 그 순위 중 2번 목록에
   속하는 가장 순위가 높은 메뉴 하나를 고른다.
   (★원칙1 — 반드시 2번에서 확보한 카테고리 메뉴 목록과 교차 검증한 뒤 골라라.
   카테고리에 속하지 않는 메뉴를 고르는 것은 절대 금지한다.)
4. tool_get_menu_detail 로 옵션을 확인한 뒤 [메뉴 담기 — 옵션 처리] 규칙을 그대로 따른다
   (옵션이 없으면 즉시 담고, 있으면 평소처럼 옵션 선택 UI를 보여준다).
5. 담은 뒤 reply에는 "오늘 인기 있는 <메뉴명>을 담아드렸어요!" 처럼, 사용자가 직접 고르지
   않고 AI가 골라줬다는 점과 그 근거(오늘 인기 메뉴)를 자연스럽게 한 문장으로 설명해라.

복수 메뉴 요청에 "카테고리 아무거나"가 섞여 있으면(예: "면류 아무거나랑 콜라 담아줘"),
위 1~3단계로 그 메뉴의 menu_id를 먼저 확정한 뒤 [복수 메뉴 주문] 절차에 따라 나머지
메뉴와 함께 처리해라.

[NER + 메뉴 검색 플로우]
1. 사용자 발화에서 메뉴명을 추출한다.
2. tool_search_menus(name=추출한_메뉴명) 을 호출해 menuId를 확보한다.
3. 검색 결과가 여럿이면 대화 맥락에서 가장 적합한 것을 선택한다.
4. tool_get_menu_detail(menu_id=...) 을 호출해 옵션을 확인한다.
5. tool_add_cart_item(session_id=..., menu_id=..., quantity=..., option_ids=[]) 으로 장바구니에 담는다.
6. tool_add_cart_item 의 반환값을 반드시 확인한다 (★원칙1). 오류가 있으면 사용자에게 알리고 재시도한다.

[복수 메뉴 주문]
사용자가 여러 메뉴를 동시에 말하면 반드시 아래 2단계 순서로 처리해라.

★ 1단계 — 모든 메뉴에 대해 search → detail 을 먼저 완료한다.
★ 2단계 — 처리 순서:
   (A) 옵션이 없는 메뉴를 전부 먼저 tool_add_cart_item 으로 담는다. (★원칙1 — 호출·확인 필수)
   (B) 옵션이 있는 메뉴가 남아있으면 첫 번째 메뉴의 옵션 선택 UI를 표시한다.
       → 나머지 옵션 메뉴는 이번 턴에서 처리하지 않는다. 사용자가 옵션 선택 후 다음 턴에서 담는다.

예) "콜라랑 숯불삼겹솥밥 주세요"
  1단계: tool_search_menus("콜라") → detail(옵션없음) / tool_search_menus("숯불삼겹솥밥") → detail(옵션있음)
  2단계 (A): tool_add_cart_item("콜라", option_ids=[]) → 담기 확인
  2단계 (B): 숯불삼겹솥밥 옵션 UI 표시 (reply에 콜라 언급 금지)

[절대 금지 — 복수 메뉴 순서 위반]
옵션 없는 메뉴를 담지 않은 채 옵션 있는 메뉴의 옵션을 먼저 표시하는 것은 엄격히 금지한다.
반드시 옵션 없는 메뉴를 tool_add_cart_item 으로 먼저 담은 뒤 옵션 UI를 표시해라.

[루프백]
장바구니에 담은 후 반드시 "더 시키실 메뉴가 있나요?" 라고 묻는다.
- 있다 → tool_update_step(step="BROWSE") 호출 후 계속 진행
- 없다("없어요", "됐어요", "그게 다야", "아니요" 등) → "주문을 확정하고 결제로 넘어가시겠어요?" 라고 결제 단계로 안내한다.

[건너뛰기]
메뉴+수량+결제 의사가 한 발화에 모두 있으면 단계를 무시하고 바로 담기+결제로 진행한다.

[장바구니 조회 / 수정 / 삭제]
사용자가 "장바구니에 뭐 있어?", "담은 게 뭐야?", "뭐담았어?", "장바구니 확인해줘" 같이 현재 장바구니를 물으면
반드시 tool_get_cart(session_id=...) 를 새로 호출한 뒤 그 결과만 근거로 답해라
(★원칙1 — 이전 tool_get_cart 결과나 "담겼습니다" 발언 재사용·추론 절대 금지. 장바구니는 외부에서 언제든 바뀐다).
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

[절대 금지 — 빈 약속(★원칙1 의 한 형태)] 초기화와 동시에 특정 메뉴를 다시 담아달라는 요청이 있으면
(예: "장바구니 비우고 계란라면 다시 담아줘", "취소하고 계란라면으로 할래"),
"옵션 선택부터 도와드릴게요" 처럼 다음에 할 일을 말로만 예고하고 menu_options 를 비워두는 것은
절대 금지한다. 같은 턴 안에서 tool_clear_cart 호출 후 곧바로 그 메뉴에 대해
[메뉴 담기 — 옵션 처리] 절차를 실제로 수행해라 — tool_get_menu_detail 로 옵션을 조회하고,
옵션이 있으면 menu_options 를 채운 옵션 선택 JSON 을, 없으면 바로 담은 결과를 반환해라.
말한 행동은 반드시 그 턴 안에서 실행까지 끝내고 결과를 JSON 에 반영해야 한다.

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
2. 옵션이 없으면 option_ids=[] 로 바로 tool_add_cart_item 을 호출해 담은 뒤(★원칙1) 아래 JSON을 반환한다.
   (★원칙2) "옵션 없이 담았어요" 같은 표현 없이 그냥 "X 담겼어요!"라고만 말해라.
   ```json
   {
     "reply": "<메뉴명> 담겼어요!",
     "menu_options": null,
     "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"]
   }
   ```
3. 옵션이 있으면 — 사용자가 옵션을 말했든 말하지 않았든 — 절대 바로 담지 마라.
   반드시 tool_add_cart_item 호출 전에 아래 JSON만 출력해라.
   (★원칙2) reply에 옵션 목록을 나열하지 마라. 옵션 데이터는 menu_options 필드에만 담아라.
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
   - 모든 그룹이 선택됐으면 해당 option_ids로 tool_add_cart_item 을 호출해 담은 뒤(★원칙1) 아래 JSON을 반환한다.
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
- 담기 성공 여부는 반드시 Tool 반환값으로 확인하고, 성공한 항목만 응답에 포함해라 (★원칙1).
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

# ── 모드 전용 행동 지침 — 공통 본문(_ORDER_SYSTEM_PROMPT) 뒤에 덧붙는다 ──────────
# ★원칙1/★원칙2, JSON 형식, tool 사용법, 장바구니 흐름 등 공통 규칙은 두 모드가
# 동일하게 따르되, 모드에 따라 실제로 달라져야 하는 행동(예: action 사용 범위,
# 화면 제어 여부, reply 상세 수준)만 여기서 모드별 블록으로 분리해 추가한다.
# 빈 문자열이면 추가 지침 없이 공통 본문 그대로 사용한다.
_AVATAR_MODE_GUIDE = ""

# 일반(터치+음성) 모드 전용 지침 — 공통 본문 뒤에 덧붙는다.
# 일반 모드에는 사용자가 보는 터치 화면이 있으므로, 음성 응답만 하지 말고
# action/recommendations 로 화면을 실제 주문 플로우(목록→상세→옵션 모달→장바구니→결제)대로
# 움직이게 한다. 공통 본문과 겹치는 주문/장바구니/옵션 규칙은 반복하지 않고 화면 제어만 추가한다.
_NORMAL_MODE_GUIDE = (
    "\n\n[일반(터치+음성) 모드 전용 지침 — 화면을 실제 주문 플로우대로 움직여라]\n"
    "이 모드에는 사용자가 직접 보는 터치 화면이 있다(메뉴 목록·상세 오버레이·옵션 모달·층/식당 탭·장바구니).\n"
    "대화만 진행하지 말고, 아래처럼 action/recommendations 로 화면을 함께 제어해 실제 주문 플로우를 따라가라.\n"
    "\n"
    "1) 메뉴를 '궁금해하거나 언급만' 한 단계 — 곧장 옵션으로 가지 말고 먼저 상세를 띄워라.\n"
    "   (예: \"OO 어때?\", \"OO 보여줘\", \"OO 뭐야\", \"OO 괜찮아?\" 처럼 담기 의사가 분명치 않을 때)\n"
    "   → action 에 {\"type\": \"open_menu_detail\", \"menu_id\": <ID>} 를 넣어 상세 오버레이를 연다.\n"
    "     (또는 recommendations 에 그 메뉴 '1개만' 담으면 프론트가 상세를 자동으로 연다.)\n"
    "   → reply 로는 짧게 소개하고 담을지 물어라. 이 단계에선 menu_options 를 채우지 마라.\n"
    "\n"
    "2) 담기/주문 의사가 '분명한' 발화 — 그때 비로소 [메뉴 담기 — 옵션 처리] 규칙대로 진행한다.\n"
    "   (예: \"OO 담아줘\", \"그걸로 주문\", \"OO 시킬게\")\n"
    "   → 옵션이 있으면 menu_options 를 채워 옵션 모달을 띄우고, 없으면 바로 담은 결과를 반환한다.\n"
    "\n"
    "3) 화면 이동이 자연스러운 발화는 action 을 적극 사용한다.\n"
    "   - 특정 층/식당 지목: {\"type\": \"select_floor\", \"floor\": N} 또는 {\"type\": \"select_restaurant\", \"name\": \"...\"}\n"
    "   - 장바구니/결제로 진행: {\"type\": \"navigate\", \"page\": \"/summary\"} (공통 규칙과 동일)\n"
    "   - 여러 메뉴를 추천/비교만 할 때: recommendations 에 여러 개를 담아 카드로 강조한다(상세는 열리지 않는다).\n"
    "\n"
    "4) 단순 담기·수정·조회처럼 화면 전환이 필요 없으면 action 은 null 로 둔다.\n"
).rstrip()


# ── 장바구니 담기 결과 검증 가드 ──────────────────────────────────────────────
# LLM 이 "OO 담았어요" 라고 답하면서 실제로는 다른 메뉴를 담는 환각을 막기 위해,
# tool_add_cart_item 호출 직후 장바구니 응답에서 실제로 담긴 메뉴명을 확인하고
# 최종 reply/menu_options 의 메뉴명이 다르면 코드가 직접 교정한다.
# (LLM 재호출 없이 문자열 치환만 하므로 응답 시간에 미치는 영향은 거의 없다.)
_MENU_ADDED_PATTERN = _re.compile(r"^(.{1,40}?)\s*(담겼어요|담았어요)")


def _find_canonical_menu_name(cart_json: str, menu_id, option_ids) -> str | None:
    """tool_add_cart_item 이 반환한 장바구니 데이터에서 실제로 담긴 메뉴명을 찾는다."""
    try:
        cart = _json.loads(cart_json)
    except (TypeError, ValueError):
        return None
    wanted_options = set(option_ids or [])
    for item in cart.get("items", []):
        if item.get("menu_id") != menu_id:
            continue
        item_options = {opt.get("option_id") for opt in item.get("options", [])}
        if item_options == wanted_options:
            return item.get("menu_name")
    return None


def _extract_json_payload(content):
    """AIMessage content 에서 JSON 페이로드를 파싱한다. (data, 코드블록여부) 반환."""
    text = content if isinstance(content, str) else "".join(
        part.get("text", "") if isinstance(part, dict) else str(part) for part in content
    )
    stripped = text.strip()
    fenced = stripped.startswith("```")
    json_text = stripped.strip("`").lstrip("json").strip() if fenced else stripped
    try:
        return _json.loads(json_text), fenced
    except (TypeError, ValueError):
        return None, fenced


async def _verify_and_fix_cart_add_reply(messages: list, session_id: int) -> list:
    """장바구니 담기 응답을 실제 데이터와 대조해 환각을 코드로 직접 교정한다.

    1) tool_add_cart_item 을 호출했지만 reply/menu_options 의 메뉴명이 실제로 담긴
       메뉴명과 다른 경우 (엉뚱한 메뉴를 담고 다른 이름으로 보고하는 환각) — 즉시 교정.
    2) tool_add_cart_item 호출 자체가 없었는데 "OO 담겼어요" 라고 답한 경우
       (호출도 없이 성공했다고 거짓 보고하는 환각) — tool_get_cart 로 사실관계를
       확인한 뒤에만 정직한 안내문으로 교정한다 (불필요한 추가 호출 최소화).
    """
    tool_call_args: dict[str, dict] = {}
    for m in messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                if tc.get("name") == "tool_add_cart_item":
                    tool_call_args[tc["id"]] = tc.get("args", {})

    canonical_by_menu_id: dict[int, str] = {}
    for m in messages:
        if isinstance(m, ToolMessage) and m.tool_call_id in tool_call_args:
            args = tool_call_args[m.tool_call_id]
            name = _find_canonical_menu_name(m.content, args.get("menu_id"), args.get("option_ids"))
            if name:
                canonical_by_menu_id[args["menu_id"]] = name

    final = messages[-1]
    if not isinstance(final, AIMessage):
        return messages
    data, fenced = _extract_json_payload(final.content)
    if not isinstance(data, dict):
        return messages

    changed = False
    reply = data.get("reply")
    menu_options = data.get("menu_options")
    match = _MENU_ADDED_PATTERN.match(reply.strip()) if isinstance(reply, str) else None

    if canonical_by_menu_id:
        if isinstance(menu_options, dict) and menu_options.get("menu_id") in canonical_by_menu_id:
            canonical = canonical_by_menu_id[menu_options["menu_id"]]
            claimed = menu_options.get("menu_name")
            if claimed and claimed != canonical:
                menu_options["menu_name"] = canonical
                if isinstance(reply, str) and claimed in reply:
                    reply = reply.replace(claimed, canonical)
                    data["reply"] = reply
                changed = True
                logging.warning("[장바구니 담기 검증] menu_options 메뉴명 환각 교정: %r → %r", claimed, canonical)
        elif len(canonical_by_menu_id) == 1 and match:
            canonical = next(iter(canonical_by_menu_id.values()))
            claimed = match.group(1).strip()
            if claimed != canonical:
                data["reply"] = reply.replace(claimed, canonical, 1)
                changed = True
                logging.warning("[장바구니 담기 검증] reply 메뉴명 환각 교정: %r → %r", claimed, canonical)
    elif match:
        # tool_add_cart_item 호출이 전혀 없었는데 "담겼어요" 라고 답한 경우 — 사실관계 확인 후 교정
        claimed = match.group(1).strip()
        try:
            cart = await get_cart(get_spring_adapter(), session_id)
            actually_added = any(claimed in item.menu_name or item.menu_name in claimed for item in cart.items)
        except Exception:
            actually_added = True  # 조회 실패 시에는 섣불리 교정하지 않는다 (오탐 방지)

        if not actually_added:
            data["reply"] = f"죄송해요, {claimed} 담는 데 문제가 있었어요. 다시 한 번 말씀해 주시겠어요?"
            data["menu_options"] = None
            data["recommendations"] = None
            data["suggestions"] = ["다시 담아줘", "장바구니 확인해줘", "메뉴 추천해줘"]
            data["action"] = None
            changed = True
            logging.warning("[장바구니 담기 검증] '담겼어요' 거짓 보고 감지 — 정직한 안내로 교정: claimed=%r", claimed)

    if not changed:
        return messages

    new_text = _json.dumps(data, ensure_ascii=False)
    if fenced:
        new_text = f"```json\n{new_text}\n```"
    return messages[:-1] + [AIMessage(content=new_text)]


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
        tone = _AVATAR_TONE if mode == "AVATAR" else _NORMAL_TONE
        mode_guide = _AVATAR_MODE_GUIDE if mode == "AVATAR" else _NORMAL_MODE_GUIDE
        system_prompt = (
            tone + f"현재 session_id: {session_id}\n\n" + _ORDER_SYSTEM_PROMPT + mode_guide
        )

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

    # ── 서버 사이드 담기 완료 알림 가드 ────────────────────────────────────────
    # 프론트가 버튼으로 /ai/api/order/cart/add 를 직접 호출한 뒤
    # "X 장바구니에 담겼어" 형태로 AI 에게 알림을 보내는 경우,
    # LLM 에 넘기지 않고 즉시 응답을 반환해 이중 담기를 원천 차단한다.
    _CART_ADD_NOTIFICATION = "장바구니에 담겼어"
    messages = list(state["messages"])
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if last_human and _CART_ADD_NOTIFICATION in (last_human.content or ""):
        raw_name = last_human.content.split(_CART_ADD_NOTIFICATION)[0].strip()
        menu_name = raw_name.split("(")[0].strip() if "(" in raw_name else raw_name
        response = _json.dumps({
            "reply": f"{menu_name} 담겼어요! 더 시키실 메뉴가 있나요?",
            "menu_options": None,
            "recommendations": None,
            "suggestions": ["장바구니 확인해줘", "메뉴 더 추가할게", "결제할게"],
            "action": None,
        }, ensure_ascii=False)
        return {"messages": [AIMessage(content=response)]}

    # ── 장바구니 조회 발화: 강제 tool 호출 힌트 주입 ──────────────────────────
    _CART_QUERY_KEYWORDS = ("장바구니", "뭐 담", "담은 거", "담은게", "뭐담")
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
    # agent 실행 결과에서 messages만 추출하고, 장바구니 담기 결과를 검증·교정한 뒤 반환
    with log_step("order_agent_build_result", request_id=request_id, session_id=session_id):
        return {"messages": await _verify_and_fix_cart_add_reply(result["messages"], session_id)}
