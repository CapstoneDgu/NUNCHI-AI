from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class SpringPort(ABC):
    """Spring 백엔드 연동 인터페이스"""

    @abstractmethod
    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        ...

    @abstractmethod
    async def post(self, path: str, body: Optional[dict] = None) -> dict:
        ...

    @abstractmethod
    async def put(self, path: str, body: dict) -> dict:
        ...

    @abstractmethod
    async def patch(self, path: str, body: Optional[dict] = None) -> dict:
        ...

    @abstractmethod
    async def delete(self, path: str) -> dict:
        ...
