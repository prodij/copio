from functools import lru_cache

from pydantic import field_validator
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
