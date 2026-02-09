from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://autoflow:autoflow@localhost:5432/autoflow"
    redis_url: str = "redis://localhost:6379"
    google_api_key: str = ""
    gemini_api_key: str = ""  # Alternative to google_api_key
    
    @model_validator(mode='after')
    def set_google_api_key_from_gemini(self):
        # If google_api_key is not set but gemini_api_key is, use gemini_api_key
        if not self.google_api_key and self.gemini_api_key:
            self.google_api_key = self.gemini_api_key
        return self

    # Auth settings
    secret_key: str = "change-this-secret-key-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # LLM settings
    default_llm_provider: str = "gemini"  # gemini, openai, anthropic
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Browser-Use Agent settings
    browser_use_llm_provider: str = "gemini"  # gemini, openai, anthropic
    browser_use_model: str = ""  # Leave empty to use provider's default model
    browser_use_headless: bool = True
    browser_use_timeout: int = 30000  # Page load timeout in ms
    browser_use_screenshot_quality: int = 80  # JPEG quality 1-100

    # Self-healing settings
    healing_enabled: bool = True
    healing_auto_approve_threshold: float = 0.85  # Auto-approve if confidence >= this
    healing_mode: str = "inline"  # inline (during run) or batch (after run) or both

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
