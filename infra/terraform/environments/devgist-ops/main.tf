locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
  ]

  artifact_registries = {
    crawler = {
      description = "Docker images for the crawler job"
    }
  }
}

data "google_project" "project" {
  project_id = var.gcp_project_id
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

moved {
  from = module.crawler_artifact_registry
  to   = module.artifact_registries["crawler"]
}
