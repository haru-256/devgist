mock_provider "google" {}
mock_provider "google-beta" {}
mock_provider "github" {}

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

run "write_github_actions_config_from_ops" {
  command = plan

  assert {
    condition     = github_repository_environment.dev.environment == "dev"
    error_message = "Expected ops Terraform to manage GitHub Environment dev"
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
    error_message = "Expected GCP_GITHUB_WIF_PROVIDER to be a repository variable written by ops"
  }

  assert {
    condition     = github_actions_variable.crawler_repo_url.repository == "devgist"
    error_message = "Expected crawler image variables to be repository variables, not environment variables"
  }
}
