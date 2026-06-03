from __future__ import annotations

"""OrderService — 세션 관리 + 그래프 실행 진입점

LangGraph 그래프를 실행하고, Spring 세션 생성/종료를 관리한다.
thread_id = session_id 로 LangGraph Checkpointer가 세션별 대화 상태를 자동 저장/복원한다.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import AsyncGenerator, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from adapter.spring_adapter import SpringAdapter
from app.core.logging_timer import log_step
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

# SSE 스트리밍 대상 노드 — 최종 응답을 생성하는 LLM 노드만 포함
# intent_classifier는 의도 분류용 중간 노드이므로 제외
_STREAMING_NODES = {"agent"}


class _MessageExtractor:
    """LLM이 스트리밍하는 JSON 토큰에서 "message" 필드 값만 추출한다.

    LLM 출력 형식: {"message": "안녕하세요!", "recommendations": [...]}
    토큰이 잘려서 오므로 버퍼에 쌓으며 "message": " 패턴을 탐색한 뒤
    그 이후 값만 프론트로 흘려보낸다.
    """

    _OPEN = re.compile(r'"message"\s*:\s*"')

    def __init__(self) -> None:
        self._buf = ""
        self._active = False   # message 값 구간 진입 여부
        self._finished = False # message 값 추출 완료 여부

    def feed(self, token: str) -> str:
        """추출된 텍스트를 반환한다. 해당 구간이 아니면 빈 문자열."""
        if self._finished:
            return ""

        if self._active:
            # 닫는 따옴표 탐색 (프롬프트에서 이스케이프 없는 순수 텍스트 보장)
            close = token.find('"')
            if close == -1:
                return token
            self._active = False
            self._finished = True
            return token[:close]

        self._buf += token
        m = self._OPEN.search(self._buf)
        if not m:
            # 패턴이 버퍼 끝에 걸쳐있을 수 있으므로 최근 30자만 유지
            if len(self._buf) > 30:
                self._buf = self._buf[-30:]
            return ""

        rest = self._buf[m.end():]
        self._buf = ""
        self._active = True
        return self.feed(rest)


class OrderService:
    def __init__(self, spring: SpringAdapter) -> None:
        self._spring = spring # Spring 통신 객체 저장
        self._graph = build_kiosk_graph() # 메인 LangGraph 그래프 생성
        self._prefetch_graph = build_prefetch_graph() # 프리패치용 그래프 생성

    async def start(
        self, # OrderService 인스턴스 자신
        mode: SessionMode = SessionMode.avatar, # body.mode에서 넘어온 값
        language: str = "ko", # body.language
        order_type: OrderType = OrderType.dine_in, # body.order_type
    ) -> StartOrderResponse:
        """Spring 세션을 생성하고 첫 인사 메시지를 반환한다."""
        session = await create_session(self._spring, mode, language, order_type) # await이므로 이 작업을 기다린 후 다음 return 시작

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
            request_id: Optional[str] = None,
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
        with log_step("save_user_message", request_id=request_id, session_id=session_id):
            await save_message(self._spring, session_id, "USER", text)

        # session_id와 messages, nunchi_signal만 넘긴다.
        # order_id / payment_id / intent 등은 그래프 노드가 관리하며
        # 매 요청마다 None으로 덮어쓰면 이전 턴에서 저장된 값이 초기화된다.

        # 랭그래프에 넘겨주는 초기 입력값
        initial_state = {
            "messages":      [HumanMessage(content=text)],
            "session_id":    session_id,
            "mode":          mode.upper(),
            "nunchi_signal": nunchi_signal,
            "request_id":    request_id,
        }

        # ainvoke는 그래프를 실행시키는 함수
        with log_step("langgraph_invoke", request_id=request_id, session_id=session_id):
            result = await self._graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": str(session_id)}},
            )

        messages = result.get("messages") or []
        if not messages:
            raise RuntimeError("그래프 실행 결과에 메시지가 없습니다")
        raw = _normalize_content(messages[-1].content)

        # JSON 응답 파싱 (추천 / 옵션 / 퀵바 suggestions / 화면 액션)
        reply, recommendations, menu_options, suggestions, parsed_action = _parse_agent_reply(raw)
        # menu_options 보강/필터링: 누락 시 tool 결과로 복원, 담기 완료 시 선택 옵션만 표시
        menu_options = _apply_menu_options_from_messages(menu_options, messages, reply)
        current_step = result.get("current_step")
        # 노드가 명시적으로 채운 action 우선, 없으면 LLM 응답 JSON 의 action 사용
        action = result.get("action") or parsed_action

        # 3. AI 응답 저장
        with log_step("save_assistant_message", request_id=request_id, session_id=session_id):
            await save_message(self._spring, session_id, "ASSISTANT", reply)

        response = ChatOrderResponse(
            session_id=session_id,
            reply=reply,
            current_step=current_step,
            recommendations=recommendations,
            menu_options=menu_options,
            suggestions=suggestions,
            action=action,
        )

        # 4. suggestions가 있으면 백그라운드 프리패치 스케줄링
        if suggestions:
            self._schedule_prefetch(session_id, suggestions, mode)

        return response

    async def handle_chat_stream(
        self,
        session_id: int,
        text: str,
        nunchi_signal: Optional[str] = None,
        mode: str = "AVATAR",
        request_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """SSE 스트리밍 핸들러.

        LangGraph astream_events()로 LLM 토큰을 즉시 전송하고,
        그래프 완료 후 recommendations / action 등 전체 파싱 결과를 done 이벤트로 전송한다.

        이벤트 포맷:
          data: {"type": "token", "text": "안녕"}      ← 말풍선 실시간 업데이트
          data: {"type": "done",  "reply": "...", ...}  ← 전체 응답 (recommendations 등 포함)
          data: {"type": "error", "message": "..."}     ← 오류 발생 시
        """
        # 프리패치 캐시 히트 → reply를 토큰으로 스트리밍 후 done 이벤트
        cached = get_prefetch_cache().get(session_id, text)
        if cached:
            logging.info("[프리패치 캐시 히트 SSE] session=%d text=%r", session_id, text)
            await save_message(self._spring, session_id, "USER", text)
            await save_message(self._spring, session_id, "ASSISTANT", cached.reply)
            for ch in cached.reply:
                yield f"data: {json.dumps({'type': 'token', 'text': ch}, ensure_ascii=False)}\n\n"
            done = {
                "type": "done",
                "reply": cached.reply,
                "recommendations": [r.model_dump() for r in cached.recommendations] if cached.recommendations else None,
                "menu_options": cached.menu_options.model_dump() if cached.menu_options else None,
                "suggestions": cached.suggestions,
                "action": cached.action,
                "current_step": cached.current_step,
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
            return

        await save_message(self._spring, session_id, "USER", text)

        initial_state = {
            "messages":      [HumanMessage(content=text)],
            "session_id":    session_id,
            "mode":          mode.upper(),
            "nunchi_signal": nunchi_signal,
            "request_id": request_id,
        }
        config = {"configurable": {"thread_id": str(session_id)}}
        extractor = _MessageExtractor()

        graph_error = False
        try:
            async for event in self._graph.astream_events(initial_state, config=config, version="v2"):
                if event["event"] != "on_chat_model_stream":
                    continue
                node = event.get("metadata", {}).get("langgraph_node", "")
                if node not in _STREAMING_NODES:
                    continue
                chunk = event["data"]["chunk"]
                # tool_call 중간 단계(content 없음)는 건너뜀
                if not isinstance(chunk.content, str) or not chunk.content:
                    continue
                extracted = extractor.feed(chunk.content)
                if extracted:
                    yield f"data: {json.dumps({'type': 'token', 'text': extracted}, ensure_ascii=False)}\n\n"

        except Exception as exc:
            logging.warning("[SSE 스트림 오류] session=%d err=%s", session_id, exc)
            graph_error = True

        # 그래프 완료 후 MemorySaver에서 최종 상태 조회
        final_state = await self._graph.aget_state(config)
        messages = final_state.values.get("messages", [])
        raw = _normalize_content(messages[-1].content) if messages else ""

        reply, recommendations, menu_options, suggestions, parsed_action = _parse_agent_reply(raw)
        current_step = final_state.values.get("current_step")
        action = final_state.values.get("action") or parsed_action

        # ASSISTANT 메시지 저장 — 그래프 오류 여부와 무관하게 항상 시도
        try:
            await save_message(self._spring, session_id, "ASSISTANT", reply)
        except Exception as exc:
            logging.warning("[ASSISTANT 메시지 저장 실패] session=%d err=%s", session_id, exc)

        if graph_error:
            yield f"data: {json.dumps({'type': 'error', 'message': '죄송해요, 다시 한 번 말씀해 주시겠어요?'}, ensure_ascii=False)}\n\n"
            return

        if suggestions:
            self._schedule_prefetch(session_id, suggestions, mode)

        done_payload = {
            "type": "done",
            "reply": reply,
            "recommendations": [r.model_dump() for r in recommendations] if recommendations else None,
            "menu_options": menu_options.model_dump() if menu_options else None,
            "suggestions": suggestions,
            "action": action,
            "current_step": current_step,
        }
        yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    def _schedule_prefetch(self, session_id: int, suggestions: list[str], mode: str) -> None:
        """suggestions 중 프리패치 적합한 것만 백그라운드 태스크로 실행한다.

        실시간 상태에 의존하는 항목(장바구니·결제·주문 변경)은 캐싱해도 stale해지므로 건너뛴다.
        """
        # suggest를 하나씩 돌면서
        for text in suggestions:
            if _is_prefetchable(text): # 프리패치 해도 되는 것만
                asyncio.create_task( # 백그라운드 태스크로 던지기
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

            # 그래프에 넘길 초기 상태
            initial_state = {
                "messages":      [HumanMessage(content=text)],
                "session_id":    session_id,
                "mode":          mode.upper(),
                "nunchi_signal": None,
            }

            # 프리패치 전용 그래프 실행
            result = await self._prefetch_graph.ainvoke(initial_state)

            messages = result.get("messages") or []
            if not messages:
                return

            raw = _normalize_content(messages[-1].content)
            # 결과 파싱
            reply, recommendations, menu_options, suggestions, parsed_action = _parse_agent_reply(raw)
            current_step = result.get("current_step")
            action = result.get("action") or parsed_action

            response = ChatOrderResponse(
                session_id=session_id,
                reply=reply,
                current_step=current_step,
                recommendations=recommendations,
                menu_options=menu_options,
                suggestions=suggestions,
                action=action,
            )

            # 캐시에 저장
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


def _parse_mcp_tool_content(content) -> dict | None:
    """MCP ToolMessage content (str or list) → dict. 실패 시 None."""
    try:
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in content
            )
        return json.loads(content) if isinstance(content, str) else None
    except Exception:
        return None


def _apply_menu_options_from_messages(
    menu_options: Optional["MenuOptionsResponse"],
    messages: list,
    reply: str,
) -> Optional["MenuOptionsResponse"]:
    """menu_options를 tool 결과 기반으로 보강하거나 필터링한다.

    1. 담기 완료 턴: add_cart_item이 호출됐으면 선택된 option_ids만 남긴다.
    2. 옵션 표시 턴: menu_options가 null이면 menu_detail에서 복원한다.
    """
    from domain.order_request import MenuOptionGroup, MenuOptionItem, MenuOptionsResponse

    last_human_idx = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1
    )
    current_turn = messages[last_human_idx + 1:]

    cart_add_happened = False
    selected_option_ids: list[int] = []

    for msg in current_turn:
        if isinstance(msg, ToolMessage):
            data = _parse_mcp_tool_content(msg.content)
            if data and ("item_id" in data or "cart_id" in data or "items" in data):
                cart_add_happened = True
        elif isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []):
                tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if "add_cart_item" in tc_name:
                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    selected_option_ids = tc_args.get("option_ids", [])

    # 담기 완료 턴: 선택된 옵션만 표시하거나 menu_options 그대로 반환
    if cart_add_happened:
        # menu_detail에서 선택된 옵션만 추려 빌드
        menu_detail: dict | None = None
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                data = _parse_mcp_tool_content(msg.content)
                if data and "option_groups" in data and data["option_groups"]:
                    menu_detail = data
                    break

        if menu_detail and selected_option_ids:
            try:
                filtered_groups = []
                for g in menu_detail.get("option_groups", []):
                    picked = [o for o in g["options"] if o["option_id"] in selected_option_ids]
                    if picked:
                        filtered_groups.append(MenuOptionGroup(
                            group_id=g["group_id"],
                            group_name=g["group_name"],
                            is_required=g.get("is_required", False),
                            max_select=g.get("max_select", 1),
                            options=[MenuOptionItem(**o) for o in picked],
                        ))
                if filtered_groups:
                    return MenuOptionsResponse(
                        menu_id=menu_detail["menu_id"],
                        menu_name=menu_detail.get("name", ""),
                        option_groups=filtered_groups,
                    )
            except Exception:
                pass
        return menu_options  # None 또는 LLM이 이미 채운 값

    # menu_options가 이미 있으면 그대로 반환 (옵션 표시 턴)
    if menu_options is not None:
        return menu_options

    # menu_options 누락 → 전체 메시지에서 최근 menu_detail로 복원
    menu_detail_for_restore: dict | None = None
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            data = _parse_mcp_tool_content(msg.content)
            if data and "option_groups" in data and data["option_groups"]:
                menu_detail_for_restore = data
                break

    if menu_detail_for_restore is None:
        return None

    option_groups_raw = menu_detail_for_restore.get("option_groups", [])
    if not option_groups_raw:
        return None

    try:
        return MenuOptionsResponse(
            menu_id=menu_detail_for_restore["menu_id"],
            menu_name=menu_detail_for_restore.get("name", ""),
            option_groups=[
                MenuOptionGroup(
                    group_id=g["group_id"],
                    group_name=g["group_name"],
                    is_required=g.get("is_required", False),
                    max_select=g.get("max_select", 1),
                    options=[MenuOptionItem(**o) for o in g["options"]],
                )
                for g in option_groups_raw
            ],
        )
    except Exception:
        return None


def _normalize_content(content) -> str:
    """LLM 응답 content를 str로 정규화한다.

    Gemini는 list[dict] 형태로, OpenAI는 str 형태로 반환한다.
    """
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content or ""


def _strip_markdown(text: str) -> str:
    """마크다운 서식을 제거하고 순수 텍스트를 반환한다."""
    text = re.sub(r'```(?:\w+)?\n?(.*?)```', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'___(.+?)___', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'__(.+?)__', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_(.+?)_', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


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
) -> tuple[
    str,
    Optional[list[RecommendedMenu]],
    Optional[MenuOptionsResponse],
    Optional[list[str]],
    Optional[dict],
]:
    """에이전트 JSON 응답을 파싱한다.

    지원 키:
    - recommendations → 추천 메뉴 카드 목록
    - menu_options     → 옵션 선택 구조화 응답
    - suggestions      → 퀵바 다음 발화 추천 문구 목록
    - action           → 프론트가 받아 화면을 컨트롤하는 단일 명령
                         (navigate / select_floor / highlight_menu /
                          open_menu_detail / close_overlay /
                          select_payment_method / select_restaurant)
    JSON 블록이 없거나 지원 키가 없으면 원본 텍스트를 그대로 반환한다.
    """
    from service.graph.ui_actions import validate as validate_action

    try:
        json_str = _extract_json_block(raw)
        if json_str is None:
            return _strip_markdown(raw), None, None, None, None
        data = json.loads(json_str)

        # JSON 파싱 성공 시 raw(전체 JSON 문자열)로 폴백하면 recommendations 등이 reply에 노출됨
        # message가 비어있으면 기본 안내 문구로 대체 (최후 방어선)
        reply = _strip_markdown(data.get("reply") or data.get("message") or "") or "죄송해요, 다시 한 번 말씀해 주시겠어요?"
        recommendations: Optional[list[RecommendedMenu]] = None
        menu_options: Optional[MenuOptionsResponse] = None
        suggestions: Optional[list[str]] = None
        action: Optional[dict] = None

        # 값이 null 이면 키가 있어도 건너뛴다 (null 순회/인덱싱 시 예외 → 원본 JSON 노출 버그 방지)
        if data.get("recommendations"):
            recommendations = [RecommendedMenu(**item) for item in data["recommendations"]]

        if data.get("menu_options"):
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

        # action 검증 — 잘못된 타입/페이로드는 None 으로 폐기 (서비스 흐름 안전)
        if data.get("action"):
            action = validate_action(data["action"])

        return reply, recommendations, menu_options, suggestions, action
    except Exception:
        logging.debug("[에이전트 응답 파싱 스킵] JSON 아님 — 원본 텍스트 반환")
        return _strip_markdown(raw), None, None, None, None
