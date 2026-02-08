output "tfstate_bucket_id" {
  value       = module.tfstate_bucket.tfstate_gcs_bucket_id
  description = "The ID of the bucket used to store terraform state"
}
