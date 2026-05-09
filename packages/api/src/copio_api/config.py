from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    database_url: str = "postgresql+asyncpg://copio:copio_dev@localhost:5435/copio"

    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-sonnet-4-6"
    anthropic_fallback_model: str = "claude-opus-4-7"

    lwa_client_id: str = ""
    lwa_client_secret: str = ""
    lwa_refresh_token: str = ""
    spapi_region: str = "NA"
    spapi_marketplace_id: str = "ATVPDKIKX0DER"
    spapi_seller_id: str = ""

    founder_tenant_id: str = "nutragroup"
    founder_display_name: str = "James"

    inngest_dev_server_url: str = "http://localhost:8288"
    inngest_event_key: str = "copio-dev"
    inngest_signing_key: str = "copio-dev-signing-key"

    web_origin: str = "http://localhost:3030"

    cache_hit_rate_target: float = 0.80
    diagnostic_p99_latency_seconds: int = 180

    memory_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "memory")

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    return settings
