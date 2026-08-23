"""
Health check endpoint — used by Kubernetes liveness probes and monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Returns service health including database connectivity.
    """
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        pass

    status = "healthy" if db_healthy else "degraded"
    return {
        "status": status,
        "service": "academic-idp-backend",
        "database": "connected" if db_healthy else "disconnected",
    }
