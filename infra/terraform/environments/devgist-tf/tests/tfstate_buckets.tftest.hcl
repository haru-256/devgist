mock_provider "google" {}
mock_provider "google-beta" {}

override_data {
  target = data.google_project.project
  values = {
    project_id = "haru256-devgist-tf"
  }
}

run "defines_github_tfstate_bucket" {
  command = plan

  assert {
    condition = toset(keys(module.tfstate_bucket)) == toset([
      "haru256-devgist-tf",
      "haru256-devgist-ops",
      "haru256-devgist-data-dev",
      "haru256-devgist-app-dev",
      "haru256-devgist-github",
    ])
    error_message = "Expected tfstate buckets for tf/ops/data-dev/app-dev/github from terraform.tfvars"
  }
}
