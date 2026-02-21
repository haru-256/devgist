provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_default_region
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_default_region
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
  }
}
