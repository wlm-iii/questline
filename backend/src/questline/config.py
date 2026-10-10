from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

LOCAL_API_TOKEN = "local-development-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("postgresql://questline:questline@localhost:5432/questline")
    api_token: SecretStr = SecretStr(LOCAL_API_TOKEN)
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    planner_provider: Literal["fake", "gemini"] = "fake"
    maps_provider: Literal["fake", "google"] = "fake"
    gemini_model: str | None = None
    run_worker_in_process: bool = False
    gemini_api_key: SecretStr | None = None
    google_maps_api_key: SecretStr | None = None
    max_transcript_chars: int = Field(default=100_000, ge=1)

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr) -> SecretStr:
        url = make_url(value.get_secret_value())
        if url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("DATABASE_URL must be a PostgreSQL URI")
        return value

    @model_validator(mode="after")
    def protect_deployment(self) -> "Settings":
        token = self.api_token.get_secret_value()
        if not token:
            raise ValueError("API_TOKEN must not be empty")
        if self.app_env == "production" and (token == LOCAL_API_TOKEN or len(token) < 32):
            raise ValueError("Production requires a unique API_TOKEN of at least 32 characters")
        return self

    @property
    def sqlalchemy_url(self) -> URL:
        return (
            make_url(self.database_url.get_secret_value())
            .set(drivername="postgresql+psycopg")
            .update_query_dict({"options": "-csearch_path=questline"})
        )

    @property
    def psycopg_url(self) -> str:
        return self.sqlalchemy_url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
