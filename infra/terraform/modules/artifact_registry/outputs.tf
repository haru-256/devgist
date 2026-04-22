output "repository_id" {
  description = "The Artifact Registry repository ID."
  value       = google_artifact_registry_repository.repository.repository_id
}

output "name" {
  description = "The full resource name of the Artifact Registry repository."
  value       = google_artifact_registry_repository.repository.name
}

output "location" {
  description = "The Artifact Registry repository location."
  value       = google_artifact_registry_repository.repository.location
}

output "repository_url" {
  description = "The Docker push URL for the Artifact Registry repository."
  value       = "${google_artifact_registry_repository.repository.location}-docker.pkg.dev/${google_artifact_registry_repository.repository.project}/${google_artifact_registry_repository.repository.repository_id}"
}
