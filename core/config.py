from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Spring 백엔드
    spring_base_url: str = "http://localhost:8080"
    spring_timeout: int = Field(default=5, ge=1)  # 최소 1초 이상

    # Gemini
    gemini_api_key: str = Field(min_length=1)  # 빈 문자열 거부
    gemini_model: str = "gemini-2.0-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
