"""Application configuration. All secrets come from the environment; never hard-coded."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Gumroad Automation"
    DATABASE_URL: str = "sqlite:///./gumroad_automation.db"

    SECRET_KEY: str = "change-me-to-a-long-random-string"
    TOKEN_MASTER_KEY: str = ""  # base64-encoded 32 bytes for AES-GCM token encryption

    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 30

    MAIL_MODE: str = "console"  # console | file | smtp
    MAIL_FILE_PATH: str = "./mailer.outbox.log"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@example.com"

    GUMROAD_CLIENT_ID: str = ""
    GUMROAD_CLIENT_SECRET: str = ""
    # Exact redirect URI registered in the Gumroad OAuth app. Empty means
    # "derive from the current public base URL at request time" — required
    # because the free tunnel URL rotates. The callback route is
    # /api/v1/gumroad-accounts/oauth/callback.
    GUMROAD_REDIRECT_URI: str = ""
    # OAuth endpoint paths — confirm in your Gumroad app settings if OAuth fails.
    GUMROAD_AUTHORIZE_URL: str = "https://gumroad.com/oauth/authorize"
    GUMROAD_TOKEN_URL: str = "https://gumroad.com/oauth/token"

    # APK file served to buyers after a successful license verification.
    APK_DOWNLOAD_PATH: str = ""
    # Lifetime (minutes) of a license download token issued after verification.
    LICENSE_DOWNLOAD_MINUTES: int = 30

    CORS_ORIGINS: str = "http://localhost:5173"
    PUBLIC_BASE_URL: str = ""

    SCHEDULER_ENABLED: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
