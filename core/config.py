from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _SpringBaseSettings(BaseSettings):
    """Spring 연동에 필요한 공통 설정."""
    spring_base_url: str = "http://localhost:8080"
    spring_timeout: int = Field(default=5, ge=1)

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),  # 로컬 우선, 배포는 .env
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


class Settings(_SpringBaseSettings):
    # OpenAI
    openai_api_key: str = Field(min_length=1, alias="OPEN_API_KEY")
    openai_model: str = "gpt-4o-mini"

    # MCP 서버
    mcp_server_url: str = "http://localhost:8090"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class McpSettings(_SpringBaseSettings):
    """MCP 서버 전용 설정 — OpenAI 키 불필요."""


@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()
