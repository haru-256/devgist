output "ops_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the ops environment"
}

output "artifact_registry_repository_ids" {
  value       = { for key, module_instance in module.artifact_registries : key => module_instance.repository_id }
  description = "Artifact Registry repository IDs keyed by repository name"
}

output "artifact_registry_repository_urls" {
  value       = { for key, module_instance in module.artifact_registries : key => module_instance.repository_url }
  description = "Docker repository URLs keyed by repository name"
}

output "crawler_artifact_registry_repository_id" {
  value       = module.artifact_registries["crawler"].repository_id
  description = "The Artifact Registry repository ID for crawler images"
}

output "crawler_artifact_registry_repository_location" {
  value       = module.artifact_registries["crawler"].location
  description = "The Artifact Registry repository location for crawler images"
}

output "crawler_artifact_registry_repository_url" {
  value       = module.artifact_registries["crawler"].repository_url
  description = "The Docker repository URL for crawler images"
}

output "github_actions_service_account_email" {
  value       = module.service_accounts.emails["github-actions"]
  description = "The email address of the GitHub Actions service account"
}

output "github_actions_service_account_member" {
  value       = module.service_accounts.members["github-actions"]
  description = "The IAM member string of the GitHub Actions service account"
}

output "ops_project_number" {
  value       = data.google_project.project.number
  description = "The GCP project number of the ops environment"
}

output "cursor_wif_pool_id" {
  value       = module.cursor_wif.pool_id
  description = "Workload identity pool ID for Cursor Cloud OIDC"
}

output "cursor_wif_provider_id" {
  value       = module.cursor_wif.provider_id
  description = "OIDC provider ID in the Cursor Cloud workload identity pool"
}

output "cursor_wif_audience" {
  value       = module.cursor_wif.audience
  description = "Default JWT audience for the Cursor Cloud OIDC provider. Mint tokens with this aud value."
}

output "github_wif_pool_id" {
  value       = module.github_wif.pool_id
  description = "Workload identity pool ID for GitHub Actions OIDC"
}

output "github_wif_provider_id" {
  value       = module.github_wif.provider_id
  description = "OIDC provider ID in the GitHub Actions workload identity pool"
}

output "github_wif_provider_name" {
  value       = module.github_wif.provider_name
  description = "Full resource name of the GitHub Actions OIDC provider. Pass this to google-github-actions/auth as workload_identity_provider."
}

output "github_wif_audience" {
  value       = module.github_wif.audience
  description = "Default JWT audience for the GitHub Actions OIDC provider. Mint tokens with this aud value."
}

output "github_wif_principal_set" {
  value       = local.github_wif_principal_set
  description = "IAM member string for the GitHub Actions federated principalSet keyed by repository. Use this when adding guest IAM for this identity."
}
