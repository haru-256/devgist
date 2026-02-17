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
