from __future__ import annotations

from typing import Optional

from core.config import Settings


class OpenAIAdapter:
    """OpenAI API 연동 (STT / LLM / TTS)"""

    def __init__(self, settings: Settings) -> None:
        pass  # STT/TTS 연동 시 구현 예정

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Whisper STT — 오디오 → 텍스트"""
        raise NotImplementedError

    async def chat(self, messages: list, tools: Optional[list] = None) -> dict:
        """GPT Chat — 메시지 + Tool 스키마 → 응답"""
        raise NotImplementedError

    async def speak(self, text: str) -> bytes:
        """TTS — 텍스트 → 오디오 바이트"""
        raise NotImplementedError
