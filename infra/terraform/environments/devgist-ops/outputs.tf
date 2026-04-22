output "ops_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the ops environment"
}

output "crawler_artifact_registry_repository_id" {
  value       = module.crawler_artifact_registry.repository_id
  description = "The Artifact Registry repository ID for crawler images"
}

output "crawler_artifact_registry_repository_url" {
  value       = module.crawler_artifact_registry.repository_url
  description = "The Docker repository URL for crawler images"
}
