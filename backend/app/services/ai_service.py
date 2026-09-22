"""
AI Agent Orchestrator — Gemini-powered agentic loop with MCP tool calling.

Replaces the previous static prompt-wrapper with an autonomous agent that:
1. Receives a user message
2. Sends it to Gemini with all MCP tool declarations
3. Processes function_call responses by dispatching to the correct MCP server
4. For read-only tools: executes immediately and feeds results back to Gemini
5. For mutating tools: creates a PendingAction and yields an approval_required event
6. Loops until Gemini produces a final text response
7. Yields structured SSE events at each step for the frontend to render live
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.database import async_session_factory
from app.mcp_servers.registry import registry
from app.schemas.agent import AgentEvent, AgentEventType
from app.schemas.deployment import (
    ManifestRequest,
    ManifestResponse,
    LogAnalyzeRequest,
    LogAnalyzeResponse,
)
from app.services import approval_service

logger = logging.getLogger(__name__)

# Gemini model and function-calling setup
_gemini_model = None


def _get_gemini_model():
    """Lazily initialise the Gemini model with MCP tool declarations."""
    global _gemini_model
    if _gemini_model is None and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)

            # Build tool declarations from the MCP registry
            tool_declarations = registry.get_gemini_declarations()
            logger.info("Registering %d tools with Gemini", len(tool_declarations))

            _gemini_model = genai.GenerativeModel(
                "gemini-2.0-flash",
                tools=[{"function_declarations": tool_declarations}] if tool_declarations else None,
                system_instruction=_build_system_prompt(),
            )
            logger.info("Gemini agent model initialized with function calling")
        except Exception as e:
            logger.warning("Failed to initialize Gemini agent: %s", e)
    return _gemini_model


def _build_system_prompt() -> str:
    """Build the system prompt for the DevOps AI agent."""
    return """You are an expert DevOps AI agent embedded in an Academic Internal Developer Platform (IDP).
Your role is to help students, guides, and admins with:
- Provisioning and managing Terraform Infrastructure-as-Code (IaC) under iac/
- Generating and managing GitHub Actions CI/CD pipelines under .github/workflows/
- Generating Dockerfiles, Kubernetes manifests, and managing cluster resources
- Diagnosing deployment failures (CrashLoopBackOff, ImagePullBackOff, OOMKilled)
- Managing GitHub repositories and ArgoCD GitOps synchronisation
- Enforcing institutional RBAC policies (student quotas vs faculty approvals)

You have access to MCP tools for:
- Terraform: inspect files, create/update configurations, format (terraform_fmt), initialize (terraform_init), validate (terraform_validate), and generate safe speculative plans (terraform_plan)
- CI/CD Workflows: list, inspect, create/update (workflow_write), and validate (workflow_validate) GitHub Actions workflows
- GitHub: create repositories, list repositories, push and read files
- Kubernetes & ArgoCD: inspect and manage cluster workloads and GitOps sync
- Policy Engine: evaluate RBAC rules and calculate cost estimations

Important Operational & Security Rules:
1. Mutating actions (such as terraform_write_file, workflow_write, github_push_file, github_create_repo) automatically trigger Human-in-the-Loop (HITL) approval gates. Inform the user that the action is queued for review.
2. Terraform apply is NOT an MCP capability. Infrastructure deployments are executed exclusively through protected GitHub Actions workflows after code is committed and approved.
3. Keep all Terraform operations strictly scoped to iac/ and workflow operations strictly scoped to .github/workflows/.
4. Always explain your plan, execute appropriate validation/formatting/planning tools, and be concise, helpful, and security-conscious. Never expose secrets or credentials."""


async def run_agent_stream(
    message: str,
    user_id: str,
    project_id: str | None = None,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Main entry point: run the agentic loop and yield SSE events.

    Each yield is a fully-formatted SSE string (event + data + newlines).
    """
    sid = uuid.UUID(session_id) if session_id else uuid.uuid4()
    uid = uuid.UUID(user_id)
    now = lambda: datetime.now(timezone.utc)

    # Yield: thinking
    yield AgentEvent(
        type=AgentEventType.THINKING,
        data={"message": "Analyzing your request and determining the best approach..."},
        timestamp=now(),
    ).to_sse()

    model = _get_gemini_model()
    if model is None:
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": "AI agent is not available. Please configure GEMINI_API_KEY."},
            timestamp=now(),
        ).to_sse()
        return

    # Build initial context
    context_parts = [message]
    if project_id:
        context_parts.append(f"\n[Context: This request is related to project ID {project_id}]")
    context_parts.append(f"\n[User ID: {user_id}]")

    try:
        # Start a chat session for multi-turn tool calling
        chat = model.start_chat(history=[])
        response = chat.send_message("\n".join(context_parts))

        # Agentic loop: keep processing until we get a text response
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Check if the response contains function calls
            candidate = response.candidates[0] if response.candidates else None
            if candidate is None:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    data={"message": "No response from AI model"},
                    timestamp=now(),
                ).to_sse()
                return

            parts = candidate.content.parts if candidate.content else []

            # Collect all function calls from this response
            function_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call]
            text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]

            # If we only have text (no function calls), this is the final response
            if not function_calls:
                final_text = "\n".join(text_parts) if text_parts else "I've completed the analysis."
                yield AgentEvent(
                    type=AgentEventType.FINAL_RESPONSE,
                    data={"message": final_text},
                    timestamp=now(),
                ).to_sse()
                return

            # Process each function call
            from google.generativeai import protos

            function_responses = []

            for fc_part in function_calls:
                fc = fc_part.function_call
                tool_name = fc.name
                tool_params = dict(fc.args) if fc.args else {}

                # Yield: tool_call event
                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL,
                    data={
                        "tool_name": tool_name,
                        "params": tool_params,
                        "is_mutating": registry.is_mutating(tool_name),
                    },
                    timestamp=now(),
                ).to_sse()

                # Check if this is a mutating tool
                if registry.is_mutating(tool_name):
                    # Create a pending action and yield approval_required
                    async with async_session_factory() as db:
                        action = await approval_service.create_pending_action(
                            db=db,
                            session_id=sid,
                            user_id=uid,
                            tool_name=tool_name,
                            tool_params=tool_params,
                        )
                        await db.commit()

                        yield AgentEvent(
                            type=AgentEventType.APPROVAL_REQUIRED,
                            data={
                                "action_id": str(action.id),
                                "tool_name": tool_name,
                                "params": tool_params,
                                "message": (
                                    f"The action '{tool_name}' requires approval from a guide or admin. "
                                    f"Action ID: {action.id}"
                                ),
                            },
                            timestamp=now(),
                        ).to_sse()

                    # Feed back a "pending" result to Gemini so it can continue reasoning
                    function_responses.append(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=tool_name,
                                response={
                                    "result": {
                                        "status": "pending_approval",
                                        "action_id": str(action.id),
                                        "message": "This mutating action requires human approval before execution. The request has been queued.",
                                    }
                                },
                            )
                        )
                    )
                else:
                    # Read-only tool: execute immediately
                    result = await registry.dispatch(tool_name, tool_params)

                    # Yield: tool_result event
                    yield AgentEvent(
                        type=AgentEventType.TOOL_RESULT,
                        data={
                            "tool_name": tool_name,
                            "success": result.success,
                            "result": result.to_dict(),
                        },
                        timestamp=now(),
                    ).to_sse()

                    function_responses.append(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=tool_name,
                                response={"result": result.to_dict()},
                            )
                        )
                    )

            # Send all function responses back to Gemini for the next iteration
            response = chat.send_message(function_responses)

        # If we hit max iterations, yield a warning
        yield AgentEvent(
            type=AgentEventType.FINAL_RESPONSE,
            data={"message": "I've reached the maximum number of reasoning steps. Here's what I've found so far."},
            timestamp=now(),
        ).to_sse()

    except Exception as e:
        logger.exception("Agent loop error")
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": f"Agent encountered an error: {str(e)}"},
            timestamp=now(),
        ).to_sse()


# ========================================================================
# Legacy API — kept for backward compatibility with existing endpoints
# ========================================================================

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


async def generate_manifests(req: ManifestRequest) -> ManifestResponse:
    """Legacy endpoint: generate K8s manifests (template-based fallback)."""
    model = _get_gemini_model()

    if model:
        try:
            import google.generativeai as genai

            # Use a simple non-agentic model for legacy endpoint
            simple_model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = f"""You are a Kubernetes expert. Generate production-ready Kubernetes YAML manifests for:
- Service Name: {req.service_name}
- Language: {req.language}
- Framework: {req.framework or 'none'}
- Database: {req.db_type}
- Replicas: {req.replicas}
- Container Port: {req.port}
- Container Image: ghcr.io/academic-idp/{req.service_name}:latest

Generate three YAML documents (Deployment, Service, Ingress).
Return ONLY valid YAML. Separate each document with ---"""

            response = simple_model.generate_content(prompt)
            parts = response.text.split("---")
            return ManifestResponse(
                deployment_yaml=parts[0].strip() if len(parts) > 0 else _generate_deployment_yaml(req),
                service_yaml=parts[1].strip() if len(parts) > 1 else _generate_service_yaml(req),
                ingress_yaml=parts[2].strip() if len(parts) > 2 else _generate_ingress_yaml(req),
                notes="Generated with Google Gemini AI",
            )
        except Exception as e:
            logger.error("Gemini manifest generation failed: %s", e)

    return ManifestResponse(
        deployment_yaml=_generate_deployment_yaml(req),
        service_yaml=_generate_service_yaml(req),
        ingress_yaml=_generate_ingress_yaml(req),
        notes="Generated from templates (Gemini API not configured)",
    )


async def analyze_logs(req: LogAnalyzeRequest) -> LogAnalyzeResponse:
    """Legacy endpoint: analyze K8s error logs (heuristic fallback)."""
    model = _get_gemini_model()

    if model:
        try:
            import google.generativeai as genai

            simple_model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = f"""You are a Kubernetes debugging expert. Analyze these error logs:

LOGS:
{req.logs}

{f"CONTEXT: {req.context}" if req.context else ""}

Respond in valid JSON:
{{"diagnosis": "...", "root_cause": "...", "suggested_actions": ["..."], "severity": "low|medium|high|critical"}}

Return ONLY the JSON object."""

            response = simple_model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            data = json.loads(text)
            return LogAnalyzeResponse(**data)
        except Exception as e:
            logger.error("Gemini log analysis failed: %s", e)

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
