"""눈치 감지 노드

React에서 전달된 망설임 신호(침묵, 반복 탐색, 헤징 발화 등)를 분석해
추천 노드로 자연스럽게 연결되도록 메시지를 준비한다.
이 노드 실행 후에는 항상 recommend_agent 노드로 이동한다.
"""

from langchain_core.messages import SystemMessage

from service.graph.state import KioskState

# 눈치 신호별 추천 유도 메시지
_NUNCHI_HINTS: dict[str, str] = {
    "silence":        "고객이 오랫동안 화면을 보며 고민 중이다. 인기 메뉴를 먼저 추천해줘.",
    "hesitation":     "고객이 '음...', '뭐가 좋지' 같은 망설임 발화를 했다. 부담 없이 추천해줘.",
    "repeat_browse":  "고객이 같은 메뉴나 카테고리를 반복해서 확인하고 있다. 해당 메뉴를 중심으로 추천해줘.",
}
_DEFAULT_HINT = "고객이 결정을 못 하고 있다. 인기 메뉴를 추천해줘."


async def detect_nunchi(state: KioskState) -> dict:
    """눈치 신호를 분석해 추천 노드로 전달할 힌트 메시지를 state에 추가한다."""
    signal = state.get("nunchi_signal") or ""
    hint = _NUNCHI_HINTS.get(signal, _DEFAULT_HINT)

    # 추천 노드가 이 힌트를 보고 적절한 추천을 수행하도록 SystemMessage로 주입
    return {
        "messages": [SystemMessage(content=hint)],
        # 라우팅은 kiosk_graph 고정 엣지(nunchi_detector → recommend_agent)로 결정되므로
        # intent 를 별도로 세팅할 필요 없다.
    }
