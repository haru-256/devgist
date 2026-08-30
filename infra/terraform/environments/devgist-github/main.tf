# GitHub リソース（Environment、repository variable、repository secret）を
# 管理する root（INFRA-ADR-019）。
#
# 変更頻度が低く、CI に載せるには GitHub App の PEM のような長寿命の秘密を
# CI に置く必要があるため、plan / apply はローカルに限定する。
# 認証は apply する人の GITHUB_TOKEN（INFRA-ADR-017 の手元運用）。
# CI の workflow はこの root を対象にしない（.github/workflows/terraform-plan.yml /
# terraform-apply.yml の deploy 対象外）。
#
# state bucket は haru256-devgist-github-tfstate。使う前に devgist-tf の
# tfstate_gcp_project_ids に haru256-devgist-github を足して tf を apply すること。
# repository secret の正本は gitignore 済み secrets.auto.tfvars。GitHub UI からは作らない。

locals {
  github_repository_owner = "haru-256"
  github_repository_name  = "devgist"

  # Actions の TF_VAR_* が set(string) として読める JSON。順序を固定して drift を防ぐ
  cursor_oidc_subjects_secret_value        = jsonencode(sort(tolist(var.cursor_oidc_subjects)))
  service_account_user_emails_secret_value = jsonencode(sort(tolist(var.service_account_user_emails)))
}

# ops の Terraform state から GitHub Actions 連携に必要な値を参照する（INFRA-ADR-006）
data "terraform_remote_state" "ops" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-ops-tfstate"
  }
}

# GitHub Actions の Terraform 由来設定（INFRA-ADR-017）。
# Environment は OIDC claim と IAM の契約ではなくなった（INFRA-ADR-019）が、
# deployment 履歴と将来の protection の器として維持する
resource "github_repository_environment" "dev" {
  repository  = local.github_repository_name
  environment = "dev"
}

resource "github_actions_variable" "gcp_github_wif_provider" {
  repository    = local.github_repository_name
  variable_name = "GCP_GITHUB_WIF_PROVIDER"
  value         = data.terraform_remote_state.ops.outputs.github_wif_provider_name
}

resource "github_actions_variable" "crawler_repo_url" {
  repository    = local.github_repository_name
  variable_name = "CRAWLER_REPO_URL"
  value         = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_url
}

resource "github_actions_variable" "crawler_image_name" {
  repository    = local.github_repository_name
  variable_name = "CRAWLER_IMAGE_NAME"
  value         = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_id
}

# CI の terraform plan / apply が ops / app-dev に渡す TF_VAR_* の器（INFRA-ADR-019）。
# GitHub API は secret 値を読めないので、正本は secrets.auto.tfvars。state に plaintext が残るが、
# この root の state は CI から読まない。
resource "github_actions_secret" "cursor_oidc_subjects" {
  repository  = local.github_repository_name
  secret_name = "CURSOR_OIDC_SUBJECTS"
  value       = local.cursor_oidc_subjects_secret_value
}

resource "github_actions_secret" "service_account_user_emails" {
  repository  = local.github_repository_name
  secret_name = "SERVICE_ACCOUNT_USER_EMAILS"
  value       = local.service_account_user_emails_secret_value
}
