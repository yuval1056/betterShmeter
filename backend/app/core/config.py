from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM proxy connection. PROXY_API_KEY may be absent -- see chat_service's
    # simulated-reply fallback.
    PROXY_API_KEY: str | None = None
    PROXY_BASE_URL: str = ""
    PROXY_MODEL_NAME: str = ""

    # GitHub integration used by the git-mode tool calls.
    GITHUB_PERSONAL_ACCESS_TOKEN: str = ""
    GITHUB_OWNER: str = ""
    GITHUB_REPO: str = ""

    # Comma-separated list of allowed frontend origins.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Code-default settings -- not required in .env.
    DB_PATH: str = "data/shmeter.db"
    GITHUB_DB_PATH: str = "data/github.db"
    HISTORY_LIMIT: int = 10
    API_PREFIX: str = "/api"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
