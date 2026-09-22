# ── Build stage ───────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

# Terraform version pin
ARG TERRAFORM_VERSION=1.9.8

# System dependencies & Terraform CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl unzip git && \
    curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o /tmp/terraform.zip && \
    unzip /tmp/terraform.zip -d /usr/local/bin/ && \
    rm /tmp/terraform.zip && \
    chmod +x /usr/local/bin/terraform && \
    apt-get purge -y --auto-remove unzip && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# ── Production ────────────────────────────────────────────────────
FROM base AS production
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Development (with hot reload) ────────────────────────────────
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
