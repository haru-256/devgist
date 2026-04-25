locals {
  # このTerraform構成で必要な全APIをリスト化
  required_services = [
    "artifactregistry.googleapis.com", # Artifact Registry
    "iam.googleapis.com",              # IAM
  ]

  artifact_registries = {
    crawler = {
      description = "Docker images for the crawler job"
    }
  }

  service_account_user_members = [
    for email in var.service_account_user_emails : "user:${email}"
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

      service_account_users = local.service_account_user_members
    }
  }

  depends_on = [module.required_project_services]
}
