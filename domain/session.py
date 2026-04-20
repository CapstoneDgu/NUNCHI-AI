from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SessionMode(str, Enum):
    normal = "NORMAL"   # 터치 기반 주문 UI
    avatar = "AVATAR"   # 아바타 화면 + 음성 대화


class SessionStatus(str, Enum):
    active = "ACTIVE"
    completed = "COMPLETED"


class SessionResult(BaseModel):
    """POST /api/sessions 응답"""

    model_config = ConfigDict(populate_by_name=True)

    session_id: int = Field(alias="sessionId")
    mode: SessionMode
    status: SessionStatus
    language: str
    created_at: datetime = Field(alias="createdAt")
