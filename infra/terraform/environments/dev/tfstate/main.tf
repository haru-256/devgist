locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "storage.googleapis.com", # GCSモジュール用
  ]
}

# google cloud project
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# 必要なAPIをすべて有効化し待機
module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id        = data.google_project.project
  required_services = local.required_services
  wait_seconds      = 30
}

# create the bucket for terraform state
module "tfstate_bucket" {
  for_each = toset(var.tfstate_gcp_project_ids)

  source                 = "../../../modules/tfstate_gcs_bucket"
  bucket_gcp_project_id  = var.gcp_project_id
  tfstate_gcp_project_id = each.value
  depends_on             = [module.required_project_services]
}
