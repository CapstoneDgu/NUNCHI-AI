"""추천 에이전트 노드

인기 메뉴 조회, 카테고리별 추천 Tool을 실행해 사용자에게 메뉴를 추천한다.
눈치 감지 노드(nunchi_node)에서도 이 노드로 연결된다.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from mcp.server import make_recommend_tools
from service.graph.state import KioskState

_RECOMMEND_SYSTEM_PROMPT = """
너는 키오스크 메뉴 추천 AI 어시스턴트다.
실제 메뉴 데이터를 기반으로 사용자에게 메뉴를 추천해줘.

규칙:
- 반드시 Tool로 조회한 실제 메뉴 데이터를 기반으로 추천해라. 임의로 메뉴를 만들지 마라.
- 추천할 때는 메뉴명과 가격을 함께 알려줘라.
- 추천 이유를 간단히 덧붙여줘라. (예: "오늘 가장 많이 팔린 메뉴예요")
- 추천 후 "장바구니에 담아드릴까요?" 로 자연스럽게 주문으로 유도해라.
- 응답은 한국어로 친절하고 간결하게 해라.

Tool 선택 기준:
- 영양소·알레르기·온도·채식·계절 조건 → tool_filter_menus 우선 사용
- "잘 팔리는", "인기 메뉴" → tool_get_top_menus 사용
- "밥류", "음료" 등 카테고리 이름이 포함된 요청 → tool_get_categories 로 categoryId 확인 후 tool_get_menus_by_category 사용
- 조건 없이 전체 메뉴 → tool_get_all_menus 사용

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
  예) "저칼로리 비건 메뉴" → tool_filter_menus(max_calorie=500, vegetarian_type="VEGAN")
- 판매량 + 속성 조건이 함께 있을 때: 반드시 두 단계로 처리
  예) "오늘 잘 팔리는 3개 중 단백질 가장 높은 것"
    1. tool_get_top_menus(limit=3) → menuId 목록 획득
    2. tool_get_menu_detail_recommend(menuId) 를 각각 호출 → nutrition 확인
    3. protein 값 비교 후 최고값 추천
  예) "인기 5개 중 나트륨 낮은 것" → 위와 동일 패턴, sodium 비교
- filter 결과가 너무 많으면 그 중 가장 잘 맞는 1~3개를 골라 추천해라.
""".strip()


async def run_recommend_agent(state: KioskState, spring: SpringAdapter) -> dict:
    """추천 ReAct 에이전트를 실행하고 결과를 반환한다."""
    s = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0.5,  # 추천은 약간의 다양성 허용
    )

    tools = make_recommend_tools(spring, state["session_id"])
    agent = create_react_agent(llm, tools, prompt=_RECOMMEND_SYSTEM_PROMPT)

    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}
