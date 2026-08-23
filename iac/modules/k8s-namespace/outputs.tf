/**
 * Outputs from the k8s-namespace module.
 */

output "namespace_name" {
  description = "The name of the created Kubernetes namespace"
  value       = kubernetes_namespace.this.metadata[0].name
}

output "namespace_uid" {
  description = "The UID of the created namespace"
  value       = kubernetes_namespace.this.metadata[0].uid
}

output "quota_name" {
  description = "The name of the ResourceQuota (if created)"
  value       = var.enable_resource_quota ? kubernetes_resource_quota.this[0].metadata[0].name : null
}

output "limit_range_name" {
  description = "The name of the LimitRange (if created)"
  value       = var.enable_limit_range ? kubernetes_limit_range.this[0].metadata[0].name : null
}
