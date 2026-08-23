/**
 * Development environment — consumes the k8s-namespace module
 * with dev-tier resource limits.
 */

terraform {
  required_version = ">= 1.9"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
  }

  # Uncomment to use remote state in production:
  # backend "s3" {
  #   bucket = "academic-idp-tfstate"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "kubernetes" {
  # For local development with minikube/kind:
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

# ── Namespace for the IDP platform itself ──────────────────────────
module "idp_platform" {
  source = "../../modules/k8s-namespace"

  namespace_name = "idp-platform"
  environment    = "dev"
  description    = "Academic IDP platform services (backend, frontend)"

  cpu_limit    = "4"
  memory_limit = "8Gi"
  max_pods     = "20"

  labels = {
    "idp.academic/tier" = "platform"
  }
}

# ── Example: Student project namespace ─────────────────────────────
module "student_demo" {
  source = "../../modules/k8s-namespace"

  namespace_name = "idp-student-demo"
  environment    = "dev"
  description    = "Demo student project namespace"

  cpu_limit    = "2"
  memory_limit = "4Gi"
  max_pods     = "10"

  labels = {
    "idp.academic/tier"  = "student"
    "idp.academic/owner" = "demo-student"
  }
}
