from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./linguaflow.db"

    secret_key: str = "change-me"
    access_token_days: int = 30
    cookie_secure: bool = False

    # Какая модель ищет слова в заметках: ollama | gemini | openai | none
    llm_provider: str = "ollama"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_api_key: str | None = None
    openai_model: str = ""

    # Часовой пояс, в котором считаются «сегодня» и серия дней подряд
    timezone: str = "Europe/Moscow"


@lru_cache
def get_settings() -> Settings:
    return Settings()
