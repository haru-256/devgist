mock_provider "github" {}

override_data {
  target = data.terraform_remote_state.ops
  values = {
    outputs = {
      github_wif_provider_name                      = "projects/123456789/locations/global/workloadIdentityPools/github-devgist/providers/oidc"
      crawler_artifact_registry_repository_url      = "us-central1-docker.pkg.dev/ops/crawler"
      crawler_artifact_registry_repository_id       = "crawler"
      crawler_artifact_registry_repository_location = "us-central1"
    }
  }
}

run "write_github_actions_config_from_github_root" {
  command = plan

  assert {
    condition     = github_repository_environment.dev.environment == "dev"
    error_message = "Expected github root Terraform to manage GitHub Environment dev"
  }

  assert {
    condition     = local.github_repository_owner == "haru-256" && local.github_repository_name == "devgist"
    error_message = "Expected GitHub repository identity to be locals for this root, not input variables"
  }

  assert {
    condition     = github_repository_environment.dev.repository == "devgist"
    error_message = "Expected GitHub Environment dev to belong to this repository"
  }

  assert {
    condition     = github_actions_variable.crawler_repo_url.value == "us-central1-docker.pkg.dev/ops/crawler"
    error_message = "Expected CRAWLER_REPO_URL to come from the crawler Artifact Registry URL"
  }

  assert {
    condition     = github_actions_variable.crawler_image_name.value == "crawler"
    error_message = "Expected CRAWLER_IMAGE_NAME to match the crawler Artifact Registry repository id"
  }

  assert {
    condition     = github_actions_variable.gcp_github_wif_provider.variable_name == "GCP_GITHUB_WIF_PROVIDER"
    error_message = "Expected GCP_GITHUB_WIF_PROVIDER to be a repository variable written by the github root"
  }

  assert {
    condition     = github_actions_variable.gcp_github_wif_provider.value == "projects/123456789/locations/global/workloadIdentityPools/github-devgist/providers/oidc"
    error_message = "Expected GCP_GITHUB_WIF_PROVIDER to come from the ops remote state"
  }

  assert {
    condition     = github_actions_variable.crawler_repo_url.repository == "devgist"
    error_message = "Expected crawler image variables to be repository variables, not environment variables"
  }
}
