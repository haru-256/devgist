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

output "crawler_artifact_registry_repository_url" {
  value       = module.artifact_registries["crawler"].repository_url
  description = "The Docker repository URL for crawler images"
}
