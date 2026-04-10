from __future__ import annotations

import json
import logging
from typing import Optional

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
        """Spring 공통 응답 파싱"""
        try:
            body = response.json()
        except json.JSONDecodeError as err:
            raise SpringApiError("Spring 응답을 파싱할 수 없습니다", response.status_code) from err

        logging.debug("[Spring 응답] HTTP %d | path 응답 수신", response.status_code)

        # Spring 공통 응답은 code / msg 사용
        status = body.get("code")
        if status not in (200, 201):
            raise SpringApiError(
                message=body.get("msg", "Spring API 오류"),
                status_code=status or response.status_code,
            )

        return body.get("data") or {}

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            response = await self._client.get(path, params=params)
            return self._parse(response)
        except httpx.TimeoutException:
            raise SpringApiTimeoutError() from None

    async def post(self, path: str, body: Optional[dict] = None) -> dict:
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

    async def patch(self, path: str, body: Optional[dict] = None) -> dict:
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
