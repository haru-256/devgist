locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
    "iam.googleapis.com",              # IAM
    "sts.googleapis.com",              # Security Token Service (WIF)
  ]

  artifact_registries = {
    crawler = {
      description = "Docker images for the crawler job"
    }
  }

  service_account_user_members = [
    for email in var.service_account_user_emails : "user:${email}"
  ]

  cursor_wif_pool_id = "cursor"

  cursor_oidc_datalake_roles = toset([
    "roles/storage.objectViewer",
    "roles/storage.objectCreator",
  ])

  cursor_oidc_datalake_bindings = {
    for pair in setproduct(var.cursor_oidc_subjects, local.cursor_oidc_datalake_roles) :
    "${pair[0]}|${pair[1]}" => {
      subject = pair[0]
      role    = pair[1]
    }
  }

  cursor_wif_subject_prefix = "principal://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${local.cursor_wif_pool_id}/subject"

  # GitHub repository id for haru-256/devgist. Rename-safe; do not use the owner/repo string.
  github_oidc_repository_id = "1106323394"

  github_oidc_workflow_ref_prefix = "haru-256/devgist/.github/workflows/crawler-image.yml@"
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

# data-dev の datalake は箱。識別子だけ借りる。ops は identity かつ下流なので guest IAM はここ（INFRA-ADR-015）
data "terraform_remote_state" "data_dev" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-data-dev-tfstate"
  }
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
  pool_id     = local.cursor_wif_pool_id
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

module "github_wif" {
  source = "../../modules/workload_identity_oidc"

  project_id  = data.google_project.project.project_id
  pool_id     = "github"
  provider_id = "oidc"
  issuer_uri  = "https://token.actions.githubusercontent.com"
  description = "OIDC federation for GitHub Actions"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.ref"           = "assertion.ref"
    "attribute.workflow_ref"  = "assertion.workflow_ref"
  }

  attribute_condition = <<-EOT
    assertion.repository_id == "${local.github_oidc_repository_id}" &&
    assertion.environment == "production" &&
    assertion.ref == "refs/heads/main" &&
    assertion.workflow_ref.startsWith("${local.github_oidc_workflow_ref_prefix}")
  EOT

  depends_on = [module.required_project_services]
}

# GitHub Actions WIF → crawler Artifact Registry。direct resource access（INFRA-ADR-016）。
# 置き場は ops 同一 root（INFRA-ADR-015）。github-actions SA は impersonate しない。
resource "google_artifact_registry_repository_iam_member" "github_oidc_crawler_writer" {
  project    = data.google_project.project.project_id
  location   = module.artifact_registries["crawler"].location
  repository = module.artifact_registries["crawler"].repository_id
  role       = "roles/artifactregistry.writer"
  member     = "principalSet://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/github/attribute.repository_id/${local.github_oidc_repository_id}"

  depends_on = [module.github_wif]
}

# Cursor WIF → data-dev datalake。direct resource access（INFRA-ADR-014）。
# 置き場は ops × data の下流（INFRA-ADR-015）。crawler runtime SA とは別 identity
resource "google_storage_bucket_iam_member" "cursor_oidc" {
  for_each = local.cursor_oidc_datalake_bindings

  bucket = data.terraform_remote_state.data_dev.outputs.datalake_bucket_name
  role   = each.value.role
  member = "${local.cursor_wif_subject_prefix}/${each.value.subject}"
}

# 既存の GitHub Actions 用 SA。INFRA-ADR-016 の image push はこの SA を impersonate しない。
# project 全体の Artifact Registry writer と人間の actAs は残す。削除は別判断。
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
  }

  depends_on = [module.required_project_services]
}
