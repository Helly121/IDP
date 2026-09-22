# Academic Internal Developer Platform (IDP)

A self-service Internal Developer Platform tailored for academic environments that automates end-to-end cloud infrastructure provisioning.

## Phase 1.5 Architecture (Agent-Driven)

The platform utilizes an autonomous, agent-driven architecture powered by Gemini 2.0 and the Model Context Protocol (MCP). Instead of static wrappers, a DevSecOps AI Mentor actively manages provisioning and deployment via human-in-the-loop (HITL) approval gates.

```mermaid
graph TB
    subgraph Presentation["Presentation Layer"]
        UI["React.js Self-Service Portal"]
        AP["AI Agent Panel (SSE)"]
        AD["Approvals Dashboard"]
    end

    subgraph Orchestration["Orchestration Layer"]
        API["FastAPI Backend"]
        AGENT["Gemini AI Agent"]
        HITL["Approval Engine"]
        DB["PostgreSQL (pending_actions)"]
    end

    subgraph MCP["MCP Tool Servers"]
        MCP_GH["GitHub Server"]
        MCP_K8S["Kubernetes Server"]
        MCP_ARGO["ArgoCD Server"]
        MCP_POL["Policy/Cost Server"]
        MCP_TF["Terraform Server (Dockerized)"]
        MCP_CICD["GitHub Actions Server"]
    end

    subgraph Execution["Execution Layer"]
        GH["GitHub Repositories / Workflows"]
        ARGO["ArgoCD GitOps"]
        K8S["Kubernetes Cluster"]
        TF_CLI["Terraform CLI (Inside Container)"]
    end

    UI --> API
    AP -- "SSE Stream" --> AGENT
    AD --> HITL
    API --> DB
    
    AGENT <--> |"Function Calling"| MCP
    MCP --> HITL
    
    MCP_GH --> GH
    MCP_K8S --> K8S
    MCP_ARGO --> ARGO
    MCP_TF --> TF_CLI
    MCP_CICD --> GH
```

## Project Structure

```
├── frontend/           # React + Vite — Self-service portal & Agent UI
├── backend/            # FastAPI — Orchestration & Agent loop
│   ├── app/mcp_servers/ # Model Context Protocol Tool Integrations
│   └── tests/          # Backend & MCP test suite
├── iac/                # Terraform — Infrastructure as Code
│   ├── environments/   # Environment configurations (dev)
│   ├── modules/        # Reusable modules (k8s-namespace)
│   └── templates/      # Resource templates
├── k8s/                # Kustomize manifests — ArgoCD target
├── .github/workflows/  # GitHub Actions CI/CD (ci-cd.yml, terraform.yml)
└── docker-compose.yml  # Local development environment
```

## MCP Capabilities & Tools

The backend exposes tools categorized into specialized MCP servers:

| MCP Server | Category | Tool | Type | Description |
|------------|----------|------|------|-------------|
| **Terraform** | `terraform` | `terraform_list_files` | Read-only | List files and directories under `iac/` |
| | | `terraform_get_file` | Read-only | Read file content from `iac/` |
| | | `terraform_write_file` | **Mutating (HITL)** | Create/update Terraform files under `iac/` |
| | | `terraform_fmt` | Read-only / Exec | Format Terraform files or check format with real CLI |
| | | `terraform_init` | Read-only / Exec | Initialize Terraform (`-backend=false`) with real CLI |
| | | `terraform_validate` | Read-only / Exec | Validate Terraform syntax with real CLI |
| | | `terraform_plan` | Read-only / Exec | Generate safe speculative execution plan |
| **CI/CD** | `cicd` | `workflow_list` | Read-only | List workflows in `.github/workflows/` |
| | | `workflow_get` | Read-only | Read workflow YAML file |
| | | `workflow_write` | **Mutating (HITL)** | Create/update workflow YAML with syntax validation |
| | | `workflow_validate` | Read-only | Validate YAML syntax and GitHub Actions schema |
| **GitHub** | `github` | `github_create_repo` | **Mutating (HITL)** | Create a new repository |
| | | `github_push_file` | **Mutating (HITL)** | Push file to repository |
| | | `github_list_repos` | Read-only | List organization repositories |
| | | `github_get_file_content`| Read-only | Read file from repository |
| **Kubernetes** | `kubernetes`| `k8s_apply_manifest` | **Mutating (HITL)** | Apply manifest to cluster |
| | | `k8s_get_resources` | Read-only | Query pods, services, deployments |
| | | `k8s_get_logs` | Read-only | Fetch container logs |
| **Policy** | `policy` | `policy_check` | Read-only | Validate RBAC limits and quotas |
| | | `policy_estimate_cost` | Read-only | Estimate cloud infrastructure cost |

> [!NOTE]
> **Terraform Apply**: `terraform_apply` is intentionally **not** an MCP tool. Infrastructure deployments are executed exclusively through protected GitHub Actions workflows (`.github/workflows/terraform.yml`) with reviewer approval.

## End-to-End HITL & Deployment Flow

```
User Prompt
    │
    ▼
Gemini Agent ──► Analyzes request & invokes MCP tools
    │
    ├─► Read-only tools (fmt, init, validate, plan): Executed immediately inside Docker
    │
    └─► Mutating tools (terraform_write_file, workflow_write):
            │
            ▼
        Approval Engine: Creates PendingAction record (status=pending)
            │
            ▼
        Guide / Admin Review: Approves action via Approvals Dashboard (/api/v1/approvals/{id}/approve)
            │
            ▼
        Execution & Git Commit: Pushed via GitHub MCP
            │
            ▼
        GitHub Actions CI/CD:
            1. Pull Request: Format check, init -backend=false, validate (no secrets needed)
            2. Main branch: Speculative plan preview
            3. Protected Apply: Manual dispatch requiring GitHub Environment reviewer sign-off
```

### Example Agent Request
> *"Create the Terraform infrastructure required for my project and prepare a CI/CD workflow."*

The agent will:
1. Inspect the `iac/` workspace using `terraform_list_files`.
2. Generate modular Terraform configurations under `iac/environments/dev/` via `terraform_write_file` (queues HITL approval).
3. Validate and format using `terraform_fmt` and `terraform_validate`.
4. Generate a speculative plan using `terraform_plan`.
5. Prepare a GitHub Actions workflow under `.github/workflows/` via `workflow_write` (queues HITL approval).

## Quick Start (Dockerized)

Terraform CLI (version 1.9.8) is pre-installed directly inside the backend Docker image. There is no need to install Terraform on the host machine.

### 1. Start Services

```bash
# Build images and start all containers
docker compose build
docker compose up -d

# Verify container status
docker compose ps

# Access the platform
#    Frontend:            http://localhost:5173
#    Backend (API Docs):  http://localhost:8000/docs
```

### 2. Verify Dockerized Terraform CLI

```bash
# Check Terraform version inside backend container
docker compose exec backend terraform version

# Run formatting check across IaC directory
docker compose exec backend terraform fmt -check -recursive /app/iac

# Initialize and validate dev environment
docker compose exec backend terraform -chdir=/app/iac/environments/dev init -backend=false
docker compose exec backend terraform -chdir=/app/iac/environments/dev validate
```

### 3. Run Backend Test Suite

```bash
docker compose exec backend pytest /app/tests -v
```

## Environment Variables & Configuration

Configure in `.env` (or environment):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://idp_user:idp_secret@postgres:5432/idp_db` |
| `GEMINI_API_KEY` | Google Gemini API Key | *(required for agent)* |
| `GITHUB_TOKEN` | GitHub Personal Access Token | *(optional for GitHub MCP)* |
| `GITHUB_ORG` | Target GitHub Organization | `academic-idp` |
| `IAC_DIR` | Path to Terraform IaC workspace | `/app/iac` |
| `WORKFLOWS_DIR` | Path to GitHub Actions workflows | `/app/.github/workflows` |
| `MCP_CONFIG_PATH` | Path to MCP config file | `/app/mcp_config.json` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agent/run` | Stream agent reasoning & tool calls (SSE) |
| GET | `/api/v1/approvals/pending` | List HITL pending mutating actions |
| POST | `/api/v1/approvals/{id}/approve` | Approve and execute a pending AI action |
| POST | `/api/v1/approvals/{id}/reject` | Reject a pending AI action |
| POST | `/api/v1/projects/create` | Create a new project from form data |
| GET | `/api/v1/projects/{id}/status` | Get project deployment status |
| GET | `/api/v1/health` | Health check |

## Deployment, State & Security Considerations

### 1. Terraform Output Sanitization
All outputs from `terraform_plan`, `terraform_validate`, `terraform_init`, and `terraform_fmt` are automatically sanitized by the Terraform MCP server before being returned to the AI agent. The sanitization engine uses regular expressions to redact:
- RSA/EC/OpenSSH private keys (`[REDACTED_PRIVATE_KEY]`)
- JWT authentication tokens (`[REDACTED_JWT_TOKEN]`)
- Cloud access key IDs and secret keys (`[REDACTED_AWS_KEY]`)
- Passwords, API tokens, and credentials in key-value format (`[REDACTED_SECRET]`)
- URLs with embedded basic authentication credentials

### 2. Kubernetes Cluster Deployment in CI/CD
- **Local Development**: Uses the local Kubernetes context (`~/.kube/config`, default context `minikube` / Docker Desktop).
- **GitHub Actions CI/CD (`.github/workflows/terraform.yml`)**: GitHub Actions runners cannot access local developer kubeconfigs. To deploy to a remote Kubernetes cluster, configure the **`KUBECONFIG_DATA`** secret in the target protected GitHub Environment (`dev` or `production`). The workflow dynamically injects this kubeconfig without printing contents in logs and cleans it up after execution.

### 3. Terraform State Lifecycle
- **Local State (Academic Default)**: In local development and initial testing, Terraform uses local state files (`terraform.tfstate`) to maintain zero cloud costs.
- **CI/CD Ephemeral Runner Limitation**: When running `terraform apply` on GitHub Actions without a remote backend, state is not persisted between runner executions.
- **Persistent Production State**: For persistent multi-environment deployments, uncomment the `backend "s3"` (or GCS / Terraform Cloud) block in `iac/environments/dev/main.tf` and provide backend credentials via the `TF_BACKEND_CONFIG` environment secret.

## License

MIT
