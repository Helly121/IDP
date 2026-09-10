# IDP System Workflow

This document describes the end-to-end workflow of the Internal Developer Platform (IDP), from student project submission and policy validation to infrastructure provisioning, GitOps deployment, human approval, and AI-driven troubleshooting.

---

## 1. Intent & Submission — Presentation Layer

A student at **Vishwakarma Institute of Technology (VIT)** logs into the React-based frontend and completes a multi-step self-service form.

The student specifies the requirements for their project, including:

- Programming language
- Framework
- Database
- Number of replicas
- Other deployment requirements

Instead of relying solely on a traditional synchronous request/response cycle, the frontend establishes a **Server-Sent Events (SSE)** connection with the FastAPI backend through:

```text
/api/v1/agent/run
```

SSE allows the backend to continuously stream **agent execution updates and tool-status events** to the student's dashboard.

For example:

```text
Agent started
→ Validating project requirements
→ Checking resource quota
→ Estimating deployment cost
→ Approval required
→ Creating GitHub repository
→ Generating deployment manifests
→ Waiting for ArgoCD synchronization
→ Deployment successful
```

This provides the student with real-time visibility into the progress of their request.

---

## 2. Context & Policy Evaluation — Agent Orchestration

The **FastAPI backend acts as the Agent Orchestrator**.

It receives the student's request and provides the **Gemini model** with:

- The student's project requirements
- Available MCP tools
- Relevant system context
- Applicable policies

The available MCP integrations include:

- GitHub MCP Server
- Kubernetes MCP Server
- ArgoCD MCP Server
- Policy MCP Server

Before generating or modifying infrastructure, the agent evaluates whether the requested deployment complies with institutional policies.

### Policy Quota Check

Gemini autonomously selects the:

```text
policy_check_quota
```

tool through the custom **Policy MCP Server**.

The tool verifies whether the student is within their permitted compute/resource limits.

### Cost Estimation

The agent then calls:

```text
policy_estimate_cost
```

to estimate the expected infrastructure cost of the requested deployment.

Since these operations are **read-only policy queries**, they can be executed immediately. The results are returned to the orchestrator and provided back to Gemini as context for the next decision.

---

## 3. Human-in-the-Loop — Approval Gate

After completing the policy checks, Gemini determines that the request is eligible to proceed and prepares to create the project infrastructure.

It attempts to invoke:

```text
github_create_repo
```

However, repository creation is classified as a **mutating action**.

The FastAPI backend therefore intercepts the tool request instead of executing it immediately.

### Pending Action

The backend creates a `PendingAction` record in **PostgreSQL** containing information such as:

- Requested action
- Requesting user
- Resource requirements
- Tool to be executed
- Current status
- Approval metadata

The frontend dynamically displays an:

> **Approval Required**

card.

The agent execution is paused until an authorized user, such as a professor or lab administrator, reviews the request through the:

```text
/approvals
```

dashboard.

The authorized user can approve or reject the requested resource allocation.

---

## 4. Infrastructure Generation — GitHub MCP Execution

Once approval is granted, the backend records the approval and resumes the paused agent workflow.

The agent proceeds with the approved GitHub operations.

### Repository Creation

The backend executes:

```text
github_create_repo
```

to create the student's project repository.

### Project Files

The agent then uses:

```text
github_push_file
```

to commit the required project files.

Depending on the selected technology stack, the generated project may include:

- Application source code
- `Dockerfile`
- Dependency configuration
- Environment configuration templates
- Kubernetes Deployment manifests
- Kubernetes Service manifests
- Kubernetes Ingress manifests
- Other standardized configuration files

The generated infrastructure follows the IDP's predefined templates and policies rather than allowing unrestricted infrastructure configuration.

---

## 5. GitOps Synchronization — ArgoCD & Kubernetes

After the project configuration and Kubernetes manifests are committed to GitHub, the workflow transitions from agent-driven provisioning to **GitOps-based deployment**.

### ArgoCD Monitoring

**ArgoCD continuously monitors the configured Git repository** for changes.

When the newly generated Kubernetes manifests are detected, ArgoCD synchronizes the desired state from Git with the live Kubernetes cluster.

Conceptually:

```text
Git Repository
      │
      │ Desired State
      ▼
   ArgoCD
      │
      │ Synchronization
      ▼
Kubernetes Cluster
      │
      ▼
Running Application
```

ArgoCD becomes responsible for maintaining the application's desired operational state.

### Deployment Verification

The agent can verify the deployment using:

```text
argocd_get_app_status
```

In the MVP, this may initially be implemented using a mock or stub tool.

Once the deployment reaches the expected state, the backend streams the final status to the frontend:

```text
Deployment Complete
```

---

## 6. AI-Driven Troubleshooting — Virtual Mentor Loop

The IDP also provides an AI-assisted troubleshooting interface for deployed applications.

For example, if a student's application fails after deployment, the student can open the portal's chat interface and ask:

> "Why is my database failing?"

Gemini can investigate the running workload through authorized Kubernetes MCP tools.

### Kubernetes Diagnostics

The agent can call:

```text
k8s_get_events
```

to retrieve Kubernetes events associated with the workload.

It can also call:

```text
k8s_get_pod_logs
```

to retrieve relevant application or container logs.

The returned information may contain errors such as:

```text
Connection refused
Database authentication failed
CrashLoopBackOff
Missing environment variable
ImagePullBackOff
```

Gemini interprets these technical signals and translates them into a **plain-English explanation** for the student.

---

## 7. AI-Assisted Remediation

If the investigation identifies a configuration or code-level problem, Gemini can prepare a proposed fix.

For example, the agent may prepare a:

```text
github_push_file
```

operation containing an updated configuration file or source-code change.

Because this is another **mutating action**, the IDP does not automatically apply the change.

Instead:

```text
AI identifies problem
        ↓
AI prepares proposed fix
        ↓
PendingAction created
        ↓
User approval required
        ↓
Authorized user approves
        ↓
Change committed to Git
        ↓
ArgoCD detects change
        ↓
Kubernetes synchronized
        ↓
Deployment verified
```

This preserves the **Human-in-the-Loop (HITL)** safety model even during automated troubleshooting.

---

# End-to-End Workflow

The complete IDP workflow can be summarized as:

```text
┌──────────────────────────┐
│     Student Frontend     │
│       React + SSE        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     FastAPI Backend      │
│    Agent Orchestrator    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       Gemini Model       │
│      Agent Decision      │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       Policy MCP         │
│  Quota + Cost Evaluation │
└────────────┬─────────────┘
             │
             ▼
       ┌─────────────┐
       │  HITL Gate  │
       └──────┬──────┘
              │ Approval
              ▼
┌──────────────────────────┐
│       GitHub MCP         │
│ Repo + File Generation   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│        GitHub Repo       │
│     Desired State        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│         ArgoCD           │
│     GitOps Sync          │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    Kubernetes Cluster    │
│    Running Workloads     │
└────────────┬─────────────┘
             │
             │ Failure / Issue
             ▼
┌──────────────────────────┐
│   Kubernetes MCP Tools   │
│ Events + Pod Logs        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    Gemini Troubleshooter │
│ Diagnose + Explain       │
└────────────┬─────────────┘
             │
             │ Proposed Fix
             ▼
       ┌─────────────┐
       │  HITL Gate  │
       └──────┬──────┘
              │ Approval
              ▼
        GitHub → ArgoCD
              │
              ▼
        Kubernetes Fix
```

---

# Key Design Principles

The IDP workflow is built around the following principles:

### 1. Self-Service

Students can provision standardized development environments without manually configuring infrastructure.

### 2. Policy-First Provisioning

Resource quotas and estimated costs are evaluated before infrastructure is created.

### 3. Human-in-the-Loop Safety

Mutating operations require explicit authorization before execution.

### 4. MCP-Based Tool Integration

The agent interacts with external systems through well-defined MCP tools rather than directly coupling the LLM to infrastructure APIs.

### 5. GitOps

Git acts as the source of truth for application and infrastructure configuration.

### 6. Real-Time Feedback

SSE provides live agent execution and deployment-status updates to the frontend.

### 7. AI-Assisted Operations

The agent can diagnose deployment failures, interpret logs, and prepare remediation changes while preserving approval controls.

### 8. Separation of Concerns

The architecture separates:

```text
Presentation
     ↓
Agent Orchestration
     ↓
Policy
     ↓
Human Approval
     ↓
Tool Execution
     ↓
GitOps
     ↓
Infrastructure
```

This separation makes the system easier to secure, audit, maintain, and extend with additional MCP tools.
