# GitHub Actions の Terraform 由来設定（INFRA-ADR-017）
locals {
  github_actions_variables = {
    GCP_GITHUB_WIF_PROVIDER = module.github_wif.provider_name
    CRAWLER_REPO_URL        = module.artifact_registries["crawler"].repository_url
    CRAWLER_IMAGE_NAME      = module.artifact_registries["crawler"].repository_id
  }
}

resource "github_repository_environment" "dev" {
  repository  = local.github_repository_name
  environment = local.github_environment_name
}

resource "github_actions_variable" "ops" {
  for_each = local.github_actions_variables

  repository    = local.github_repository_name
  variable_name = each.key
  value         = each.value
}
