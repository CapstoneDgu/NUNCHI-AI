# MCP 서버 설정 분리 계획

## 왜 고쳐야 하나

지금 MCP 서버(`kiosk_mcp/mcp_server.py`)는 FastAPI 서버와 **같은 `Settings` 클래스**를 공유한다.

```python
# core/config.py
class Settings(BaseSettings):
    spring_base_url: str = ...
    openai_api_key: str = Field(min_length=1, alias="OPEN_API_KEY")  # 필수
    openai_model: str = ...
    mcp_server_url: str = ...
```

MCP 서버는 Spring API만 호출하고 OpenAI를 전혀 쓰지 않는데,
`Settings`에 `openai_api_key`가 필수 필드로 박혀 있어서
**OpenAI 키 없이는 MCP 서버 자체가 기동 불가**한 상태다.

그래서 Claude Desktop config에 억지로 OpenAI 키를 넣고 있다.
→ 불필요한 민감정보 노출, 논리적으로도 맞지 않음.

---

## 고칠 내용

### 1. `core/config.py` — McpSettings 클래스 추가

```python
class McpSettings(BaseSettings):
    spring_base_url: str = "http://localhost:8080"
    spring_timeout: int = Field(default=5, ge=1)

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()
```

### 2. `kiosk_mcp/mcp_server.py` — get_settings → get_mcp_settings로 교체

```python
# 변경 전
from core.config import get_settings
_settings = get_settings()

# 변경 후
from core.config import get_mcp_settings
_settings = get_mcp_settings()
```

### 3. Claude Desktop config — OPEN_API_KEY 줄 제거

```json
"nunchi-kiosk": {
  "command": "/Users/hyodongg/Desktop/workspace/capstone_ai/venv/bin/python",
  "args": ["-m", "kiosk_mcp.mcp_server"],
  "cwd": "/Users/hyodongg/Desktop/workspace/capstone_ai",
  "env": {
    "MCP_TRANSPORT": "stdio",
    "PYTHONPATH": "/Users/hyodongg/Desktop/workspace/capstone_ai",
    "SPRING_BASE_URL": "http://localhost:8080"
  }
}
```

---

## 변경 범위 요약

| 파일 | 변경 내용 |
|------|-----------|
| `core/config.py` | `McpSettings` 클래스 추가, `get_mcp_settings()` 함수 추가 |
| `kiosk_mcp/mcp_server.py` | `get_settings()` → `get_mcp_settings()` 교체 |
| `claude_desktop_config.json` | `OPEN_API_KEY` 항목 제거 |
