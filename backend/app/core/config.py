from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    redis_url: str
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket: str
    s3_region: str = "us-east-1"
    presigned_upload_seconds: int = Field(default=900, ge=1)
    presigned_download_seconds: int = Field(default=300, ge=1)
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    anthropic_api_key: SecretStr | None = None
    deepgram_api_key: SecretStr | None = None
    transcription_provider: str = "deepgram"
    email_provider: str = "console"
    public_base_url: str = "http://localhost:8000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str = "reports@homean.com"
    smtp_from_name: str = "Homean"
    smtp_use_tls: bool = True
    email_pending_lease_seconds: int = Field(default=900, ge=1)
    app_env: str = "dev"
    dashboard_origin: str = "http://localhost:3000"
    auth_rate_limit: int = Field(default=100, ge=1)
    public_share_rate_limit: int = Field(default=120, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    rate_limit_key_prefix: str = "homean"
    sentry_dsn: str | None = None
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_solo_monthly_price_id: str | None = None
    stripe_api_base_url: str = "https://api.stripe.com/v1"
    # Days to keep captured media objects. 0 disables purging entirely, which
    # is the default: evidence wants long retention and privacy law wants
    # minimisation, and that number is a policy decision, not a code one.
    media_retention_days: int = Field(default=0, ge=0)
    anthropic_input_cost_per_million: float = Field(default=0.0, ge=0)
    anthropic_output_cost_per_million: float = Field(default=0.0, ge=0)

    @field_validator("presigned_upload_seconds", "presigned_download_seconds")
    @classmethod
    def cap_presigned_ttl(cls, value: int) -> int:
        return min(value, 900)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
