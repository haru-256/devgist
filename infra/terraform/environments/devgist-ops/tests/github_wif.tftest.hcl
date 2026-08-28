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
    condition     = google_artifact_registry_repository_iam_member.github_oidc_crawler_writer.member == "principalSet://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/github-devgist/attribute.environment/dev"
    error_message = "Expected GitHub OIDC writer member to be the environment principalSet"
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
    condition     = module.github_wif.pool_id == "github-devgist"
    error_message = "Expected GitHub WIF pool id to be github-devgist"
  }

  assert {
    condition     = module.github_wif.provider_id == "oidc"
    error_message = "Expected GitHub WIF provider id to be oidc"
  }

  assert {
    condition     = local.github_oidc_attribute_mapping["attribute.environment"] == "assertion.environment"
    error_message = "Expected GitHub WIF to map the environment claim used in IAM"
  }

  assert {
    condition     = strcontains(local.github_oidc_attribute_condition, "assertion.repository_id == \"1106323394\"")
    error_message = "Expected GitHub WIF condition to require this repository id"
  }

  assert {
    condition     = !strcontains(local.github_oidc_attribute_condition, "assertion.environment")
    error_message = "Expected GitHub WIF condition not to pin environment; IAM uses attribute.environment"
  }

  assert {
    condition     = !strcontains(local.github_oidc_attribute_condition, "assertion.workflow_ref")
    error_message = "Expected GitHub WIF condition not to pin a workflow; this pool is for the whole repository"
  }

  assert {
    condition     = !contains(keys(local.github_oidc_attribute_mapping), "attribute.workflow_ref")
    error_message = "Expected GitHub WIF not to map workflow_ref when it is unused in condition and IAM"
  }
}
