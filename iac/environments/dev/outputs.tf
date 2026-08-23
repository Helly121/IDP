/**
 * Outputs for the dev environment.
 */

output "platform_namespace" {
  value = module.idp_platform.namespace_name
}

output "student_demo_namespace" {
  value = module.student_demo.namespace_name
}
