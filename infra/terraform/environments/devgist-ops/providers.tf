provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_default_region
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_default_region
}

# GitHub リソースは environments/devgist-github へ移す。ops の state に
# github_repository_environment / github_actions_variable が残っているあいだは
# removed（destroy = false）の解釈にこの provider が要る。init し直すだけでは足りない。
# forget が終わったら provider と required_providers の github は消してよい。
provider "github" {
  owner = local.github_repository_owner
}

terraform {
  required_version = "~>1.14.4"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~>7.18.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~>7.18.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.12.0"
    }
  }
}
