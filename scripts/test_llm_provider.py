"""LLM 공급자 전환 테스트

사용법:
  python scripts/test_llm_provider.py

.env의 LLM_PROVIDER 값에 따라 OpenAI 또는 Gemini로 테스트한다.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from core.config import get_settings
from core.llm_factory import build_llm


async def main():
    s = get_settings()
    print(f"[테스트] LLM_PROVIDER = {s.llm_provider}")

    if s.llm_provider == "gemini":
        print(f"[테스트] 모델 = {s.gemini_model}")
        if not s.gemini_api_key:
            print("[실패] GEMINI_API_KEY가 비어있습니다. .env를 확인하세요.")
            return
    else:
        print(f"[테스트] 모델 = {s.openai_model}")
        if not s.openai_api_key:
            print("[실패] OPEN_API_KEY가 비어있습니다. .env를 확인하세요.")
            return

    llm = build_llm(temperature=0)

    print("[테스트] LLM 호출 중...")
    response = await llm.ainvoke([HumanMessage(content="안녕하세요. 한 문장으로 자기소개 해주세요.")])

    print(f"\n[응답]\n{response.content}")
    print("\n[성공] LLM 연결 정상")


if __name__ == "__main__":
    asyncio.run(main())
