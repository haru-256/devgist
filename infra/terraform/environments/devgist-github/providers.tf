provider "github" {
  owner = local.github_repository_owner
}

terraform {
  required_version = "~>1.14.4"
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.12.0"
    }
  }
}
