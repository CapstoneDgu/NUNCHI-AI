from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """Spring에서 반환하는 대화 메시지 응답 모델"""
    messageId: int
    sessionId: int
    role: str
    text: str
    createdAt: datetime
