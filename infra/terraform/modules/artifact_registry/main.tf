resource "google_artifact_registry_repository" "repository" {
  project       = var.project_id
  location      = var.location
  repository_id = var.repository_id
  description   = var.description
  format        = "DOCKER"

  # INFRA-ADR-018: never inherit project-level Container Scanning.
  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }

  # INFRA-ADR-018: KEEP wins over DELETE for matching versions.
  cleanup_policy_dry_run = var.cleanup_policy_dry_run

  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = var.cleanup_keep_count
    }
  }

  cleanup_policies {
    id     = "delete-older-than"
    action = "DELETE"

    condition {
      tag_state  = "ANY"
      older_than = var.cleanup_delete_older_than
    }
  }
}
