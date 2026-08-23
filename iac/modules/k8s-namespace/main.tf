/**
 * Terraform Module: k8s-namespace
 *
 * Provisions a Kubernetes namespace with:
 *   - Resource Quota (CPU, Memory, Pods)
 *   - Limit Range (default container requests/limits)
 *   - Configurable labels and annotations
 */

terraform {
  required_version = ">= 1.9"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
  }
}

# ── Namespace ──────────────────────────────────────────────────────
resource "kubernetes_namespace" "this" {
  metadata {
    name = var.namespace_name

    labels = merge(
      {
        "app.kubernetes.io/managed-by" = "academic-idp"
        "idp.academic/environment"     = var.environment
      },
      var.labels,
    )

    annotations = {
      "idp.academic/created-by"  = "terraform"
      "idp.academic/description" = var.description
    }
  }
}

# ── Resource Quota ─────────────────────────────────────────────────
resource "kubernetes_resource_quota" "this" {
  count = var.enable_resource_quota ? 1 : 0

  metadata {
    name      = "${var.namespace_name}-quota"
    namespace = kubernetes_namespace.this.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = var.cpu_request_limit
      "requests.memory" = var.memory_request_limit
      "limits.cpu"      = var.cpu_limit
      "limits.memory"   = var.memory_limit
      "pods"            = var.max_pods
      "services"        = var.max_services
      "persistentvolumeclaims" = var.max_pvcs
    }
  }
}

# ── Limit Range (sensible defaults for every container) ────────────
resource "kubernetes_limit_range" "this" {
  count = var.enable_limit_range ? 1 : 0

  metadata {
    name      = "${var.namespace_name}-limits"
    namespace = kubernetes_namespace.this.metadata[0].name
  }

  spec {
    limit {
      type = "Container"

      default = {
        cpu    = var.default_container_cpu_limit
        memory = var.default_container_memory_limit
      }

      default_request = {
        cpu    = var.default_container_cpu_request
        memory = var.default_container_memory_request
      }

      max = {
        cpu    = var.max_container_cpu
        memory = var.max_container_memory
      }
    }
  }
}
