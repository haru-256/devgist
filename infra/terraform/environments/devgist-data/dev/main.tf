locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "storage.googleapis.com", # GCS
    "iam.googleapis.com",     # custom role 用
  ]
}

# google cloud project
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# 必要なAPIをすべて有効化し待機
module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}

# data platform
module "data_platform" {
  source = "../../../modules/data_platform"

  gcp_project_id           = data.google_project.project.project_id
  datalake_bucket_location = var.gcp_default_region
  depends_on               = [module.required_project_services]
}

# GitHub Actions CI の plan が datalake bucket の IAM member（cursor / crawler の grant）を
# refresh するための read-only custom role（INFRA-ADR-019）。
# predefined の read-only role には storage.buckets.getIamPolicy が無い。
# bucket への grant は ops が書く（INFRA-ADR-015）。この role の定義変更は bootstrap
# （CI の apply principal には iam.roles.update を付けない）
resource "google_project_iam_custom_role" "datalake_iam_reader" {
  project     = data.google_project.project.project_id
  role_id     = "datalakeIamReader"
  title       = "Datalake bucket IAM reader"
  description = "Read-only access to the datalake bucket IAM policy for terraform plan (INFRA-ADR-019)"
  permissions = [
    "storage.buckets.get",
    "storage.buckets.getIamPolicy",
  ]

  depends_on = [module.required_project_services]
}
