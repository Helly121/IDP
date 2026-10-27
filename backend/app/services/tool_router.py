"""
Deterministic Intent & Tool Category Router for DevHub AI Agent.

Selects a minimal subset of MCP tool categories per user request to slash
prompt token overhead from ~3k tokens (all 29 tools) down to ~400-800 tokens.

Rules:
- Strictly deterministic keyword and pattern matching (no LLM calls, zero latency).
- ToolCategory.POLICY is ALWAYS included (for RBAC, quotas, and cost estimation).
- Safe fallback: if no domain-specific categories match, all categories are included.
"""

from __future__ import annotations

import re
from typing import Set

from app.mcp_servers.base import ToolCategory

# Regex keyword patterns for deterministic category routing
_CATEGORY_PATTERNS: dict[ToolCategory, list[str]] = {
    ToolCategory.TERRAFORM: [
        r"\bterraform\b",
        r"\btf\b",
        r"\biac\b",
        r"\binfrastructure\b",
        r"\binfra\b",
        r"\bhcl\b",
        r"\bs3\b",
        r"\bbucket\b",
        r"\bvpc\b",
        r"\bplan\b",
        r"\bmain\.tf\b",
        r"\bvariables?\.tf\b",
        r"\boutputs?\.tf\b",
    ],
    ToolCategory.CICD: [
        r"\bpipeline\b",
        r"\bworkflows?\b",
        r"\bci\b",
        r"\bcd\b",
        r"\bci/cd\b",
        r"\bci-cd\b",
        r"\bgithub\s*actions\b",
        r"\baction\b",
        r"\bactions\b",
        r"\bci\.ya?ml\b",
        r"\bdeploy\.ya?ml\b",
        r"\bbuild\b",
    ],
    ToolCategory.GITHUB: [
        r"\bgithub\b",
        r"\brepos?\b",
        r"\brepository\b",
        r"\brepositories\b",
        r"\bcommit\b",
        r"\bpush\b",
        r"\bbranch\b",
        r"\bpull\s*request\b",
        r"\bpr\b",
        r"\bclone\b",
    ],
    ToolCategory.KUBERNETES: [
        r"\bk8s\b",
        r"\bkubernetes\b",
        r"\bkube\b",
        r"\bpods?\b",
        r"\bcrashloop\b",
        r"\bcrashloopbackoff\b",
        r"\blogs?\b",
        r"\boom\b",
        r"\boomkilled\b",
        r"\bimage\s*pull\b",
        r"\bimagepullbackoff\b",
        r"\bnamespaces?\b",
        r"\bclusters?\b",
        r"\bmanifests?\b",
        r"\brestarts?\b",
        r"\bcontainer\b",
        r"\bdeployment\b",
        r"\bdeployments\b",
    ],
    ToolCategory.ARGOCD: [
        r"\bargo\b",
        r"\bargocd\b",
        r"\bsync\b",
        r"\bgitops\b",
        r"\bcrashloop\b",
        r"\bcrashloopbackoff\b",
        r"\bdeployment\b",
        r"\bdeployments\b",
        r"\bdeploy\b",
    ],
    ToolCategory.POLICY: [
        r"\bcosts?\b",
        r"\bestimates?\b",
        r"\bestimation\b",
        r"\bquotas?\b",
        r"\bbudgets?\b",
        r"\bprices?\b",
        r"\bpricing\b",
        r"\breplicas?\b",
        r"\broles?\b",
        r"\brbac\b",
        r"\bpermissions?\b",
        r"\bescalat(?:e|ion)\b",
    ],
}


def select_tool_categories(
    message: str,
    target_project: str | None = None,
) -> set[ToolCategory]:
    """
    Selects the minimal set of ToolCategory values relevant to the user's message.

    - Always includes ToolCategory.POLICY.
    - If no specific categories match, safely returns all registered categories.
    """
    normalized = message.lower().strip()
    selected: set[ToolCategory] = {ToolCategory.POLICY}

    matched_any = False
    for category, patterns in _CATEGORY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, normalized, re.IGNORECASE):
                selected.add(category)
                matched_any = True
                break

    # If cluster deployment/crash diagnosis is detected, pair Kubernetes and ArgoCD together
    if ToolCategory.KUBERNETES in selected or ToolCategory.ARGOCD in selected:
        selected.add(ToolCategory.KUBERNETES)
        selected.add(ToolCategory.ARGOCD)

    # Safe fallback: if only POLICY matched (no specific domain detected), return all categories
    if not matched_any:
        return set(ToolCategory)

    return selected
