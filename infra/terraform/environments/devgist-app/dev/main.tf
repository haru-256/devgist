locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "iam.googleapis.com",            # IAM
    "run.googleapis.com",            # Cloud Run Jobs / Services
    "cloudscheduler.googleapis.com", # Cloud Scheduler
  ]

  service_account_user_members = [
    for email in var.service_account_user_emails : "user:${email}"
  ]

  # Cloud Run Service Agent にクロスプロジェクトの Artifact Registry からイメージを pull するための設定
  cloud_run_service_agent_images = {
    crawler = {
      repository_id = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_id
    }
  }

  # INFRA-ADR-019: GitHub Actions CI の認可単位（operation × environment）
  ci_scope_terraform_plan_dev  = "terraform-plan-dev"
  ci_scope_terraform_apply_dev = "terraform-apply-dev"

  github_ci_principal_set_prefix = "principalSet://iam.googleapis.com/projects/${data.terraform_remote_state.ops.outputs.ops_project_number}/locations/global/workloadIdentityPools/${data.terraform_remote_state.ops.outputs.github_wif_pool_id}/attribute.ci_scope"
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

# ops 環境の Terraform state から、ops 環境で作成したリソースの情報を参照するための data source
data "terraform_remote_state" "ops" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-ops-tfstate"
  }
}

# data 環境の Terraform state から、data 環境で作成したリソースの情報を参照するための data source
data "terraform_remote_state" "data_dev" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-data-dev-tfstate"
  }
}

# プロジェクトで必要なAPIを有効化
module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}

# SAの作成と権限付与
module "service_accounts" {
  source = "../../../modules/service_accounts"

  project_id = data.google_project.project.project_id

  service_accounts = {
    crawler = {
      description           = "Service account used by the crawler workload in dev"
      service_account_users = local.service_account_user_members
    }
  }

  depends_on = [module.required_project_services]
}

# Cloud Run Service Agent に cross-project image pull 権限を付与
#
# Cloud Run Service Agent (service-{project_number}@serverless-robot-prod.iam.gserviceaccount.com)
# は Google 管理のサービスアカウントで、Cloud Run プラットフォームがコンテナイメージを
# Artifact Registry から pull する際に使用される。
#
# これはコンテナ内のアプリケーション（crawler SA）とは別の主体である。
# crawler SA はアプリ起動後の GCS アクセスなどに使われるのに対し、
# Cloud Run Service Agent はクロスプロジェクトの Artifact Registry から
# image をダウンロードするために必要な権限である。
resource "google_artifact_registry_repository_iam_member" "cloud_run_service_agent" {
  for_each = local.cloud_run_service_agent_images

  project    = data.terraform_remote_state.ops.outputs.ops_project_id
  location   = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_location
  repository = each.value.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.project.number}@serverless-robot-prod.iam.gserviceaccount.com"
}

# data環境のGCSバケットに対して、crawler SA へ読み込み・書き込みを付ける。
# crawler は app が identity かつ下流（INFRA-ADR-009 / INFRA-ADR-015）
resource "google_storage_bucket_iam_member" "crawler" {
  for_each = toset(["roles/storage.objectViewer", "roles/storage.objectCreator"])

  bucket = data.terraform_remote_state.data_dev.outputs.datalake_bucket_name
  role   = each.value
  member = module.service_accounts.members["crawler"]
}

# ============================================================
# GitHub Actions CI principals（INFRA-ADR-019）
# identity=ops × resource=app は下流の app が書く（INFRA-ADR-015）。
# これらの grant 自体の変更（setIamPolicy）は CI principal に付けない。
# 差分が出たら CI apply は権限不足で失敗し、手元 apply（bootstrap）となる。
# ============================================================

resource "google_project_iam_member" "ci_plan_app_dev" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
  ])

  project = data.google_project.project.project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_plan_dev}"
}

resource "google_project_iam_member" "ci_apply_app_dev" {
  for_each = toset([
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/run.admin",                      # Cloud Run Job の作成・更新・削除
    "roles/iam.serviceAccountAdmin",        # crawler SA の作成・削除と SA IAM
    "roles/serviceusage.serviceUsageAdmin", # API 有効化
  ])

  project = data.google_project.project.project_id
  role    = each.value
  member  = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# apply が Cloud Run Job の実行 SA として crawler SA を指定するための actAs
resource "google_service_account_iam_member" "ci_apply_crawler_sa_user" {
  service_account_id = module.service_accounts.names["crawler"]
  role               = "roles/iam.serviceAccountUser"
  member             = "${local.github_ci_principal_set_prefix}/${local.ci_scope_terraform_apply_dev}"
}

# Crawler用のCloud Run Job の作成
resource "google_cloud_run_v2_job" "crawler" {
  name                = "crawler"
  location            = var.gcp_default_region
  project             = data.google_project.project.project_id
  deletion_protection = false
  labels = {
    app         = "devgist"
    environment = "dev"
    component   = "crawler"
  }

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = module.service_accounts.emails["crawler"]
      max_retries     = 0
      timeout         = "43200s" # タスクのタイムアウトを12時間に設定

      containers {
        image = var.crawler_image
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
        env {
          name  = "DATA_LAKE_PROJECT_ID"
          value = data.terraform_remote_state.data_dev.outputs.datalake_project_id
        }
        env {
          name  = "DATA_LAKE_BUCKET_NAME"
          value = data.terraform_remote_state.data_dev.outputs.datalake_bucket_name
        }
        env {
          name  = "LOG_LEVEL"
          value = "DEBUG"
        }
        env {
          name  = "CONFERENCE_NAMES"
          value = var.crawler_conference_names
        }
      }
    }
  }

  depends_on = [
    module.required_project_services,
    google_artifact_registry_repository_iam_member.cloud_run_service_agent,
  ]
}

# TODO: 手動実行で問題なければ有効化する
# TODO: 以下の権限を付与する
# 1. クローラーのサービスアカウントが自身を起動するための roles/run.invoker 権限（Cloud Run Job に対する付与）
# 2. Cloud Scheduler サービスエージェントがクローラーのサービスアカウントを使用するための roles/iam.serviceAccountUser 権限（サービスアカウントに対する付与）
# # Cloud Run Job を定期実行するための Cloud Scheduler ジョブの作成
# resource "google_cloud_scheduler_job" "crawler" {
#   name             = "crawler-scheduler"
#   description      = "Trigger crawler Cloud Run Job periodically"
#   schedule         = "0 2 * * *" # 毎日午前2時（例）
#   time_zone        = "Asia/Tokyo"
#   project          = data.google_project.project.project_id
#   region           = var.gcp_default_region
#
#   http_target {
#     http_method = "POST"
#     uri         = "https://${var.gcp_default_region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${data.google_project.project.project_id}/jobs/crawler:run"
#     oauth_token {
#       service_account_email = module.service_accounts.emails["crawler"]
#     }
#   }
#
#   depends_on = [google_cloud_run_v2_job.crawler]
# }
