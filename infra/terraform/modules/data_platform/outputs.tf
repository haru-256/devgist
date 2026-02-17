output "datalake_bucket_name" {
  description = "Name of the datalake GCS bucket"
  value       = google_storage_bucket.datalake.name
}

output "datalake_bucket_id" {
  description = "ID of the datalake GCS bucket"
  value       = google_storage_bucket.datalake.id
}

output "datalake_bucket_self_link" {
  description = "Self link of the datalake GCS bucket"
  value       = google_storage_bucket.datalake.self_link
}
