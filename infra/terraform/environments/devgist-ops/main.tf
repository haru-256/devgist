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
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

# data-dev の datalake は箱。識別子だけ借りる。ops は identity かつ下流なので guest IAM はここ（INFRA-ADR-015）
data "terraform_remote_state" "data" {
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

# Cursor WIF → data-dev datalake。direct resource access（INFRA-ADR-014）。
# 置き場は ops × data の下流（INFRA-ADR-015）。crawler runtime SA とは別 identity
resource "google_storage_bucket_iam_member" "cursor_oidc" {
  for_each = local.cursor_oidc_datalake_bindings

  bucket = data.terraform_remote_state.data.outputs.datalake_bucket_name
  role   = each.value.role
  member = "${local.cursor_wif_subject_prefix}/${each.value.subject}"
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
  }

  depends_on = [module.required_project_services]
}
