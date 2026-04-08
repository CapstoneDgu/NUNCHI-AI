from functools import lru_cache

from adapter.openai_adapter import OpenAIAdapter
from adapter.spring_adapter import SpringAdapter
from core.config import get_settings


@lru_cache
def get_spring_adapter() -> SpringAdapter:
    return SpringAdapter(get_settings())


@lru_cache
def get_openai_adapter() -> OpenAIAdapter:
    return OpenAIAdapter(get_settings())
