mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id    = "ops"
  location      = "us-central1"
  repository_id = "crawler"
  description   = "Docker images for the crawler job"
}

run "disables_vulnerability_scanning" {
  command = plan

  assert {
    condition = (
      google_artifact_registry_repository.repository.vulnerability_scanning_config[0].enablement_config
      == "DISABLED"
    )
    error_message = "Expected Artifact Registry vulnerability scanning to be DISABLED"
  }
}

run "keeps_recent_versions_and_deletes_old" {
  command = plan

  assert {
    condition     = google_artifact_registry_repository.repository.cleanup_policy_dry_run == false
    error_message = "Expected cleanup policies to run actively (dry_run=false)"
  }

  assert {
    condition = anytrue([
      for policy in google_artifact_registry_repository.repository.cleanup_policies :
      policy.id == "keep-minimum-versions" &&
      policy.action == "KEEP" &&
      try(policy.most_recent_versions[0].keep_count, 0) == 5
    ])
    error_message = "Expected KEEP policy keep-minimum-versions with keep_count=5"
  }

  assert {
    condition = anytrue([
      for policy in google_artifact_registry_repository.repository.cleanup_policies :
      policy.id == "delete-older-than" &&
      policy.action == "DELETE" &&
      try(policy.condition[0].older_than, "") == "30d" &&
      try(policy.condition[0].tag_state, "") == "ANY"
    ])
    error_message = "Expected DELETE policy delete-older-than with older_than=30d and tag_state=ANY"
  }
}
