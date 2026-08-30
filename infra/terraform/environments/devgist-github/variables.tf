variable "service_account_user_emails" {
  type        = set(string)
  sensitive   = true
  description = "Email addresses of users allowed to attach / actAs managed service accounts. Written to repository secret SERVICE_ACCOUNT_USER_EMAILS as JSON for TF_VAR_service_account_user_emails in CI (INFRA-ADR-019). Set in the gitignored secrets.tfvars. No default on purpose: an unset value fails instead of wiping the secret."

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
  sensitive   = true
  description = "Cursor OIDC subject claims allowed to access the data-dev datalake via WIF direct resource access. Written to repository secret CURSOR_OIDC_SUBJECTS as JSON for TF_VAR_cursor_oidc_subjects in CI (INFRA-ADR-019). Set in the gitignored secrets.tfvars. No default on purpose: an unset value fails instead of wiping the secret."

  validation {
    condition = alltrue([
      for sub in var.cursor_oidc_subjects :
      can(regex("^(user|service_account):.+$", sub))
    ])
    error_message = "Each cursor_oidc_subjects value must start with \"user:\" or \"service_account:\"."
  }
}
