output "pool_id" {
  description = "The workload identity pool ID."
  value       = google_iam_workload_identity_pool.pool.workload_identity_pool_id
}

output "provider_id" {
  description = "The workload identity pool provider ID."
  value       = google_iam_workload_identity_pool_provider.oidc.workload_identity_pool_provider_id
}

output "pool_name" {
  description = "The full resource name of the workload identity pool."
  value       = google_iam_workload_identity_pool.pool.name
}

output "provider_name" {
  description = "The full resource name of the OIDC provider."
  value       = google_iam_workload_identity_pool_provider.oidc.name
}

output "audience" {
  description = "Default JWT audience for this provider. Mint OIDC tokens with this aud value."
  value       = "https://iam.googleapis.com/${google_iam_workload_identity_pool_provider.oidc.name}"
}

output "issuer_uri" {
  description = "OIDC issuer URI of this provider."
  value       = google_iam_workload_identity_pool_provider.oidc.oidc[0].issuer_uri
}

output "attribute_condition" {
  description = "CEL condition that tokens must satisfy."
  value       = google_iam_workload_identity_pool_provider.oidc.attribute_condition
}
