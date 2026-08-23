"""
AI-powered endpoints — manifest generation and log analysis via Google Gemini.
"""

from fastapi import APIRouter

from app.schemas.deployment import (
    ManifestRequest,
    ManifestResponse,
    LogAnalyzeRequest,
    LogAnalyzeResponse,
)
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI Intelligence"])


@router.post(
    "/manifest-generate",
    response_model=ManifestResponse,
    summary="Generate Kubernetes manifests from project specs",
)
async def manifest_generate(payload: ManifestRequest):
    """
    Takes project configuration and returns optimized Kubernetes
    Deployment, Service, and Ingress YAML manifests.

    Uses Google Gemini API when configured; falls back to
    template-based generation otherwise.
    """
    return await ai_service.generate_manifests(payload)


@router.post(
    "/log-analyze",
    response_model=LogAnalyzeResponse,
    summary="Analyze Kubernetes error logs",
)
async def log_analyze(payload: LogAnalyzeRequest):
    """
    Accepts raw error logs (CrashLoopBackOff, ImagePullBackOff, OOMKilled, etc.)
    and returns a natural-language diagnosis with suggested corrective actions.

    Uses Google Gemini API when configured; falls back to
    heuristic-based analysis otherwise.
    """
    return await ai_service.analyze_logs(payload)
