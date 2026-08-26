locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
    "iam.googleapis.com",              # IAM
    "sts.googleapis.com",              # Security Token Service (WIF)
    "iamcredentials.googleapis.com",   # IAM Credentials (SA impersonation)
  ]

  artifact_registries = {
    crawler = {
      description = "Docker images for the crawler job"
    }
  }

  service_account_user_members = [
    for email in var.service_account_user_emails : "user:${email}"
  ]

  # Cursor OIDC の sub を WIF federated principal に変換する。
  # allowlist が空なら impersonate できる member は無い。
  cursor_cloud_workload_identity_users = [
    for sub in var.cursor_oidc_subjects :
    "principal://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${module.cursor_wif.pool_id}/subject/${sub}"
  ]
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

module "required_project_services" {
  source = "../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}

// project 内で利用する Docker 用 Artifact Registry を作成
module "artifact_registries" {
  for_each = local.artifact_registries

  source = "../../modules/artifact_registry"

  project_id    = data.google_project.project.project_id
  location      = var.gcp_default_region
  repository_id = each.key
  description   = each.value.description

  depends_on = [module.required_project_services]
}

module "cursor_wif" {
  source = "../../modules/workload_identity_oidc"

  project_id  = data.google_project.project.project_id
  pool_id     = "cursor"
  provider_id = "oidc"
  issuer_uri  = "https://api.cursor.com"
  description = "OIDC federation for Cursor Cloud Agent"

  attribute_mapping = {
    "google.subject"    = "assertion.sub"
    "attribute.repo"    = "assertion.repo_url"
    "attribute.runtime" = "assertion.agent_runtime"
  }

  attribute_condition = "assertion.repo_url == \"${var.cursor_oidc_repo_url}\" && assertion.agent_runtime == \"managed\""

  depends_on = [module.required_project_services]
}

module "service_accounts" {
  source = "../../modules/service_accounts"

  project_id = data.google_project.project.project_id

  service_accounts = {
    github-actions = {
      description = "Service account used by GitHub Actions for DevGist CI/CD"

      project_roles = [
        {
          project = data.google_project.project.project_id
          role    = "roles/artifactregistry.writer"
        }
      ]

      service_account_users = local.service_account_user_members
    }

    cursor-cloud = {
      description = "Service account impersonated by Cursor Cloud Agent via Workload Identity Federation"

      # datalake IAM は app-dev 側で付与する。ops は data の remote state を読まない。
      service_account_users   = local.service_account_user_members
      workload_identity_users = local.cursor_cloud_workload_identity_users
    }
  }

  depends_on = [module.required_project_services]
}
