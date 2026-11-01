from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    frontend_url: str
    zitadel_issuer: str
    zitadel_api_url: str
    zitadel_project_id: str
    zitadel_instance_org_id: str
    zitadel_service_token: str = ""
    # Compose mounts the PAT that `make bootstrap` wrote; read it when no token is given directly.
    zitadel_service_token_file: str | None = None
    lago_api_url: str
    lago_api_key: str
    lago_webhook_issuer: str
    lago_stripe_provider_code: str = "stripe"
    stripe_secret_key: str

    @field_validator("stripe_secret_key")
    @classmethod
    def test_mode_only(cls, value: str) -> str:
        if not value.startswith("sk_test_"):
            raise ValueError("Stripe must run in test-mode (sk_test_...) in milestone 1")
        return value

    @model_validator(mode="after")
    def token_from_file(self) -> "Settings":
        if not self.zitadel_service_token and self.zitadel_service_token_file:
            path = Path(self.zitadel_service_token_file)
            if not path.is_file():
                raise ValueError(f"zitadel_service_token_file {path} not found; run `make bootstrap`")
            self.zitadel_service_token = path.read_text().strip()
        return self


class DatabaseSettings(BaseSettings):
    """Just the database, for migrations: they must run before the rest is configured."""

    model_config = SettingsConfigDict(extra="ignore")
    database_url: str


class LagoSettings(BaseSettings):
    """Just Lago, for `python -m app.billing.sync`."""

    model_config = SettingsConfigDict(extra="ignore")
    lago_api_url: str
    lago_api_key: str


class FrontendSettings(BaseSettings):
    """Just the app origin, for CORS: error responses must stay readable while the rest is misconfigured."""

    model_config = SettingsConfigDict(extra="ignore")
    frontend_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
