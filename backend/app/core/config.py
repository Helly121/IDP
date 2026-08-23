"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe, validated configuration.
"""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────
    # Default: SQLite (zero-config). Override with PostgreSQL URL for production:
    #   postgresql+asyncpg://user:pass@localhost:5432/idp_db
    DATABASE_URL: str = "sqlite+aiosqlite:///./idp_dev.db"

    # ── CORS ──────────────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:5173"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    # ── JWT Authentication ────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Google Gemini API ─────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── App ───────────────────────────────────────────────────────
    APP_NAME: str = "Academic IDP"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
