# GitHub Actions の Terraform 由来設定（INFRA-ADR-017）
resource "github_repository_environment" "dev" {
  repository  = local.github_repository_name
  environment = local.github_environment_name
}

resource "github_actions_variable" "gcp_github_wif_provider" {
  repository    = local.github_repository_name
  variable_name = "GCP_GITHUB_WIF_PROVIDER"
  value         = module.github_wif.provider_name
}

resource "github_actions_variable" "crawler_repo_url" {
  repository    = local.github_repository_name
  variable_name = "CRAWLER_REPO_URL"
  value         = module.artifact_registries["crawler"].repository_url
}

resource "github_actions_variable" "crawler_image_name" {
  repository    = local.github_repository_name
  variable_name = "CRAWLER_IMAGE_NAME"
  value         = module.artifact_registries["crawler"].repository_id
}
