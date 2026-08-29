variable "project_id" {
  type        = string
  description = "The GCP project ID where the Artifact Registry repository is created."
}

variable "location" {
  type        = string
  description = "The regional location for the Artifact Registry repository."
}

variable "repository_id" {
  type        = string
  description = "The Artifact Registry repository ID."
}

variable "description" {
  type        = string
  description = "The description for the Artifact Registry repository."
  default     = ""
}

variable "cleanup_keep_count" {
  type        = number
  description = "Minimum number of most recent package versions to keep per package (INFRA-ADR-018)."
  default     = 5

  validation {
    condition     = var.cleanup_keep_count >= 1
    error_message = "cleanup_keep_count must be at least 1."
  }
}

variable "cleanup_delete_older_than" {
  type        = string
  description = "Delete versions older than this duration unless kept by keep-minimum-versions (e.g. \"30d\")."
  default     = "30d"

  validation {
    condition     = can(regex("^[0-9]+[smhd]$", var.cleanup_delete_older_than))
    error_message = "cleanup_delete_older_than must be a duration like \"30d\", \"48h\", \"60m\", or \"3600s\"."
  }
}

variable "cleanup_policy_dry_run" {
  type        = bool
  description = "When true, cleanup policies log candidates without deleting (INFRA-ADR-018)."
  default     = false
}
