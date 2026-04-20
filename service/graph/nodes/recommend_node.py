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

사용자 발화 → 필드 활용 기준:
- "칼로리 낮은 거" → calorie 낮은 메뉴 우선
- "매운 거" → spicyLevel 3 이상, "안 매운 거" → spicyLevel 0
- "알레르기 있어" (예: 땅콩) → allergies에 해당 항목 없는 메뉴만 추천
- "채식이야 / 비건이야" → vegetarianType = VEGETARIAN / VEGAN 메뉴만
- "따뜻한 거" → temperatureType = HOT, "시원한 거" → COLD
- "여름/봄/가을/겨울 메뉴" → seasonRecommended 해당 계절 또는 ALL
- "단백질 많은 거" → protein 높은 메뉴 우선
- "나트륨 낮은 거" → sodium 낮은 메뉴 우선
- 품절(isSoldOut=true) 메뉴는 절대 추천하지 마라.
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
