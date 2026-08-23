"""
AI service layer — integrates with Google Gemini API for:
  1. Kubernetes manifest generation from project specifications
  2. Error log analysis and diagnosis

Falls back to template-based generation if the Gemini API key is not configured.
"""

import json
import logging
from app.core.config import settings
from app.schemas.deployment import (
    ManifestRequest,
    ManifestResponse,
    LogAnalyzeRequest,
    LogAnalyzeResponse,
)

logger = logging.getLogger(__name__)

# ── Gemini client (lazy-loaded) ──────────────────────────────────
_gemini_model = None


def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel("gemini-3.6-flash")
            logger.info("Gemini API client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini: {e}")
    return _gemini_model


# ── Template-based fallback manifests ────────────────────────────

def _generate_deployment_yaml(req: ManifestRequest) -> str:
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {req.service_name}
  labels:
    app: {req.service_name}
    managed-by: academic-idp
spec:
  replicas: {req.replicas}
  selector:
    matchLabels:
      app: {req.service_name}
  template:
    metadata:
      labels:
        app: {req.service_name}
    spec:
      containers:
        - name: {req.service_name}
          image: ghcr.io/academic-idp/{req.service_name}:latest
          ports:
            - containerPort: {req.port}
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: {req.port}
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: {req.port}
            initialDelaySeconds: 5
            periodSeconds: 10
"""


def _generate_service_yaml(req: ManifestRequest) -> str:
    return f"""apiVersion: v1
kind: Service
metadata:
  name: {req.service_name}-svc
  labels:
    app: {req.service_name}
spec:
  type: ClusterIP
  selector:
    app: {req.service_name}
  ports:
    - port: 80
      targetPort: {req.port}
      protocol: TCP
"""


def _generate_ingress_yaml(req: ManifestRequest) -> str:
    return f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {req.service_name}-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
    - host: {req.service_name}.idp.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {req.service_name}-svc
                port:
                  number: 80
"""


# ── Public API ───────────────────────────────────────────────────

async def generate_manifests(req: ManifestRequest) -> ManifestResponse:
    """
    Generate Kubernetes manifests. Uses Gemini if configured,
    otherwise falls back to template-based generation.
    """
    model = _get_gemini_model()

    if model:
        try:
            prompt = f"""You are a Kubernetes expert. Generate production-ready Kubernetes YAML manifests for the following application:

- Service Name: {req.service_name}
- Language: {req.language}
- Framework: {req.framework or 'none'}
- Database: {req.db_type}
- Replicas: {req.replicas}
- Container Port: {req.port}
- Container Image: ghcr.io/academic-idp/{req.service_name}:latest

Generate three YAML documents:
1. A Deployment with resource requests/limits, health probes, and security context
2. A ClusterIP Service
3. An Ingress resource

Return ONLY valid YAML. Separate each document with ---
Include best-practice annotations, labels, and security settings.
"""
            response = model.generate_content(prompt)
            parts = response.text.split("---")

            deployment_yaml = parts[0].strip() if len(parts) > 0 else _generate_deployment_yaml(req)
            service_yaml = parts[1].strip() if len(parts) > 1 else _generate_service_yaml(req)
            ingress_yaml = parts[2].strip() if len(parts) > 2 else _generate_ingress_yaml(req)

            return ManifestResponse(
                deployment_yaml=deployment_yaml,
                service_yaml=service_yaml,
                ingress_yaml=ingress_yaml,
                notes="Generated with Google Gemini AI",
            )
        except Exception as e:
            logger.error(f"Gemini manifest generation failed: {e}")

    # Fallback to templates
    return ManifestResponse(
        deployment_yaml=_generate_deployment_yaml(req),
        service_yaml=_generate_service_yaml(req),
        ingress_yaml=_generate_ingress_yaml(req),
        notes="Generated from templates (Gemini API not configured)",
    )


async def analyze_logs(req: LogAnalyzeRequest) -> LogAnalyzeResponse:
    """
    Analyze Kubernetes error logs. Uses Gemini if configured,
    otherwise returns a heuristic-based diagnosis.
    """
    model = _get_gemini_model()

    if model:
        try:
            prompt = f"""You are a Kubernetes debugging expert. Analyze the following error logs and provide a diagnosis.

LOGS:
{req.logs}

{f"CONTEXT: {req.context}" if req.context else ""}

Respond in valid JSON with this exact structure:
{{
  "diagnosis": "A clear, natural-language summary of what went wrong",
  "root_cause": "The most likely root cause",
  "suggested_actions": ["action1", "action2", "action3"],
  "severity": "low|medium|high|critical"
}}

Return ONLY the JSON object, no markdown fences or additional text.
"""
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            data = json.loads(text)

            return LogAnalyzeResponse(**data)
        except Exception as e:
            logger.error(f"Gemini log analysis failed: {e}")

    # Heuristic fallback
    diagnosis = "Unable to determine — AI analysis unavailable"
    root_cause = "Unknown"
    severity = "medium"
    actions = ["Check pod logs with: kubectl logs <pod-name>"]

    logs_lower = req.logs.lower()
    if "crashloopbackoff" in logs_lower:
        diagnosis = "The container is repeatedly crashing after startup."
        root_cause = "Application crash — likely a missing dependency, config error, or unhandled exception."
        severity = "high"
        actions = [
            "Check application logs: kubectl logs <pod-name> --previous",
            "Verify environment variables and config maps",
            "Ensure the container entrypoint command is correct",
            "Check if required secrets are mounted",
        ]
    elif "imagepullbackoff" in logs_lower or "errimagepull" in logs_lower:
        diagnosis = "Kubernetes cannot pull the container image."
        root_cause = "Image does not exist, tag is wrong, or registry credentials are missing."
        severity = "high"
        actions = [
            "Verify the image name and tag exist in the registry",
            "Check imagePullSecrets in the pod spec",
            "Ensure the registry is accessible from the cluster",
        ]
    elif "oomkilled" in logs_lower:
        diagnosis = "The container was terminated because it exceeded its memory limit."
        root_cause = "Memory leak or insufficient memory allocation."
        severity = "critical"
        actions = [
            "Increase memory limits in the deployment spec",
            "Profile the application for memory leaks",
            "Consider horizontal scaling instead of vertical",
        ]

    return LogAnalyzeResponse(
        diagnosis=diagnosis,
        root_cause=root_cause,
        suggested_actions=actions,
        severity=severity,
    )
