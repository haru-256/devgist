output "app_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the app environment"
}

output "crawler_service_account_email" {
  value       = module.service_accounts.emails["crawler"]
  description = "The email address of the crawler dev service account"
}

output "crawler_service_account_member" {
  value       = module.service_accounts.members["crawler"]
  description = "The IAM member string of the crawler dev service account"
}
