variable "bucket_gcp_project_id" {
  type        = string
  description = "The ID of the GCP project where the GCS bucket for tfstate will be created."
}

variable "tfstate_gcp_project_id" {
  type        = string
  description = "The ID of the GCP project to be managed by Terraform."
}

variable "bucket_location" {
  type        = string
  description = "The location of the GCS bucket for tfstate."
  default     = "US"
}
