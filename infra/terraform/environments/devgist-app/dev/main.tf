locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "run.googleapis.com", # Cloud Run Jobs / Services
  ]
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id        = data.google_project.project.project_id
  required_services = local.required_services
  wait_seconds      = 30
}
