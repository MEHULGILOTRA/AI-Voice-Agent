from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
