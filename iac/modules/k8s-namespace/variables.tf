/**
 * Input variables for the k8s-namespace module.
 */

# ── Core ───────────────────────────────────────────────────────────
variable "namespace_name" {
  description = "Name of the Kubernetes namespace to create"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", var.namespace_name))
    error_message = "Namespace name must be a valid DNS label (lowercase, hyphens, 3-63 chars)."
  }
}

variable "environment" {
  description = "Environment label (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "description" {
  description = "Human-readable description of the namespace purpose"
  type        = string
  default     = "Managed by Academic IDP"
}

variable "labels" {
  description = "Additional labels to apply to the namespace"
  type        = map(string)
  default     = {}
}

# ── Resource Quota ─────────────────────────────────────────────────
variable "enable_resource_quota" {
  description = "Whether to create a ResourceQuota in the namespace"
  type        = bool
  default     = true
}

variable "cpu_request_limit" {
  description = "Total CPU requests allowed across all pods"
  type        = string
  default     = "2"
}

variable "memory_request_limit" {
  description = "Total memory requests allowed across all pods"
  type        = string
  default     = "4Gi"
}

variable "cpu_limit" {
  description = "Total CPU limits allowed across all pods"
  type        = string
  default     = "4"
}

variable "memory_limit" {
  description = "Total memory limits allowed across all pods"
  type        = string
  default     = "8Gi"
}

variable "max_pods" {
  description = "Maximum number of pods in the namespace"
  type        = string
  default     = "20"
}

variable "max_services" {
  description = "Maximum number of services"
  type        = string
  default     = "10"
}

variable "max_pvcs" {
  description = "Maximum number of PersistentVolumeClaims"
  type        = string
  default     = "5"
}

# ── Limit Range ────────────────────────────────────────────────────
variable "enable_limit_range" {
  description = "Whether to create a LimitRange in the namespace"
  type        = bool
  default     = true
}

variable "default_container_cpu_request" {
  description = "Default CPU request per container"
  type        = string
  default     = "100m"
}

variable "default_container_memory_request" {
  description = "Default memory request per container"
  type        = string
  default     = "128Mi"
}

variable "default_container_cpu_limit" {
  description = "Default CPU limit per container"
  type        = string
  default     = "500m"
}

variable "default_container_memory_limit" {
  description = "Default memory limit per container"
  type        = string
  default     = "512Mi"
}

variable "max_container_cpu" {
  description = "Maximum CPU a single container can request"
  type        = string
  default     = "2"
}

variable "max_container_memory" {
  description = "Maximum memory a single container can request"
  type        = string
  default     = "4Gi"
}
