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
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.database import init_db, close_db, async_session_factory
from app.api.v1.router import api_router

# Ensure models are imported so Base.metadata knows about them
import app.models  # noqa: F401
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


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

    # Seed demo user if it doesn't exist
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.id == DEMO_USER_ID))
        if result.scalar_one_or_none() is None:
            demo_user = User(
                id=DEMO_USER_ID,
                email="demo@academic-idp.dev",
                role=UserRole.STUDENT,
                full_name="Demo Student",
            )
            session.add(demo_user)
            await session.commit()
            logger.info("👤 Demo user seeded (demo@academic-idp.dev)")

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
