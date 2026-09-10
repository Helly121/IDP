"""
Kubernetes MCP Server — Tools for querying and managing Kubernetes clusters.

Supports kubeconfig-file mode (local dev with Docker Desktop) and
in-cluster mode (when running inside a K8s pod).
"""

from __future__ import annotations

import logging
import os
import yaml as _yaml_unused  # noqa – may not be installed; we use json anyway

from app.core.config import settings
from app.mcp_servers.base import (
    MCPServerBase,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)

# We lazily import the kubernetes client to avoid hard failures if it isn't
# installed (the server will report is_available=False).
_k8s_available = False
try:
    from kubernetes import client as k8s_client, config as k8s_config
    _k8s_available = True
except ImportError:
    logger.warning("kubernetes package not installed — K8s MCP server will be unavailable")


class KubernetesMCPServer(MCPServerBase):
    """MCP server wrapping the Kubernetes Python client (async-compatible via threads)."""

    def __init__(self) -> None:
        self._configured = False
        if not _k8s_available:
            return

        try:
            kubeconfig = settings.KUBECONFIG
            if kubeconfig and os.path.isfile(kubeconfig):
                k8s_config.load_kube_config(config_file=kubeconfig)
                logger.info("K8s MCP: loaded kubeconfig from %s", kubeconfig)
            else:
                # Try default kubeconfig location
                try:
                    k8s_config.load_kube_config()
                    logger.info("K8s MCP: loaded default kubeconfig")
                except Exception:
                    # Last resort: in-cluster config
                    k8s_config.load_incluster_config()
                    logger.info("K8s MCP: loaded in-cluster config")
            self._v1 = k8s_client.CoreV1Api()
            self._apps_v1 = k8s_client.AppsV1Api()
            self._configured = True
        except Exception as e:
            logger.warning("K8s MCP: configuration failed — %s", e)

    # ------------------------------------------------------------------
    # MCPServerBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return _k8s_available and self._configured

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="k8s_list_pods",
                description="List all pods in a Kubernetes namespace with their status, restarts, and age.",
                parameters=[
                    ToolParameter(name="namespace", type="string", description="Kubernetes namespace (e.g. default, idp-my-service)"),
                ],
                is_mutating=False,
                category=ToolCategory.KUBERNETES,
            ),
            ToolDefinition(
                name="k8s_get_pod_logs",
                description=(
                    "Fetch the most recent logs from a specific pod. "
                    "Use this to diagnose CrashLoopBackOff, OOMKilled, or application errors."
                ),
                parameters=[
                    ToolParameter(name="namespace", type="string", description="Kubernetes namespace"),
                    ToolParameter(name="pod_name", type="string", description="Exact pod name"),
                    ToolParameter(name="tail_lines", type="integer", description="Number of recent lines to return", required=False),
                    ToolParameter(name="previous", type="boolean", description="If true, return logs from the previous terminated container", required=False),
                ],
                is_mutating=False,
                category=ToolCategory.KUBERNETES,
            ),
            ToolDefinition(
                name="k8s_get_namespace_resources",
                description="Check resource quotas, limit ranges, and current usage for a namespace.",
                parameters=[
                    ToolParameter(name="namespace", type="string", description="Kubernetes namespace"),
                ],
                is_mutating=False,
                category=ToolCategory.KUBERNETES,
            ),
            ToolDefinition(
                name="k8s_get_events",
                description="Get recent Kubernetes events for a namespace. Useful for diagnosing scheduling, pulling, or mounting failures.",
                parameters=[
                    ToolParameter(name="namespace", type="string", description="Kubernetes namespace"),
                    ToolParameter(name="limit", type="integer", description="Max number of events to return", required=False),
                ],
                is_mutating=False,
                category=ToolCategory.KUBERNETES,
            ),
            ToolDefinition(
                name="k8s_apply_manifest",
                description="Apply a Kubernetes YAML manifest to the cluster. This creates or updates the resource.",
                parameters=[
                    ToolParameter(name="namespace", type="string", description="Target namespace"),
                    ToolParameter(name="manifest_yaml", type="string", description="The full YAML manifest to apply"),
                ],
                is_mutating=True,
                category=ToolCategory.KUBERNETES,
            ),
        ]

    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        if not self.is_available():
            return ToolResult(success=False, error="Kubernetes client is not configured")

        dispatch = {
            "k8s_list_pods": self._list_pods,
            "k8s_get_pod_logs": self._get_pod_logs,
            "k8s_get_namespace_resources": self._get_namespace_resources,
            "k8s_get_events": self._get_events,
            "k8s_apply_manifest": self._apply_manifest,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        try:
            # Kubernetes client is synchronous; run in a thread
            import asyncio
            return await asyncio.to_thread(handler, params)
        except Exception as e:
            logger.exception("K8s tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Tool implementations (sync — called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _list_pods(self, params: dict) -> ToolResult:
        ns = params["namespace"]
        pods = self._v1.list_namespaced_pod(namespace=ns)
        result = []
        for pod in pods.items:
            container_statuses = pod.status.container_statuses or []
            restarts = sum(cs.restart_count for cs in container_statuses)
            result.append({
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "restarts": restarts,
                "node": pod.spec.node_name,
                "created_at": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
            })
        return ToolResult(success=True, data=result)

    def _get_pod_logs(self, params: dict) -> ToolResult:
        ns = params["namespace"]
        pod = params["pod_name"]
        tail = params.get("tail_lines", 100)
        previous = params.get("previous", False)

        logs = self._v1.read_namespaced_pod_log(
            name=pod,
            namespace=ns,
            tail_lines=tail,
            previous=previous,
        )
        return ToolResult(success=True, data={"pod": pod, "logs": logs})

    def _get_namespace_resources(self, params: dict) -> ToolResult:
        ns = params["namespace"]

        # Resource quotas
        quotas = self._v1.list_namespaced_resource_quota(namespace=ns)
        quota_data = []
        for q in quotas.items:
            quota_data.append({
                "name": q.metadata.name,
                "hard": dict(q.status.hard) if q.status.hard else {},
                "used": dict(q.status.used) if q.status.used else {},
            })

        # Limit ranges
        limits = self._v1.list_namespaced_limit_range(namespace=ns)
        limit_data = []
        for lr in limits.items:
            for item in (lr.spec.limits or []):
                limit_data.append({
                    "type": item.type,
                    "max": dict(item.max) if item.max else {},
                    "default": dict(item.default) if item.default else {},
                    "default_request": dict(item.default_request) if item.default_request else {},
                })

        return ToolResult(success=True, data={"quotas": quota_data, "limits": limit_data})

    def _get_events(self, params: dict) -> ToolResult:
        ns = params["namespace"]
        limit = params.get("limit", 20)

        events = self._v1.list_namespaced_event(namespace=ns, limit=limit)
        result = []
        for ev in events.items:
            result.append({
                "type": ev.type,
                "reason": ev.reason,
                "message": ev.message,
                "source": ev.source.component if ev.source else None,
                "first_seen": ev.first_timestamp.isoformat() if ev.first_timestamp else None,
                "last_seen": ev.last_timestamp.isoformat() if ev.last_timestamp else None,
                "count": ev.count,
                "involved_object": f"{ev.involved_object.kind}/{ev.involved_object.name}" if ev.involved_object else None,
            })
        return ToolResult(success=True, data=result)

    def _apply_manifest(self, params: dict) -> ToolResult:
        import yaml
        from kubernetes.utils import create_from_yaml
        from kubernetes import client as k8s_client
        import tempfile, os

        ns = params["namespace"]
        manifest = params["manifest_yaml"]

        # Write manifest to a temp file and apply
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(manifest)
            f.flush()
            temp_path = f.name

        try:
            api_client = k8s_client.ApiClient()
            created = create_from_yaml(api_client, temp_path, namespace=ns)
            names = []
            for item_group in created:
                if isinstance(item_group, list):
                    for item in item_group:
                        names.append(f"{item.kind}/{item.metadata.name}")
                else:
                    names.append(f"{item_group.kind}/{item_group.metadata.name}")
            return ToolResult(success=True, data={"applied": names, "namespace": ns})
        finally:
            os.unlink(temp_path)
