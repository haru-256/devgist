locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "iam.googleapis.com", # IAM
    "run.googleapis.com", # Cloud Run Jobs / Services
  ]

  service_account_user_members = [
    for email in var.service_account_user_emails : "user:${email}"
  ]
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

// ops 環境の Terraform state から、ops 環境で作成したリソースの情報を参照するための data source
data "terraform_remote_state" "ops" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-ops-tfstate"
  }
}

// data 環境の Terraform state から、data 環境で作成したリソースの情報を参照するための data source
data "terraform_remote_state" "data" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-data-dev-tfstate"
  }
}

module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}

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

// ops 環境の Artifact Registry に対して、dev 環境の crawler 用 service account に reader 権限を付与
resource "google_artifact_registry_repository_iam_member" "crawler" {
  project    = data.terraform_remote_state.ops.outputs.ops_project_id
  location   = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_location
  repository = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_id
  role       = "roles/artifactregistry.reader"
  member     = module.service_accounts.members["crawler"]
}
moved {
  from = google_artifact_registry_repository_iam_member.crawler_reader
  to   = google_artifact_registry_repository_iam_member.crawler
}

// data環境のGCSバケットに対して、dev環境のcrawler用service accountに読み込み・書き込み権限を付与
resource "google_storage_bucket_iam_member" "crawler" {
  for_each = toset(["roles/storage.objectViewer", "roles/storage.objectCreator"])

  bucket = data.terraform_remote_state.data.outputs.datalake_bucket_name
  role   = each.value
  member = module.service_accounts.members["crawler"]
}
