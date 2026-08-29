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

variable "github_repository_owner" {
  type        = string
  description = "GitHub user or organization that owns the repository. Cursor OIDC repo_url is github.com/<owner>/<name>."
  default     = "haru-256"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository_owner))
    error_message = "github_repository_owner must be a GitHub login."
  }
}

variable "github_repository_name" {
  type        = string
  description = "GitHub repository name without the owner. Cursor OIDC repo_url is github.com/<owner>/<name>."
  default     = "devgist"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository_name))
    error_message = "github_repository_name must be a GitHub repository name."
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
