from abc import ABC, abstractmethod


class SpringPort(ABC):
    """Spring 백엔드 연동 인터페이스"""

    @abstractmethod
    async def get(self, path: str, params: dict | None = None) -> dict:
        ...

    @abstractmethod
    async def post(self, path: str, body: dict | None = None) -> dict:
        ...

    @abstractmethod
    async def put(self, path: str, body: dict) -> dict:
        ...

    @abstractmethod
    async def patch(self, path: str, body: dict | None = None) -> dict:
        ...

    @abstractmethod
    async def delete(self, path: str) -> dict:
        ...
