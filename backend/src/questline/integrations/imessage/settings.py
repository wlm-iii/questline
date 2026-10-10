from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RelaySettings(BaseSettings):
    """Env on the relay Mac only (SPEC §15). Kept apart from the API's `.env`."""

    model_config = SettingsConfigDict(env_file=".env.relay", extra="ignore")

    questline_api_url: str
    api_token: SecretStr
    web_base_url: str
    imsg_bin: str = "imsg"
    relay_state_path: Path = Field(
        default=Path("~/.questline/imessage-relay.json"), validate_default=True
    )
    relay_flush_seconds: float = Field(default=15, gt=0)
    relay_flush_max: int = Field(default=20, ge=1, le=500)

    @field_validator("relay_state_path")
    @classmethod
    def expand_home(cls, value: Path) -> Path:
        return value.expanduser()
