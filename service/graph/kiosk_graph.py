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
from service.graph.nodes.step_node import transition_step
from service.graph.state import KioskState


def _build_graph(with_checkpointer: bool = True):
    # 빈 그래프 생성
    graph = StateGraph(KioskState)

    # 노드들 등록
    graph.add_node("intent_classifier", classify_intent)
    graph.add_node("order_agent",        run_order_agent)
    graph.add_node("payment_agent",      run_payment_agent)
    graph.add_node("recommend_agent",    run_recommend_agent)
    graph.add_node("nunchi_detector",    detect_nunchi)
    graph.add_node("step_transition",    transition_step)

    # ainvoke()호출 시 항상 여기서 시작
    graph.set_entry_point("intent_classifier")

    # 엣지 설계 (함수 반환 값에 따라 다르게 분기)
    graph.add_conditional_edges(
        "intent_classifier", # 의도 분류 노드 실행
        # 의도 분류 노드 실행이 끝난 후 아래 함수를 실행하여 다음 노드 결정
        route_by_intent,
        {
            "order":      "order_agent", # order 반환시 order_agent로
            "payment":    "payment_agent",
            "recommend":  "recommend_agent",
            "hesitation": "nunchi_detector",
        },
    )

    # 고정 경로 설계
    graph.add_edge("nunchi_detector",  "recommend_agent")
    graph.add_edge("order_agent",      "step_transition")
    graph.add_edge("recommend_agent",  "step_transition")
    graph.add_edge("step_transition",  END)
    graph.add_edge("payment_agent",    END)

    if with_checkpointer:
        return graph.compile(checkpointer=MemorySaver())
    return graph.compile()


def build_kiosk_graph():
    """메인 대화 그래프 — MemorySaver로 세션별 상태를 자동 저장한다."""
    return _build_graph(with_checkpointer=True)


def build_prefetch_graph():
    """프리패치 전용 그래프 — 상태 저장 없이 매 호출을 독립적으로 실행한다."""
    return _build_graph(with_checkpointer=False)
