mock_provider "google" {}
mock_provider "google-beta" {}

override_data {
  target = data.google_project.project
  values = {
    project_id = "ops"
    number     = "123456789"
  }
}

override_data {
  target = data.terraform_remote_state.data_dev
  values = {
    outputs = {
      datalake_bucket_name = "mock-datalake-bucket"
      datalake_project_id  = "mock-data-project"
    }
  }
}

override_data {
  target = data.terraform_remote_state.tf
  values = {
    outputs = {
      tf_project_id = "mock-tf-project"
      tfstate_buckets = [
        { project_id = "haru256-devgist-tf", bucket_id = "haru256-devgist-tf-tfstate" },
        { project_id = "haru256-devgist-ops", bucket_id = "haru256-devgist-ops-tfstate" },
        { project_id = "haru256-devgist-data-dev", bucket_id = "haru256-devgist-data-dev-tfstate" },
        { project_id = "haru256-devgist-app-dev", bucket_id = "haru256-devgist-app-dev-tfstate" },
        { project_id = "haru256-devgist-github", bucket_id = "haru256-devgist-github-tfstate" },
      ]
    }
  }
}

variables {
  gcp_project_id              = "ops"
  gcp_default_region          = "us-central1"
  cursor_oidc_subjects        = []
  service_account_user_emails = []
}

run "github_wif_pool_and_provider_stay_single_entry" {
  command = plan

  assert {
    condition     = module.github_wif.pool_id == "github-devgist"
    error_message = "Expected GitHub WIF pool id to be github-devgist"
  }

  assert {
    condition     = module.github_wif.provider_id == "oidc"
    error_message = "Expected GitHub WIF provider id to be oidc"
  }

  assert {
    condition     = module.github_wif.issuer_uri == "https://token.actions.githubusercontent.com"
    error_message = "Expected GitHub WIF issuer to be GitHub Actions OIDC"
  }
}

run "github_wif_condition_is_repository_ids_and_ci_scope" {
  command = plan

  assert {
    condition = (
      strcontains(module.github_wif.attribute_condition, "assertion.repository_id == \"1106323394\"") &&
      strcontains(module.github_wif.attribute_condition, "assertion.repository_owner_id == \"31652298\"") &&
      strcontains(module.github_wif.attribute_condition, "attribute.ci_scope != \"none\"") &&
      !strcontains(module.github_wif.attribute_condition, "environment") &&
      !strcontains(module.github_wif.attribute_condition, "workflow") &&
      !strcontains(module.github_wif.attribute_condition, "assertion.ref")
    )
    error_message = "Expected GitHub WIF condition to be repository_id, repository_owner_id, and ci_scope != none only"
  }
}

run "github_wif_mapping_synthesizes_ci_scope_without_environment_key" {
  command = plan

  assert {
    condition     = !contains(keys(module.github_wif.attribute_mapping), "attribute.environment")
    error_message = "Expected attribute.environment to be removed from the mapping (INFRA-ADR-019)"
  }

  assert {
    condition = (
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "terraform-apply-dev") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "terraform-plan-dev") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "terraform-apply-prod") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "terraform-plan-prod") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "crawler-push-dev")
    )
    error_message = "Expected ci_scope mapping to contain all five scopes"
  }

  assert {
    condition = (
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "/.github/workflows/terraform-apply.yml@refs/heads/main") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "/.github/workflows/terraform-plan.yml@refs/pull/") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "/.github/workflows/terraform-apply-prod.yml@refs/heads/main") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "/.github/workflows/crawler-deploy.yaml@refs/heads/main") &&
      strcontains(module.github_wif.attribute_mapping["attribute.ci_scope"], "has(assertion.environment)")
    )
    error_message = "Expected ci_scope mapping to pin workflow files and guard the optional environment claim"
  }
}

run "crawler_writer_is_bound_to_crawler_push_dev_scope" {
  command = plan

  assert {
    condition     = google_artifact_registry_repository_iam_member.crawler_push_dev.member == "principalSet://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/github-devgist/attribute.ci_scope/crawler-push-dev"
    error_message = "Expected crawler writer member to be the crawler-push-dev ci_scope principalSet"
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.crawler_push_dev.role == "roles/artifactregistry.writer"
    error_message = "Expected GitHub OIDC IAM role to be artifactregistry.writer"
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.crawler_push_dev.repository == "crawler"
    error_message = "Expected GitHub OIDC writer on the crawler Artifact Registry repository"
  }
}
