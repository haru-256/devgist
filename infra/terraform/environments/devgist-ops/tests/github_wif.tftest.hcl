mock_provider "google" {}
mock_provider "google-beta" {}

override_data {
  target = data.google_project.project
  values = {
    project_id = "ops"
    number     = "123456789"
  }
}

override_data {
  target = data.terraform_remote_state.data_dev
  values = {
    outputs = {
      datalake_bucket_name = "mock-datalake-bucket"
      datalake_project_id  = "mock-data-project"
    }
  }
}

variables {
  gcp_project_id     = "ops"
  gcp_default_region = "us-central1"
}

run "grant_github_oidc_crawler_writer" {
  command = plan

  assert {
    condition     = google_artifact_registry_repository_iam_member.github_oidc_crawler_writer.member == "principalSet://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/github/attribute.repository/haru-256/devgist"
    error_message = "Expected GitHub OIDC writer member to be the repository principalSet"
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.github_oidc_crawler_writer.role == "roles/artifactregistry.writer"
    error_message = "Expected GitHub OIDC IAM role to be artifactregistry.writer"
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.github_oidc_crawler_writer.repository == "crawler"
    error_message = "Expected GitHub OIDC writer on the crawler Artifact Registry repository"
  }

  assert {
    condition     = module.github_wif.pool_id == "github"
    error_message = "Expected GitHub WIF pool id to be github"
  }

  assert {
    condition     = module.github_wif.provider_id == "oidc"
    error_message = "Expected GitHub WIF provider id to be oidc"
  }
}
