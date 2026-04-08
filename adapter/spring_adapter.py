import json

import httpx

from adapter.ports import SpringPort
from core.config import Settings
from core.exceptions import SpringApiError, SpringApiTimeoutError


class SpringAdapter(SpringPort):
    """Spring 백엔드 HTTP 연동"""

    def __init__(self, settings: Settings) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.spring_base_url,
            timeout=settings.spring_timeout,
        )

    async def close(self) -> None:
        """공유 클라이언트 종료 — 앱 lifespan 종료 시 호출"""
        await self._client.aclose()

    def _parse(self, response: httpx.Response) -> dict:
        """Spring 공통 응답 { code, msg, data } 파싱"""
        try:
            body = response.json()
        except json.JSONDecodeError as err:
            raise SpringApiError("Spring 응답을 파싱할 수 없습니다", response.status_code) from err

        code = body.get("code")
        if code not in (200, 201):
            raise SpringApiError(
                message=body.get("msg", "Spring API 오류"),
                status_code=code or response.status_code,
            )

        return body.get("data") or {}

    async def get(self, path: str, params: dict | None = None) -> dict:
        try:
            response = await self._client.get(path, params=params)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None

    async def post(self, path: str, body: dict | None = None) -> dict:
        try:
            response = await self._client.post(path, json=body)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None

    async def put(self, path: str, body: dict) -> dict:
        try:
            response = await self._client.put(path, json=body)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None

    async def patch(self, path: str, body: dict | None = None) -> dict:
        try:
            response = await self._client.patch(path, json=body)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None

    async def delete(self, path: str) -> dict:
        try:
            response = await self._client.delete(path)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None
