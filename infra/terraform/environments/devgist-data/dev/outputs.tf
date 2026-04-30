output "datalake_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the data environment"
}

output "datalake_bucket_name" {
  description = "Name of the datalake GCS bucket"
  value       = module.data_platform.datalake_bucket_name
}
