from __future__ import annotations

"""OrderService — 세션 관리 + 그래프 실행 진입점

LangGraph 그래프를 실행하고, Spring 세션 생성/종료를 관리한다.
thread_id = session_id 로 LangGraph Checkpointer가 세션별 대화 상태를 자동 저장/복원한다.
"""

import asyncio
import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from adapter.spring_adapter import SpringAdapter
from core.config import get_settings
from core.model_context import set_model_override
from core.prefetch_cache import get_prefetch_cache
from domain.order_request import (
    ChatOrderResponse,
    MenuOptionGroup,
    MenuOptionItem,
    MenuOptionsResponse,
    RecommendedMenu,
    StartOrderResponse,
)
from domain.session import OrderType, SessionMode
from kiosk_mcp.tools.session_tools import create_session, save_message
from service.graph.kiosk_graph import build_kiosk_graph, build_prefetch_graph

_GREETING_PROMPT = "안녕하세요! 무엇을 도와드릴까요? 메뉴를 추천해드릴까요, 아니면 직접 골라보시겠어요?"


class OrderService:
    def __init__(self, spring: SpringAdapter) -> None:
        self._spring = spring
        self._graph = build_kiosk_graph()
        self._prefetch_graph = build_prefetch_graph()

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
        캐시에 프리패치된 응답이 있으면 즉시 반환한다.
        """
        # 1. 프리패치 캐시 확인 — 히트 시 즉시 반환
        cached = get_prefetch_cache().get(session_id, text)
        if cached:
            logging.debug("[프리패치 캐시 히트] session=%d text=%r", session_id, text)
            await save_message(self._spring, session_id, "USER", text)
            await save_message(self._spring, session_id, "ASSISTANT", cached.reply)
            return cached

        # 2. 사용자 발화 저장
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

        # JSON 응답 파싱 (추천 / 옵션 / 퀵바 suggestions)
        reply, recommendations, menu_options, suggestions = _parse_agent_reply(raw)
        current_step = result.get("current_step")

        # 3. AI 응답 저장
        await save_message(self._spring, session_id, "ASSISTANT", reply)

        response = ChatOrderResponse(
            session_id=session_id,
            reply=reply,
            current_step=current_step,
            recommendations=recommendations,
            menu_options=menu_options,
            suggestions=suggestions,
        )

        # 4. suggestions가 있으면 백그라운드 프리패치 스케줄링
        if suggestions:
            self._schedule_prefetch(session_id, suggestions, mode)

        return response

    def _schedule_prefetch(self, session_id: int, suggestions: list[str], mode: str) -> None:
        """suggestions 중 프리패치 적합한 것만 백그라운드 태스크로 실행한다.

        실시간 상태에 의존하는 항목(장바구니·결제·주문 변경)은 캐싱해도 stale해지므로 건너뛴다.
        """
        for text in suggestions:
            if _is_prefetchable(text):
                asyncio.create_task(
                    self._run_prefetch(session_id, text, mode),
                    name=f"prefetch-{session_id}",
                )

    async def _run_prefetch(self, session_id: int, text: str, mode: str) -> None:
        """mini 모델 그래프로 suggestion 응답을 미리 생성해 캐시에 저장한다.

        asyncio 태스크는 생성 시점의 컨텍스트 복사본을 가지므로,
        set_model_override() 호출은 이 태스크 안에서만 유효하다.
        에러가 발생해도 로그만 남기고 무시한다. 사용자 응답 흐름에 영향을 주지 않는다.
        """
        try:
            set_model_override(get_settings().prefetch_model)
            initial_state = {
                "messages":      [HumanMessage(content=text)],
                "session_id":    session_id,
                "mode":          mode.upper(),
                "nunchi_signal": None,
            }

            result = await self._prefetch_graph.ainvoke(initial_state)

            messages = result.get("messages") or []
            if not messages:
                return

            raw = messages[-1].content
            reply, recommendations, menu_options, suggestions = _parse_agent_reply(raw)
            current_step = result.get("current_step")

            response = ChatOrderResponse(
                session_id=session_id,
                reply=reply,
                current_step=current_step,
                recommendations=recommendations,
                menu_options=menu_options,
                suggestions=suggestions,
            )
            get_prefetch_cache().set(session_id, text, response)
            logging.debug("[프리패치 완료] session=%d text=%r", session_id, text)
        except Exception as exc:
            logging.debug("[프리패치 실패 무시] session=%d text=%r err=%s", session_id, text, exc)


# 실시간 상태에 의존하므로 프리패치 대상에서 제외할 키워드
# - 장바구니: 조회/수정/초기화 결과가 시점마다 달라짐
# - 결제·주문·취소: 실행 자체가 목적인 액션
# - 담아줘·빼줘·비워줘·수량: 장바구니 변경 액션
_NO_PREFETCH_KEYWORDS = ("장바구니", "결제", "주문", "취소", "담아줘", "빼줘", "비워줘", "수량")


def _is_prefetchable(text: str) -> bool:
    """프리패치 적합 여부를 반환한다. 실시간 상태 의존 발화는 False."""
    return not any(kw in text for kw in _NO_PREFETCH_KEYWORDS)


def _extract_json_block(raw: str) -> Optional[str]:
    """응답 문자열에서 JSON 블록을 추출한다.

    우선순위:
    1. ```json ... ``` 블록이 있으면 그 안의 내용만 추출
    2. 전체 문자열이 JSON이면 그대로 반환
    3. 없으면 None 반환
    """
    text = raw.strip()
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            candidate = parts[1].strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            return candidate
    if text.startswith("{"):
        return text
    return None


def _parse_agent_reply(
    raw: str,
) -> tuple[str, Optional[list[RecommendedMenu]], Optional[MenuOptionsResponse], Optional[list[str]]]:
    """에이전트 JSON 응답을 파싱한다.

    지원 키:
    - recommendations → 추천 메뉴 카드 목록
    - menu_options     → 옵션 선택 구조화 응답
    - suggestions      → 퀵바 다음 발화 추천 문구 목록
    JSON 블록이 없거나 지원 키가 없으면 원본 텍스트를 그대로 반환한다.
    """
    try:
        json_str = _extract_json_block(raw)
        if json_str is None:
            return raw, None, None, None
        data = json.loads(json_str)

        reply = data.get("reply") or data.get("message") or raw
        recommendations: Optional[list[RecommendedMenu]] = None
        menu_options: Optional[MenuOptionsResponse] = None
        suggestions: Optional[list[str]] = None

        if "recommendations" in data:
            recommendations = [RecommendedMenu(**item) for item in data["recommendations"]]

        if "menu_options" in data:
            mo = data["menu_options"]
            menu_options = MenuOptionsResponse(
                menu_id=mo["menu_id"],
                menu_name=mo["menu_name"],
                option_groups=[
                    MenuOptionGroup(
                        group_id=g["group_id"],
                        group_name=g["group_name"],
                        is_required=g.get("is_required", False),
                        max_select=g.get("max_select", 1),
                        options=[MenuOptionItem(**o) for o in g["options"]],
                    )
                    for g in mo.get("option_groups", [])
                ],
            )

        raw_suggestions = data.get("suggestions")
        if isinstance(raw_suggestions, list):
            suggestions = [s for s in raw_suggestions if isinstance(s, str)][:3] or None

        return reply, recommendations, menu_options, suggestions
    except Exception:
        logging.debug("[에이전트 응답 파싱 스킵] JSON 아님 — 원본 텍스트 반환")
        return raw, None, None, None
