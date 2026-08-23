"""
API v1 router — aggregates all endpoint routers under /api/v1.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import health, projects, ai

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(ai.router)
