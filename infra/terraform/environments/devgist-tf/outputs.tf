output "tfstate_buckets" {
  value = [for key, bucket in module.tfstate_bucket : {
    project_id = key
    bucket_id  = bucket.tfstate_gcs_bucket_id
  }]
  description = "List of all tfstate buckets with their project IDs"
}
