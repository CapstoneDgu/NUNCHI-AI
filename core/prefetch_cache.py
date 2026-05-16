"""퀵바 프리패치 인메모리 캐시

suggestions 3개를 백그라운드에서 미리 실행한 결과를 TTL 기반으로 캐싱한다.
외부 의존 없이 프로세스 메모리만 사용하며, 서버 재시작 시 초기화된다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from domain.order_request import ChatOrderResponse


@dataclass
class _CacheEntry:
    response: "ChatOrderResponse"
    expires_at: float


class PrefetchCache:
    def __init__(self, ttl: int = 90) -> None:
        self._store: dict[tuple[int, str], _CacheEntry] = {}
        self._ttl = ttl

    def _key(self, session_id: int, text: str) -> tuple[int, str]:
        return (session_id, text.strip().lower())

    def set(self, session_id: int, text: str, response: "ChatOrderResponse") -> None:
        key = self._key(session_id, text)
        self._store[key] = _CacheEntry(response=response, expires_at=time.monotonic() + self._ttl)

    def get(self, session_id: int, text: str) -> Optional["ChatOrderResponse"]:
        key = self._key(session_id, text)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.response

    def invalidate_session(self, session_id: int) -> None:
        """세션 종료 시 해당 세션의 캐시를 전부 삭제한다."""
        keys = [k for k in self._store if k[0] == session_id]
        for key in keys:
            del self._store[key]


_instance: Optional[PrefetchCache] = None


def get_prefetch_cache() -> PrefetchCache:
    global _instance
    if _instance is None:
        _instance = PrefetchCache()
    return _instance
