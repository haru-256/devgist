output "app_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the app environment"
}
