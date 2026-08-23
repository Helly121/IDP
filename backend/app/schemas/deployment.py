"""
Pydantic v2 schemas for Deployment data and AI service payloads.
"""

from pydantic import BaseModel, Field


class ManifestRequest(BaseModel):
    """Input for the AI manifest generator."""
    service_name: str = Field(..., json_schema_extra={"examples": ["my-flask-api"]})
    language: str = Field(..., json_schema_extra={"examples": ["python"]})
    framework: str | None = Field(None, json_schema_extra={"examples": ["fastapi"]})
    db_type: str = Field("none", json_schema_extra={"examples": ["postgres"]})
    replicas: int = Field(1, ge=1, le=10)
    port: int = Field(8000, ge=1, le=65535)


class ManifestResponse(BaseModel):
    """Generated Kubernetes manifests."""
    deployment_yaml: str
    service_yaml: str
    ingress_yaml: str | None = None
    notes: str | None = None


class LogAnalyzeRequest(BaseModel):
    """Input for the AI log analyzer."""
    logs: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Raw error logs (e.g., CrashLoopBackOff output)",
        json_schema_extra={
            "examples": [
                "Back-off restarting failed container app in pod my-app-7d9f8b6c5-x2k4m"
            ]
        },
    )
    context: str | None = Field(
        None,
        max_length=2000,
        description="Additional context about the deployment",
    )


class LogAnalyzeResponse(BaseModel):
    """AI-generated log diagnosis."""
    diagnosis: str
    root_cause: str
    suggested_actions: list[str]
    severity: str = Field(
        ..., description="low | medium | high | critical"
    )
