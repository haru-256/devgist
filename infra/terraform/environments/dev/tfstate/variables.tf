variable "gcp_project_id" {
  type        = string
  description = "The ID of GCP project"
}

variable "gcp_default_region" {
  type        = string
  description = "The name of GCP default region"
}

variable "tfstate_gcp_project_ids" {
  type        = list(string)
  description = "A list of GCP project IDs for which to create tfstate buckets."
}
