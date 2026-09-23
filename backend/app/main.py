"""
Academic IDP — FastAPI Application Entry Point

Initializes the FastAPI app with:
- CORS middleware for the React frontend
- Lifespan events for database connection management
- MCP Tool Registry initialization
- v1 API router mount
- Auto-generated OpenAPI documentation
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1.router import api_router

# Ensure models are imported so Base.metadata knows about them
import app.models  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    logger.info("🚀 Starting Academic IDP Backend v%s...", settings.APP_VERSION)
    await init_db()
    logger.info("🗄 Database tables created/verified")

    # Initialize MCP Tool Registry
    from app.mcp_servers.registry import registry
    registry.initialize(config_path=settings.MCP_CONFIG_PATH)
    status = registry.get_server_status()
    for name, info in status.items():
        logger.info(
            "🔧 MCP Server '%s': %d tools — %s",
            name,
            info["tool_count"],
            ", ".join(info["tools"]),
        )

    yield
    logger.info("🛑 Shutting down...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Self-service Internal Developer Platform for academic environments. "
        "Features an autonomous AI DevOps agent with MCP tool integration, "
        "human-in-the-loop approval gates, and SSE streaming."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
