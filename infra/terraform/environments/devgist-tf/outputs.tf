output "tfstate_buckets" {
  value = [for key, bucket in module.tfstate_bucket : {
    project_id = key
    bucket_id  = bucket.tfstate_gcs_bucket_id
  }]
  description = "List of all tfstate buckets with their project IDs"
}

output "tf_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID that hosts the tfstate buckets. Downstream roots grant CI project IAM here (INFRA-ADR-019)"
}
