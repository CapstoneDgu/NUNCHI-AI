"""LLM 팩토리

LLM_PROVIDER 설정값에 따라 OpenAI 또는 Gemini LLM 객체를 반환한다.
.env의 LLM_PROVIDER=openai|gemini 한 줄만 바꾸면 전체 노드가 전환된다.
"""

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from core.config import get_settings
from core.model_context import get_current_model


def build_llm(temperature: float = 0, streaming: bool = False) -> BaseChatModel:
    """현재 LLM_PROVIDER에 맞는 LLM 객체를 반환한다.

    prefetch 태스크 안에서 set_model_override()가 호출된 경우
    get_current_model()이 해당 모델명을 우선 반환한다.
    """
    s = get_settings()

    if s.llm_provider == "gemini":
        model = get_current_model(s.gemini_model)
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=s.gemini_api_key,
            temperature=temperature,
            streaming=streaming,
        )

    model = get_current_model(s.openai_model)
    return ChatOpenAI(
        model=model,
        api_key=s.openai_api_key,
        temperature=temperature,
        streaming=streaming,
    )
