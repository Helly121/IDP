"""
Unit tests for deterministic tool category routing (select_tool_categories).
Tests at least 10 canonical, domain-specific, mixed, and ambiguous prompts.
"""

import pytest
from app.mcp_servers.base import ToolCategory
from app.services.tool_router import select_tool_categories


def test_router_terraform_and_cicd():
    prompt = "Create the Terraform infrastructure for my project and prepare a CI/CD workflow"
    categories = select_tool_categories(prompt)
    assert ToolCategory.TERRAFORM in categories
    assert ToolCategory.CICD in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.GITHUB not in categories


def test_router_pure_terraform():
    prompt = "Format and validate main.tf and variables.tf under iac/dev"
    categories = select_tool_categories(prompt)
    assert ToolCategory.TERRAFORM in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.KUBERNETES not in categories
    assert ToolCategory.ARGOCD not in categories


def test_router_pure_cicd():
    prompt = "Update the GitHub Actions build pipeline to test on push"
    categories = select_tool_categories(prompt)
    assert ToolCategory.CICD in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.TERRAFORM not in categories


def test_router_k8s_crashloop():
    prompt = "Why is my pod in CrashLoopBackOff?"
    categories = select_tool_categories(prompt)
    assert ToolCategory.KUBERNETES in categories
    assert ToolCategory.ARGOCD in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.TERRAFORM not in categories


def test_router_k8s_oom_and_logs():
    prompt = "Pod logs show OOMKilled in default namespace, check container memory"
    categories = select_tool_categories(prompt)
    assert ToolCategory.KUBERNETES in categories
    assert ToolCategory.ARGOCD in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.GITHUB not in categories


def test_router_argocd_sync():
    prompt = "Check ArgoCD gitops application status and trigger sync"
    categories = select_tool_categories(prompt)
    assert ToolCategory.ARGOCD in categories
    assert ToolCategory.KUBERNETES in categories
    assert ToolCategory.POLICY in categories


def test_router_github_push_and_repo():
    prompt = "Push Dockerfile to GitHub repo and create a new branch"
    categories = select_tool_categories(prompt)
    assert ToolCategory.GITHUB in categories
    assert ToolCategory.POLICY in categories
    assert ToolCategory.TERRAFORM not in categories


def test_router_policy_cost_estimation():
    prompt = "Estimate cost for 4 replicas with postgres"
    categories = select_tool_categories(prompt)
    assert categories == {ToolCategory.POLICY}


def test_router_policy_quota_and_escalation():
    prompt = "Check my student quota limits and request quota escalation"
    categories = select_tool_categories(prompt)
    assert categories == {ToolCategory.POLICY}


def test_router_ambiguous_greeting():
    prompt = "Hello! How can you help me today?"
    categories = select_tool_categories(prompt)
    # Ambiguous prompt must safely fall back to all registered categories
    assert categories == set(ToolCategory)


def test_router_ambiguous_vague_query():
    prompt = "Something is failing in my project but I am not sure what"
    categories = select_tool_categories(prompt)
    assert categories == set(ToolCategory)


def test_router_ambiguous_general_inquiry():
    prompt = "What are the best practices for academic project submissions?"
    categories = select_tool_categories(prompt)
    assert categories == set(ToolCategory)


def test_router_policy_always_included():
    # In every single prompt, POLICY must always be present
    test_cases = [
        "provision infra",
        "ci actions",
        "check logs",
        "push file",
        "cost estimate",
        "random message",
    ]
    for msg in test_cases:
        cats = select_tool_categories(msg)
        assert ToolCategory.POLICY in cats, f"Policy missing for prompt: {msg}"
