from __future__ import annotations

import logging

from adapter.spring_adapter import SpringAdapter
from domain.conversation import ConversationMessage
from domain.session import SessionMode, SessionResult


async def create_session(
    spring: SpringAdapter,
    mode: SessionMode = SessionMode.avatar,
    language: str = "ko",
) -> SessionResult:
    """주문 세션 시작 — POST /api/sessions"""
    data = await spring.post("/api/sessions", {"mode": mode.value, "language": language})
    try:
        return SessionResult.model_validate(data)
    except Exception as exc:
        logging.error(f"[세션 생성 파싱 오류] data={data} | {exc}")
        raise


async def save_message(
    spring: SpringAdapter,
    session_id: int,
    role: str,
    text: str,
) -> None:
    """대화 메시지 저장 — POST /api/sessions/{sessionId}/messages"""
    await spring.post(
        f"/api/sessions/{session_id}/messages",
        {"role": role, "text": text},
    )


async def save_tool_log(
    spring: SpringAdapter,
    session_id: int,
    tool_name: str,
    request: str,
    response: str,
) -> None:
    """AI 툴 호출 로그 저장 — POST /api/sessions/{sessionId}/tool-logs"""
    try:
        await spring.post(
            f"/api/sessions/{session_id}/tool-logs",
            {"toolName": tool_name, "request": request, "response": response},
        )
    except Exception as exc:
        logging.warning(f"[툴 로그 저장 실패] tool={tool_name} session={session_id} | {exc}")


async def complete_session(spring: SpringAdapter, session_id: int) -> dict:
    """주문 세션 종료 — PATCH /api/sessions/{sessionId}/complete"""
    logging.warning(f"[세션 종료 호출] session_id={session_id}")
    result = await spring.patch(f"/api/sessions/{session_id}/complete")
    logging.warning(f"[세션 종료 완료] result={result}")
    return result


async def update_step(spring: SpringAdapter, session_id: int, step: str) -> dict:
    """주문 단계 업데이트 — PATCH /api/sessions/{sessionId}/step"""
    return await spring.patch(f"/api/sessions/{session_id}/step", {"step": step})


async def get_messages(spring: SpringAdapter, session_id: int, limit: int = 100) -> list[ConversationMessage]:
    """대화 이력 조회 — GET /api/sessions/{sessionId}/messages"""
    data = await spring.get(f"/api/sessions/{session_id}/messages", params={"limit": limit})
    try:
        return [ConversationMessage.model_validate(item) for item in data]
    except Exception as exc:
        logging.error(f"[대화 이력 파싱 오류] session_id={session_id} | {exc}")
        raise
