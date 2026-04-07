from adapter.spring_adapter import SpringAdapter
from domain.session import SessionResult


async def create_session(spring: SpringAdapter, mode: str = "AVATAR", language: str = "ko") -> SessionResult:
    """주문 세션 시작 — POST /api/sessions

    Args:
        mode: NORMAL(터치 주문) 또는 AVATAR(아바타 음성 대화)
        language: 언어 코드 (ko, en 등)

    Returns:
        SessionResult (session_id 포함 — 이후 모든 Tool에 전달 필요)
    """
    data = await spring.post("/api/sessions", {"mode": mode, "language": language})
    return SessionResult(**data)


async def complete_session(spring: SpringAdapter, session_id: int) -> dict:
    """주문 세션 종료 — PATCH /api/sessions/{sessionId}/complete"""
    return await spring.patch(f"/api/sessions/{session_id}/complete")
