"""AgentService — LLM Tool 실행 흐름 (골격)

역할:
  - OpenAI Chat API에 메시지와 Tool 스키마를 전달
  - LLM이 Tool 호출을 요청하면 해당 MCP Tool 함수를 실행
  - 결과를 다시 LLM에 전달하는 루프를 반복
  - 최종 텍스트 응답을 반환
"""

from adapter.openai_adapter import OpenAIAdapter
from adapter.spring_adapter import SpringAdapter


class AgentService:
    def __init__(self, openai: OpenAIAdapter, spring: SpringAdapter) -> None:
        self._openai = openai
        self._spring = spring

    async def run(self, messages: list[dict]) -> str:
        """LLM + MCP Tool 체이닝 실행"""
        raise NotImplementedError
