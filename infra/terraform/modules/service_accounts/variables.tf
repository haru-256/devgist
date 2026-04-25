variable "project_id" {
  description = "Project ID where service accounts are created."
  type        = string
}

variable "prefix" {
  description = "Prefix for service account IDs."
  type        = string
  default     = ""
}

variable "service_accounts" {
  description = <<EOT
Service accounts and IAM settings.

- project_roles:
  Roles granted to this service account on projects.
  This controls what the service account can do.

- token_creators:
  Members allowed to impersonate this service account by creating short-lived tokens.
  Usually used for GitHub Actions WIF, human break-glass users, or deployer SAs.

- service_account_users:
  Members allowed to attach / actAs this service account.
  Usually used by deployer identities for Cloud Run, GCE, Cloud Functions, etc.
EOT

  type = map(object({
    description = optional(string)

    project_roles = optional(list(object({
      project = string
      role    = string
    })), [])

    token_creators = optional(list(string), [])

    service_account_users = optional(list(string), [])
  }))

  default = {}
}
