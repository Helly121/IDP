"""
API v1 router â€” aggregates all endpoint routers under /api/v1.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, projects, agent, approvals

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(agent.router)
api_router.include_router(approvals.router)

