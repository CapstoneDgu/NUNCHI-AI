"""모델 컨텍스트 — 태스크별 LLM 모델 오버라이드

asyncio 태스크는 생성 시점의 컨텍스트 복사본을 가지므로,
프리패치 태스크 안에서 set_model_override()를 호출하면
메인 대화 흐름에 영향 없이 해당 태스크에서만 다른 모델을 사용할 수 있다.
"""

from contextvars import ContextVar
from typing import Optional

_model_override: ContextVar[Optional[str]] = ContextVar("model_override", default=None)


def get_current_model(default: str) -> str:
    """현재 태스크의 모델을 반환한다. 오버라이드가 없으면 default를 사용한다."""
    return _model_override.get() or default


def set_model_override(model: str) -> None:
    """현재 태스크의 모델을 오버라이드한다."""
    _model_override.set(model)
