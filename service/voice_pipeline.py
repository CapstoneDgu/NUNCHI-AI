"""VoicePipeline — STT → Agent → TTS 파이프라인 (골격)

역할:
  - 오디오 바이트를 받아 STT로 텍스트 변환
  - 텍스트를 AgentService에 전달해 응답 생성
  - 응답 텍스트를 TTS로 음성으로 변환해 반환
"""

from adapter.openai_adapter import OpenAIAdapter
from service.agent_service import AgentService


class VoicePipeline:
    def __init__(self, openai: OpenAIAdapter, agent: AgentService) -> None:
        self._openai = openai
        self._agent = agent

    async def process(self, audio_bytes: bytes) -> bytes:
        """오디오 입력 → 음성 응답 출력"""
        raise NotImplementedError
