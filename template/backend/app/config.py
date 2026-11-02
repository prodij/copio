from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BillingModeSettings(BaseSettings):
    """What decides mock payment: server config only, no request can change it. create_app checks this
    when the process starts, so an unsafe mix stops the backend instead of faking payments."""

    # Hide inputs: pydantic's message otherwise prints them, and the logs would get part of the Stripe key.
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    # Empty is real billing. `mock` is mock payment: only with APP_ENV=local and no Stripe key.
    billing_mode: str = ""
    app_env: str = ""
    # Empty means billing isn't set up: the product works, checkout says so, paid features stay off.
    stripe_secret_key: str = ""

    @model_validator(mode="after")
    def mock_payment_only_when_safe(self) -> "BillingModeSettings":
        mode = self.billing_mode.strip()
        if mode not in ("", "mock"):
            raise ValueError(f"BILLING_MODE must be empty or mock, not {mode!r}")
        if mode == "mock" and self.app_env.strip() != "local":
            raise ValueError("BILLING_MODE=mock (mock payment) is refused: it needs APP_ENV=local")
        if mode == "mock" and self.stripe_secret_key.strip():
            raise ValueError("BILLING_MODE=mock (mock payment) is refused: STRIPE_SECRET_KEY is set; use one or the other")
        return self

    @property
    def mock_payment(self) -> bool:
        return self.billing_mode.strip() == "mock"


class Settings(BillingModeSettings):
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

    @field_validator("stripe_secret_key")
    @classmethod
    def test_mode_only(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith("sk_test_"):
            raise ValueError("Stripe must run in test-mode (sk_test_...) in milestone 1")
        return value

    @property
    def stripe_configured(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def billing_configured(self) -> bool:
        return self.stripe_configured or self.mock_payment

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
