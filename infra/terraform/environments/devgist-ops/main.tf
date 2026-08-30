locals {
  cursor_wif_pool_id      = "cursor"
  github_wif_pool_id      = "github-devgist"
  github_repository_owner = "haru-256"
  github_repository_name  = "devgist"

  # INFRA-ADR-019: GitHub Actions CI の認可単位（operation × environment）
  ci_scope_terraform_plan_dev  = "terraform-plan-dev"
  ci_scope_terraform_apply_dev = "terraform-apply-dev"
  ci_scope_crawler_push_dev    = "crawler-push-dev"

  github_ci_principal_set_prefix = "principalSet://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${local.github_wif_pool_id}/attribute.ci_scope"

  # CI apply が state を read/write する root の tfstate bucket キー
  # （devgist-tf の tfstate_gcp_project_ids の要素）。tf 自身と devgist-github root の state は CI に載せない
  ci_deploy_state_bucket_keys = toset([
    "haru256-devgist-ops",
    "haru256-devgist-data-dev",
    "haru256-devgist-app-dev",
  ])

  tfstate_buckets        = data.terraform_remote_state.tf.outputs.tfstate_buckets
  all_tfstate_bucket_ids = toset([for bucket in local.tfstate_buckets : bucket.bucket_id])
  ci_deploy_state_bucket_ids = toset([
    for bucket in local.tfstate_buckets : bucket.bucket_id
    if contains(local.ci_deploy_state_bucket_keys, bucket.project_id)
  ])
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

# tfstate bucket の識別子と tf project id を借りる。tf は最上流なので循環しない（INFRA-ADR-015 / INFRA-ADR-019）
data "terraform_remote_state" "tf" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-tf-tfstate"
  }
}

module "required_project_services" {
  source = "../../modules/google_project_services"

  project_id = data.google_project.project.project_id
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
    "iam.googleapis.com",              # IAM
    "sts.googleapis.com",              # Security Token Service (WIF)
  ]
  wait_seconds = 30
}

// project 内で利用する Docker 用 Artifact Registry を作成
module "artifact_registries" {
  for_each = {
    crawler = {
      description = "Docker images for the crawler job"
    }
  }

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

  attribute_condition = "assertion.repo_url == \"github.com/${local.github_repository_owner}/${local.github_repository_name}\" && assertion.agent_runtime == \"managed\""

  depends_on = [module.required_project_services]
}

# INFRA-ADR-016（認証モデル）/ INFRA-ADR-019（ci_scope による認可）
module "github_wif" {
  source = "../../modules/workload_identity_oidc"

  project_id  = data.google_project.project.project_id
  pool_id     = local.github_wif_pool_id
  provider_id = "oidc"
  issuer_uri  = "https://token.actions.githubusercontent.com"
  description = "OIDC federation for GitHub Actions"

  # ci_scope は GitHub が署名した claim から合成する。workflow の YAML が名乗る文字列ではない。
  # environment は optional claim なので has() で guard する。
  # apply 系は environment も条件に含め、GitHub Environment の protection（prod の承認）と identity を結合する。
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ci_scope"            = <<-EOT
      assertion.workflow_ref == assertion.repository + "/.github/workflows/terraform-apply.yml@refs/heads/main" &&
      assertion.event_name == "push" &&
      assertion.ref == "refs/heads/main" &&
      has(assertion.environment) && assertion.environment == "dev"
        ? "terraform-apply-dev"
      : assertion.workflow_ref == assertion.repository + "/.github/workflows/terraform-apply.yml@refs/heads/main" &&
        assertion.event_name == "workflow_dispatch" &&
        assertion.ref == "refs/heads/main" &&
        has(assertion.environment) && assertion.environment == "dev"
        ? "terraform-apply-dev"
      : assertion.workflow_ref == assertion.repository + "/.github/workflows/terraform-apply.yml@refs/heads/main" &&
        (assertion.event_name == "push" || assertion.event_name == "workflow_dispatch") &&
        assertion.ref == "refs/heads/main" &&
        !has(assertion.environment)
        ? "terraform-plan-dev"
      : assertion.event_name == "pull_request" &&
        assertion.workflow_ref.startsWith(assertion.repository + "/.github/workflows/terraform-plan.yml@refs/pull/")
        ? "terraform-plan-dev"
      : assertion.workflow_ref == assertion.repository + "/.github/workflows/terraform-apply-prod.yml@refs/heads/main" &&
        assertion.event_name == "workflow_dispatch" &&
        assertion.ref == "refs/heads/main" &&
        has(assertion.environment) && assertion.environment == "prod"
        ? "terraform-apply-prod"
      : assertion.workflow_ref == assertion.repository + "/.github/workflows/terraform-apply-prod.yml@refs/heads/main" &&
        assertion.event_name == "workflow_dispatch" &&
        assertion.ref == "refs/heads/main" &&
        !has(assertion.environment)
        ? "terraform-plan-prod"
      : assertion.workflow_ref == assertion.repository + "/.github/workflows/crawler-deploy.yaml@refs/heads/main" &&
        assertion.event_name == "push" &&
        assertion.ref == "refs/heads/main"
        ? "crawler-push-dev"
      : "none"
    EOT
  }

  attribute_condition = <<-EOT
    assertion.repository_id == "1106323394" &&
    assertion.repository_owner_id == "31652298" &&
    attribute.ci_scope != "none"
  EOT

  depends_on = [module.required_project_services]
}

# crawler Artifact Registry の writer は crawler-push-dev に限る（INFRA-ADR-019）。
# 置き場は ops 同一 root（INFRA-ADR-015）
resource "google_artifact_registry_repository_iam_member" "crawler_push_dev" {
  project    = data.google_project.project.project_id
  location   = module.artifact_registries["crawler"].location
  repository = module.artifact_registries["crawler"].repository_id
  role       = "roles/artifactregistry.writer"
  member     = "${local.github_ci_principal_set_prefix}/${local.ci_scope_crawler_push_dev}"

  depends_on = [module.github_wif]
}

# 016 からのリネーム（member は attribute.environment/dev から attribute.ci_scope/crawler-push-dev へ）
moved {
  from = google_artifact_registry_repository_iam_member.github_oidc_dev
  to   = google_artifact_registry_repository_iam_member.crawler_push_dev
}

# ============================================================
# GitHub Actions CI principals（INFRA-ADR-019）
# ci_scope ごとの principalSet に direct resource access で付与する。
# plan は read-only、apply は deploy 対象 root の write。
# これらの grant 自体の変更（setIamPolicy）は CI principal に付けない。
# 差分が出たら CI apply は権限不足で失敗し、手元 apply（bootstrap）となる。
# ============================================================

# --- tfstate bucket（tf project）: identity=ops × resource=tf は下流の ops が書く（INFRA-ADR-015） ---

# plan / apply ともに全 tfstate bucket の read。
# tfstateReader は devgist-tf が定義する custom role。predefined の read-only role には
# storage.buckets.getIamPolicy が無く、plan が bucket IAM member を refresh できないため
resource "google_storage_bucket_iam_member" "ci_tfstate_read" {
  for_each = {
    for pair in setproduct(
      [local.ci_scope_terraform_plan_dev, local.ci_scope_terraform_apply_dev],
      local.all_tfstate_bucket_ids,
      ) : "${pair[0]}|${pair[1]}" => {
      scope  = pair[0]
      bucket = pair[1]
    }
  }

  bucket = each.value.bucket
  role   = "projects/${data.terraform_remote_state.tf.outputs.tf_project_id}/roles/tfstateReader"
  member = "${local.github_ci_principal_set_prefix}/${each.value.scope}"
}

# apply は deploy 対象 root の state bucket に object の read/write（GCS backend の state と lock file）
resource "google_storage_bucket_iam_member" "ci_apply_tfstate_write" {
  for_each = local.ci_deploy_state_bucket_ids

  bucket = each.value
  role   = "roles/storage.objectUser"
  member = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# --- tf project: この root が書く project レベルの IAM member を plan が refresh するための read ---
# tf project には write を付けない（tfstate 基盤は CI に載せない）
resource "google_project_iam_member" "ci_plan_tf" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
  ])

  project = data.terraform_remote_state.tf.outputs.tf_project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

resource "google_project_iam_member" "ci_apply_tf" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
  ])

  project = data.terraform_remote_state.tf.outputs.tf_project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# --- data-dev project: identity=ops × resource=data は ops が書く（INFRA-ADR-015） ---
resource "google_project_iam_member" "ci_plan_data_dev" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
  ])

  project = data.terraform_remote_state.data_dev.outputs.datalake_project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

resource "google_project_iam_member" "ci_apply_data_dev" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/storage.admin",                  # bucket の作成・更新・削除（data-dev の主リソース）
    "roles/serviceusage.serviceUsageAdmin", # API 有効化
  ])

  project = data.terraform_remote_state.data_dev.outputs.datalake_project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# --- datalake bucket（data-dev project） ---
# plan が cursor / crawler の bucket IAM member を refresh するための read-only custom role。
# datalakeIamReader は devgist-data/dev が定義する。apply は project の roles/storage.admin がカバーする
resource "google_storage_bucket_iam_member" "ci_plan_datalake_iam_read" {
  bucket = data.terraform_remote_state.data_dev.outputs.datalake_bucket_name
  role   = "projects/${data.terraform_remote_state.data_dev.outputs.datalake_project_id}/roles/datalakeIamReader"
  member = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

# --- ops project（同一 root） ---
resource "google_project_iam_member" "ci_plan_ops" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/serviceusage.serviceUsageConsumer", # WIF direct access の quota project 利用
  ])

  project = data.google_project.project.project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

resource "google_project_iam_member" "ci_apply_ops" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/artifactregistry.admin",            # repository の作成・削除と repository IAM
    "roles/iam.serviceAccountAdmin",           # SA の作成・削除と SA IAM
    "roles/serviceusage.serviceUsageAdmin",    # API 有効化
    "roles/serviceusage.serviceUsageConsumer", # WIF direct access の quota project 利用
  ])

  project = data.google_project.project.project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# plan が AR repository の IAM member を refresh するための read-only custom role。
# predefined の read-only role には artifactregistry.repositories.getIamPolicy が無い。
# 定義の変更は CI では通らない（apply principal に iam.roles.update を付けない）
resource "google_project_iam_custom_role" "ar_repo_iam_reader" {
  project     = data.google_project.project.project_id
  role_id     = "arRepoIamReader"
  title       = "Artifact Registry repository IAM reader"
  description = "Read-only access to Artifact Registry repository IAM policies for terraform plan (INFRA-ADR-019)"
  permissions = [
    "artifactregistry.repositories.get",
    "artifactregistry.repositories.getIamPolicy",
  ]
}

resource "google_artifact_registry_repository_iam_member" "ci_plan_crawler_repo_iam_read" {
  project    = data.google_project.project.project_id
  location   = module.artifact_registries["crawler"].location
  repository = module.artifact_registries["crawler"].repository_id
  role       = google_project_iam_custom_role.ar_repo_iam_reader.name
  member     = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

# Cursor WIF → data-dev datalake。direct resource access（INFRA-ADR-014）。
# 置き場は ops × data の下流（INFRA-ADR-015）。crawler runtime SA とは別 identity
resource "google_storage_bucket_iam_member" "cursor_oidc" {
  for_each = {
    for pair in setproduct(var.cursor_oidc_subjects, toset([
      "roles/storage.objectViewer",
      "roles/storage.objectCreator",
    ])) :
    "${pair[0]}|${pair[1]}" => {
      subject = pair[0]
      role    = pair[1]
    }
  }

  bucket = data.terraform_remote_state.data_dev.outputs.datalake_bucket_name
  role   = each.value.role
  member = "principal://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${local.cursor_wif_pool_id}/subject/${each.value.subject}"
}

# 既存の GitHub Actions 用 SA。INFRA-ADR-016 の image push では使わない。
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

      service_account_users = [for email in var.service_account_user_emails : "user:${email}"]
    }
  }

  depends_on = [module.required_project_services]
}
