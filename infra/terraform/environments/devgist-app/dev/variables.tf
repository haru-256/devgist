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

variable "crawler_conference_names" {
  type        = string
  description = "Comma-separated conference names for the crawler Cloud Run Job."
  default     = "recsys,kdd,wsdm,www,sigir,cikm"

  validation {
    condition = alltrue([
      for name in split(",", trimspace(var.crawler_conference_names)) :
      contains(["recsys", "kdd", "wsdm", "www", "sigir", "cikm"], lower(trimspace(name)))
    ])
    error_message = "crawler_conference_names must be a comma-separated list of known conference names: recsys,kdd,wsdm,www,sigir,cikm."
  }
}

variable "cursor_oidc_subjects" {
  type        = set(string)
  description = "Cursor OIDC subject claims allowed to access the data-dev datalake via WIF direct resource access. Empty means no federated principal gets GCS IAM. Set this in the gitignored terraform.tfvars."
  default     = []

  validation {
    condition = alltrue([
      for sub in var.cursor_oidc_subjects :
      can(regex("^(user|service_account):.+$", sub))
    ])
    error_message = "Each cursor_oidc_subjects value must start with \"user:\" or \"service_account:\"."
  }
}
