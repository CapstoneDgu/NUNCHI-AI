"""키오스크 LangGraph 그래프 조립

모든 노드와 엣지를 조립해서 실행 가능한 그래프로 컴파일한다.
OrderService가 이 그래프를 ainvoke()로 실행한다.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from service.graph.nodes.intent_node import classify_intent, route_by_intent
from service.graph.nodes.nunchi_node import detect_nunchi
from service.graph.nodes.order_node import run_order_agent
from service.graph.nodes.payment_node import run_payment_agent
from service.graph.nodes.recommend_node import run_recommend_agent
from service.graph.state import KioskState


def build_kiosk_graph():
    """컴파일된 그래프를 반환한다."""
    graph = StateGraph(KioskState)

    # 노드 등록
    graph.add_node("intent_classifier", classify_intent)
    graph.add_node("order_agent",        run_order_agent)
    graph.add_node("payment_agent",      run_payment_agent)
    graph.add_node("recommend_agent",    run_recommend_agent)
    graph.add_node("nunchi_detector",    detect_nunchi)

    # 시작점
    graph.set_entry_point("intent_classifier")

    # 조건부 엣지 — 의도에 따라 분기
    graph.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "order":      "order_agent",
            "payment":    "payment_agent",
            "recommend":  "recommend_agent",
            "hesitation": "nunchi_detector",
        },
    )

    # 고정 엣지
    graph.add_edge("nunchi_detector",  "recommend_agent")
    graph.add_edge("order_agent",      END)
    graph.add_edge("payment_agent",    END)
    graph.add_edge("recommend_agent",  END)

    # 세션별 대화 상태 자동 저장 (thread_id = session_id)
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
