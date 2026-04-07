import httpx

from adapter.ports import SpringPort
from core.config import Settings
from core.exceptions import SpringApiError, SpringApiTimeoutError


class SpringAdapter(SpringPort):
    """Spring 백엔드 HTTP 연동"""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.spring_base_url
        self._timeout = settings.spring_timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )

    def _parse(self, response: httpx.Response) -> dict:
        """Spring 공통 응답 { code, msg, data } 파싱"""
        try:
            body = response.json()
        except Exception:
            raise SpringApiError("Spring 응답을 파싱할 수 없습니다", response.status_code)

        code = body.get("code")
        if code not in (200, 201):
            raise SpringApiError(
                message=body.get("msg", "Spring API 오류"),
                status_code=code or response.status_code,
            )

        return body.get("data") or {}

    async def get(self, path: str, params: dict | None = None) -> dict:
        try:
            async with self._client() as client:
                response = await client.get(path, params=params)
                return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError()

    async def post(self, path: str, body: dict | None = None) -> dict:
        try:
            async with self._client() as client:
                response = await client.post(path, json=body)
                return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError()

    async def put(self, path: str, body: dict) -> dict:
        try:
            async with self._client() as client:
                response = await client.put(path, json=body)
                return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError()

    async def patch(self, path: str, body: dict | None = None) -> dict:
        try:
            async with self._client() as client:
                response = await client.patch(path, json=body)
                return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError()

    async def delete(self, path: str) -> dict:
        try:
            async with self._client() as client:
                response = await client.delete(path)
                return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError()
