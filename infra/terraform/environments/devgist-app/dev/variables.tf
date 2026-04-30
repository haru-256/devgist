variable "gcp_project_id" {
  type        = string
  description = "The ID of GCP project"
}

variable "gcp_default_region" {
  type        = string
  description = "The name of GCP default region"
}

variable "service_account_user_emails" {
  type        = set(string)
  description = "Email addresses of users allowed to attach / actAs managed service accounts."
  default     = []

  validation {
    condition = alltrue([
      for email in var.service_account_user_emails :
      can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", email))
    ])
    error_message = "Each service account user email must be a valid email address."
  }
}

variable "crawler_image" {
  type        = string
  description = "Container image digest for the crawler Cloud Run Job (e.g. us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@sha256:...)"

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.crawler_image))
    error_message = "crawler_image must be an immutable digest reference ending with @sha256:<64 lowercase hex chars>."
  }
}
