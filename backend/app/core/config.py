"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe, validated configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────
    # Default: SQLite (zero-config). Override with PostgreSQL URL for production:
    #   postgresql+asyncpg://user:pass@localhost:5432/idp_db
    DATABASE_URL: str = "sqlite+aiosqlite:///./idp_dev.db"

    # ── CORS ─────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:5173"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    # ── JWT Authentication ─────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Google OAuth ───────────────────────────────────────
    # Required for Google Sign-In server-side ID token verification.
    # Obtain from: Google Cloud Console → APIs & Services → Credentials
    GOOGLE_CLIENT_ID: str = ""

    # ── Google Gemini API ──────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── GitHub MCP Server ──────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_ORG: str = "academic-idp"

    # ── Kubernetes MCP Server ──────────────────────────────
    KUBECONFIG: str = ""

    # ── ArgoCD MCP Server ──────────────────────────────────
    ARGOCD_URL: str = ""
    ARGOCD_TOKEN: str = ""

    # ── MCP Configuration ──────────────────────────────────
    MCP_CONFIG_PATH: str = "../mcp_config.json"

    # ── IaC & CI/CD MCP Paths ──────────────────────────────
    IAC_DIR: str = "/app/iac"
    WORKFLOWS_DIR: str = "/app/.github/workflows"

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "Academic IDP"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
