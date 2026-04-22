locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
  ]
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

// crawler用のArtifact Registryを作成
module "crawler_artifact_registry" {
  source = "../../modules/artifact_registry"

  project_id    = data.google_project.project.project_id
  location      = var.gcp_default_region
  repository_id = "crawler"
  description   = "Docker images for the crawler job"

  depends_on = [module.required_project_services]
}
