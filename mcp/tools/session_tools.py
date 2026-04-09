from __future__ import annotations

import logging

from adapter.spring_adapter import SpringAdapter
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


async def complete_session(spring: SpringAdapter, session_id: int) -> dict:
    """주문 세션 종료 — PATCH /api/sessions/{sessionId}/complete"""
    logging.warning(f"[세션 종료 호출] session_id={session_id}")
    result = await spring.patch(f"/api/sessions/{session_id}/complete")
    logging.warning(f"[세션 종료 완료] result={result}")
    return result
