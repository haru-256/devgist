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
    condition     = github_repository_environment.dev.repository == "devgist"
    error_message = "Expected GitHub Environment dev to belong to this repository"
  }

  assert {
    condition     = github_repository_environment.dev.environment == local.github_environment_name
    error_message = "Expected GitHub Environment name to match the WIF IAM environment attribute"
  }

  assert {
    condition     = github_actions_variable.ops["CRAWLER_REPO_URL"].value == "us-central1-docker.pkg.dev/ops/crawler"
    error_message = "Expected CRAWLER_REPO_URL to come from the crawler Artifact Registry URL"
  }

  assert {
    condition     = github_actions_variable.ops["CRAWLER_IMAGE_NAME"].value == "crawler"
    error_message = "Expected CRAWLER_IMAGE_NAME to match the crawler Artifact Registry repository id"
  }

  assert {
    condition     = github_actions_variable.ops["GCP_GITHUB_WIF_PROVIDER"].variable_name == "GCP_GITHUB_WIF_PROVIDER"
    error_message = "Expected GCP_GITHUB_WIF_PROVIDER to be a repository variable written by ops"
  }

  assert {
    condition     = length(github_actions_variable.ops) == 3
    error_message = "Expected ops to write exactly the WIF provider and crawler image repository variables"
  }

  assert {
    condition     = github_actions_variable.ops["CRAWLER_REPO_URL"].repository == "devgist"
    error_message = "Expected crawler image variables to be repository variables, not environment variables"
  }
}
