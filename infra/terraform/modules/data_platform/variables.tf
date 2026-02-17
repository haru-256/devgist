variable "gcp_project_id" {
  type        = string
  description = "The ID for your GCP project"
}

variable "datalake_bucket_location" {
  type        = string
  description = "The location of the GCS bucket for tfstate."
  default     = "US"
}
