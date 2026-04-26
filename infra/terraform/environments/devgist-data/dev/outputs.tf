output "datalake_bucket_name" {
  description = "Name of the datalake GCS bucket"
  value       = module.data_platform.datalake_bucket_name
}
