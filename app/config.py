from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Google Sheets
    google_sheets_credentials_json: str = "./credentials.json"
    google_sheets_url: str = ""
    google_sheets_parent_tab: str = "Parents"
    google_sheets_student_tab: str = "Students"
    google_sheets_audit_tab: str = "AuditLog"
    google_sheets_review_tab: str = "HumanReview"

    # Vapi
    vapi_api_key: str = ""
    vapi_mock_mode: bool = True

    # WhatsApp
    whatsapp_api_key: str = ""
    whatsapp_from_number: str = "whatsapp:+14155238886"
    whatsapp_mock_mode: bool = True

    # Telegram
    telegram_bot_token: str = ""
    telegram_mock_mode: bool = True

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    quiet_hours_start: int = 21
    quiet_hours_end: int = 8
    confidence_threshold: float = 0.75
    max_retry_attempts: int = 3
    retry_backoff_base: int = 2
    session_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("confidence_threshold")
    @classmethod
    def _check_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        return v

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def _check_hours(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError("quiet hours must be between 0 and 23")
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
