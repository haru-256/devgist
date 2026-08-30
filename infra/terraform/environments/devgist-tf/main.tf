locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "storage.googleapis.com", # GCSモジュール用
    "iam.googleapis.com",     # custom role 用
  ]
}

# google cloud project
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# 必要なAPIをすべて有効化し待機
module "required_project_services" {
  source = "../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}

# create the bucket for terraform state
module "tfstate_bucket" {
  for_each = toset(var.tfstate_gcp_project_ids)

  source                 = "../../modules/tfstate_gcs_bucket"
  bucket_gcp_project_id  = var.gcp_project_id
  tfstate_gcp_project_id = each.value
  depends_on             = [module.required_project_services]
}

# GitHub Actions CI の plan / apply が tfstate bucket を読み、bucket IAM member を refresh するための
# read-only custom role（INFRA-ADR-019）。predefined の read-only role には
# storage.buckets.getIamPolicy が無い。bucket への grant は ops が書く（INFRA-ADR-015）。
# この role の定義変更はローカル apply（CI の apply principal には iam.roles.update を付けない）
resource "google_project_iam_custom_role" "tfstate_reader" {
  project     = data.google_project.project.project_id
  role_id     = "tfstateReader"
  title       = "Terraform state bucket reader"
  description = "Read-only access to tfstate buckets and their IAM policies for terraform plan (INFRA-ADR-019)"
  permissions = [
    "storage.buckets.get",
    "storage.buckets.getIamPolicy",
    "storage.objects.get",
    "storage.objects.list",
  ]

  depends_on = [module.required_project_services]
}
