locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "storage.googleapis.com", # GCS
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
