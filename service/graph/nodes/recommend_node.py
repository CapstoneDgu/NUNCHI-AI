"""추천 에이전트 노드

인기 메뉴 조회, 카테고리별 추천 Tool을 실행해 사용자에게 메뉴를 추천한다.
눈치 감지 노드(nunchi_node)에서도 이 노드로 연결된다.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from core.config import get_settings
from core.model_context import get_current_model
from service.graph.state import KioskState
from service.mcp_client import get_mcp_tools

_RECOMMEND_SYSTEM_PROMPT = """
너는 키오스크 메뉴 추천 AI 어시스턴트다.
실제 메뉴 데이터를 기반으로 사용자에게 메뉴를 추천해줘.

Tool 선택 기준:
- 영양소·알레르기·온도·채식·계절 조건 → tool_filter_menus 우선 사용
- "잘 팔리는", "인기 메뉴", 조건 없는 추천 → tool_get_top_menus(limit=3) 사용
- "밥류", "음료" 등 카테고리 이름이 포함된 요청 → tool_get_categories 로 category_id 확인 후 tool_get_menus 사용

사용자 발화 → tool_filter_menus 파라미터 매핑:
- "칼로리 낮은 거" → max_calorie 적정값 설정
- "고칼로리" → min_calorie 적정값 설정
- "저렴한 거", "N원 이하" → max_price 설정, "N원 이상" → min_price 설정
- "단백질 많은 거" → min_protein 적정값 설정
- "나트륨 낮은 거" → max_sodium 적정값 설정
- "매운 거" → min_spicy_level=3, "안 매운 거" → max_spicy_level=1
- "알레르기 있어" (예: 땅콩) → exclude_allergies="PEANUT"
  알레르기 영문 enum: MILK, EGG, WHEAT, SOY, PEANUT, WALNUT, PINE, SHRIMP, CRAB, SQUID, CLAM, BEEF, PORK, CHICKEN, PEACH, TOMATO, BUCKWHEAT
- "채식이야" → vegetarian_type="VEGETARIAN", "비건이야" → vegetarian_type="VEGAN"
- "따뜻한 거" → temperature_type="HOT", "시원한 거" → temperature_type="COLD"
- "여름/봄/가을/겨울 메뉴" → season="SUMMER"/"SPRING"/"FALL"/"WINTER"
- 품절(isSoldOut=true) 메뉴는 절대 추천하지 마라.

체인(복합) 쿼리 처리 패턴:
- 속성 조건만 있을 때: tool_filter_menus 한 번으로 해결
- 판매량 + 속성 조건이 함께 있을 때:
  1. tool_get_top_menus → menu_id 목록 획득
  2. tool_get_menu_detail 각각 호출 → 속성 확인
- filter 결과가 너무 많으면 가장 잘 맞는 1~3개만 선택해라.

응답 규칙:
- 추천 개수는 최대 3개다.
- 반드시 아래 JSON 형식만 출력해라. 다른 텍스트, 마크다운 블록, 설명을 절대 붙이지 마라.
- message 텍스트에 마크다운 서식(**, *, #, `, _ 등)을 절대 사용하지 마라. 순수 텍스트로만 작성해라.
- message: 추천 메뉴를 안내하는 멘트. 길이와 상세 수준은 맨 아래 [응답 모드] 지시를 따른다.
  [필수] message 는 절대 null 이나 빈 문자열("")로 두지 마라. Tool 조회 결과가 없어도 "조건에 맞는 메뉴를 찾지 못했어요." 처럼 반드시 사용자에게 전달할 문장을 작성해야 한다.
- recommendations: Tool에서 조회한 실제 값만 채워라. 없는 필드는 null로 둬라.
- suggestions: 사용자가 다음에 할 법한 발화 3개. recommendations가 있으면 반드시 마지막 항목을 "다른 메뉴도 추천해줘"로 고정하고 나머지 2개는 탐색/장바구니 관련 문구를 넣어라. ("장바구니 확인해줘", "조건 바꿔서 추천해줘" 등)

화면 액션(action) 규칙:
- recommendations 가 1개 이상이면 첫 메뉴를 강조한다: {"type": "highlight_menu", "menu_id": <첫 추천 메뉴 ID>}
- 사용자 발화가 특정 층("1층/2층/3층 메뉴") 을 명시하면: {"type": "select_floor", "floor": 1}
- 사용자 발화가 특정 식당명("솥앤누들/분식당" 등) 을 명시하면: {"type": "select_restaurant", "name": "솥앤누들"}
- 위 셋이 동시에 해당하면 highlight_menu 를 우선한다.
- recommendations 가 없거나 명확한 화면 의도가 없으면 action 은 null.

출력 형식:
{
  "message": "오늘 인기 메뉴를 추천해 드릴게요!",
  "recommendations": [
    {
      "menu_id": 13,
      "name": "일식카레덮밥",
      "price": 7000,
      "image_url": "/images/menu/덮밥류/일식카레덮밥.png",
      "restaurant_name": "쇼앤누들",
      "floor": 1,
      "quantity_sold": 50
    }
  ],
  "suggestions": ["장바구니 확인해줘", "매운 거 빼고 다시 추천해줘", "다른 메뉴도 추천해줘"],
  "action": {"type": "highlight_menu", "menu_id": 13}
}
""".strip()


async def run_recommend_agent(state: KioskState) -> dict:
    """추천 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()

    llm = ChatOpenAI(model=get_current_model(s.openai_model), api_key=s.openai_api_key, temperature=0.2)

    # 모드별 message 상세 수준 — 텍스트 모드는 카드가 안 보이므로 message 에 상세를 다 담아야 한다.
    mode = state.get("mode", "NORMAL")
    if mode == "AVATAR":
        verbosity = (
            "\n\n[응답 모드] 음성 아바타 모드. message 는 1~2문장으로 짧게. "
            "메뉴명·가격·파는 곳 같은 상세는 recommendations 카드가 보여주니 message 에는 넣지 마라."
        )
    else:
        verbosity = (
            "\n\n[응답 모드] 텍스트 채팅 모드. message 에 추천 메뉴의 이름·가격·파는 곳(층/식당)을 "
            "모두 포함해, 사용자가 텍스트만 봐도 충분히 알 수 있게 2~4문장으로 충실히 작성해라. "
            "(마크다운 서식은 여전히 금지 — 순수 텍스트로만)"
        )

    tools = get_mcp_tools()
    agent = create_react_agent(llm, tools, prompt=_RECOMMEND_SYSTEM_PROMPT + verbosity)
    result = await agent.ainvoke({"messages": state["messages"]})

    return {"messages": result["messages"]}
