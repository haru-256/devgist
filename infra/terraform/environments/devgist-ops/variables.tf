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
  description = "Email addresses of users allowed to attach / actAs managed service accounts. No default on purpose: set it in the gitignored secrets.auto.tfvars (local) or TF_VAR_service_account_user_emails (CI; repository secret written by the devgist-github root) so that an unset value fails instead of wiping grants (INFRA-ADR-019)."

  validation {
    condition = alltrue([
      for email in var.service_account_user_emails :
      can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", email))
    ])
    error_message = "Each service account user email must be a valid email address."
  }
}

variable "cursor_oidc_subjects" {
  type        = set(string)
  description = "Cursor OIDC subject claims allowed to access the data-dev datalake via WIF direct resource access. Empty means no federated principal gets GCS IAM. No default on purpose: set it in the gitignored secrets.auto.tfvars (local) or TF_VAR_cursor_oidc_subjects (CI; repository secret written by the devgist-github root) so that an unset value fails instead of wiping grants (INFRA-ADR-019)."

  validation {
    condition = alltrue([
      for sub in var.cursor_oidc_subjects :
      can(regex("^(user|service_account):.+$", sub))
    ])
    error_message = "Each cursor_oidc_subjects value must start with \"user:\" or \"service_account:\"."
  }
}
