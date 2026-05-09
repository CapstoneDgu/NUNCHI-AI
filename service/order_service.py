from __future__ import annotations

"""OrderService — 세션 관리 + 그래프 실행 진입점

LangGraph 그래프를 실행하고, Spring 세션 생성/종료를 관리한다.
thread_id = session_id 로 LangGraph Checkpointer가 세션별 대화 상태를 자동 저장/복원한다.
"""

import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from adapter.spring_adapter import SpringAdapter
from domain.order_request import ChatOrderResponse, RecommendedMenu, StartOrderResponse
from domain.session import OrderType, SessionMode
from kiosk_mcp.tools.session_tools import create_session, save_message
from service.graph.kiosk_graph import build_kiosk_graph

_GREETING_PROMPT = "안녕하세요! 무엇을 도와드릴까요? 메뉴를 추천해드릴까요, 아니면 직접 골라보시겠어요?"


class OrderService:
    def __init__(self, spring: SpringAdapter) -> None:
        self._spring = spring
        self._graph = build_kiosk_graph()

    async def start(
        self,
        mode: SessionMode = SessionMode.avatar,
        language: str = "ko",
        order_type: OrderType = OrderType.dine_in,
    ) -> StartOrderResponse:
        """Spring 세션을 생성하고 첫 인사 메시지를 반환한다."""
        session = await create_session(self._spring, mode, language, order_type)

        # 첫 인사 — LLM 호출 없이 고정 메시지로 빠르게 응답
        return StartOrderResponse(
            session_id=session.session_id,
            greeting=_GREETING_PROMPT,
        )

    async def handle_chat(
        self,
        session_id: int,
        text: str,
        nunchi_signal: Optional[str] = None,
        mode: str = "NORMAL",
    ) -> ChatOrderResponse:
        """사용자 발화를 받아 그래프를 실행하고 AI 응답을 반환한다.

        thread_id를 session_id로 사용하면 LangGraph Checkpointer가
        이전 대화 상태를 자동으로 복원한다.
        """
        # 1. 사용자 발화 저장
        await save_message(self._spring, session_id, "USER", text)

        # session_id와 messages, nunchi_signal만 넘긴다.
        # order_id / payment_id / intent 등은 그래프 노드가 관리하며
        # 매 요청마다 None으로 덮어쓰면 이전 턴에서 저장된 값이 초기화된다.
        initial_state = {
            "messages":      [HumanMessage(content=text)],
            "session_id":    session_id,
            "mode":          mode.upper(),
            "nunchi_signal": nunchi_signal,
        }

        result = await self._graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": str(session_id)}},
        )

        messages = result.get("messages") or []
        if not messages:
            raise RuntimeError("그래프 실행 결과에 메시지가 없습니다")
        raw = messages[-1].content

        # 추천 노드가 JSON을 반환한 경우 파싱해 구조화 응답으로 변환
        reply, recommendations = _parse_recommend_reply(raw)

        # 2. AI 응답 저장
        await save_message(self._spring, session_id, "ASSISTANT", reply)

        return ChatOrderResponse(session_id=session_id, reply=reply, recommendations=recommendations)


def _parse_recommend_reply(raw: str) -> tuple[str, Optional[list[RecommendedMenu]]]:
    """추천 노드 JSON 응답을 파싱한다. JSON이 아니면 원본 텍스트를 그대로 반환한다."""
    try:
        text = raw.strip()
        # ```json ... ``` 블록 제거
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if "recommendations" not in data:
            return raw, None
        menus = [RecommendedMenu(**item) for item in data["recommendations"]]
        return data.get("message", raw), menus
    except Exception:
        logging.debug("[추천 파싱 스킵] JSON 아님 — 원본 텍스트 반환")
        return raw, None
