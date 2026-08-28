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

variable "cursor_oidc_repo_url" {
  type        = string
  description = "GitHub repository URL claim that Cursor OIDC tokens must match (host/owner/repo, no scheme)."
  default     = "github.com/haru-256/devgist"

  validation {
    condition     = can(regex("^github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.cursor_oidc_repo_url))
    error_message = "cursor_oidc_repo_url must look like github.com/owner/repo without a scheme."
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
