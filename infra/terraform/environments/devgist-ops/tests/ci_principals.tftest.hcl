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

run "ci_principals_get_tfstate_read_on_all_buckets" {
  command = plan

  assert {
    condition     = length(google_storage_bucket_iam_member.ci_tfstate_read) == 10
    error_message = "Expected tfstate read grants for plan/apply scopes on all five tfstate buckets"
  }

  assert {
    condition     = google_storage_bucket_iam_member.ci_tfstate_read["terraform-plan-dev|haru256-devgist-ops-tfstate"].role == "projects/mock-tf-project/roles/tfstateReader"
    error_message = "Expected tfstate read to use the tfstateReader custom role defined in the tf project"
  }

  assert {
    condition     = google_storage_bucket_iam_member.ci_tfstate_read["terraform-apply-dev|haru256-devgist-ops-tfstate"].member == "principalSet://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/github-devgist/attribute.ci_scope/terraform-apply-dev"
    error_message = "Expected tfstate read member to be the terraform-apply-dev ci_scope principalSet"
  }
}

run "ci_apply_writes_only_deploy_state_buckets" {
  command = plan

  assert {
    condition = toset(keys(google_storage_bucket_iam_member.ci_apply_tfstate_write)) == toset([
      "haru256-devgist-ops-tfstate",
      "haru256-devgist-data-dev-tfstate",
      "haru256-devgist-app-dev-tfstate",
    ])
    error_message = "Expected apply write grants on the ops/data-dev/app-dev state buckets only (not tf, not github)"
  }

  assert {
    condition     = google_storage_bucket_iam_member.ci_apply_tfstate_write["haru256-devgist-ops-tfstate"].role == "roles/storage.objectUser"
    error_message = "Expected apply state write to use storage.objectUser"
  }
}

run "ci_principals_ops_project_roles" {
  command = plan

  assert {
    condition = toset([for binding in values(google_project_iam_member.ci_plan_ops) : binding.role]) == toset([
      "roles/viewer",
      "roles/iam.securityReviewer",
      "roles/serviceusage.serviceUsageConsumer",
    ])
    error_message = "Expected plan principal to be read-only on the ops project"
  }

  assert {
    condition = toset([for binding in values(google_project_iam_member.ci_apply_ops) : binding.role]) == toset([
      "roles/viewer",
      "roles/iam.securityReviewer",
      "roles/artifactregistry.admin",
      "roles/iam.serviceAccountAdmin",
      "roles/serviceusage.serviceUsageAdmin",
      "roles/serviceusage.serviceUsageConsumer",
    ])
    error_message = "Expected apply principal roles on the ops project"
  }

  assert {
    condition     = !contains([for binding in values(google_project_iam_member.ci_apply_ops) : binding.role], "roles/resourcemanager.projectIamAdmin")
    error_message = "Apply principal must not get project IAM admin (it would be able to change its own grants)"
  }
}

run "ci_principals_data_dev_project_roles" {
  command = plan

  assert {
    condition     = google_project_iam_member.ci_plan_data_dev["roles/viewer"].project == "mock-data-project"
    error_message = "Expected plan principal viewer on the data-dev project from remote state"
  }

  assert {
    condition = toset([for binding in values(google_project_iam_member.ci_apply_data_dev) : binding.role]) == toset([
      "roles/viewer",
      "roles/iam.securityReviewer",
      "roles/storage.admin",
      "roles/serviceusage.serviceUsageAdmin",
    ])
    error_message = "Expected apply principal roles on the data-dev project"
  }
}

run "ci_plan_reads_datalake_and_ar_repo_iam_via_custom_roles" {
  command = plan

  assert {
    condition     = google_storage_bucket_iam_member.ci_plan_datalake_iam_read.role == "projects/mock-data-project/roles/datalakeIamReader"
    error_message = "Expected datalake IAM read to use the datalakeIamReader custom role defined in the data-dev root"
  }

  assert {
    condition     = google_storage_bucket_iam_member.ci_plan_datalake_iam_read.bucket == "mock-datalake-bucket"
    error_message = "Expected datalake IAM read on the data-dev datalake bucket"
  }

  assert {
    condition = toset(google_project_iam_custom_role.ar_repo_iam_reader.permissions) == toset([
      "artifactregistry.repositories.get",
      "artifactregistry.repositories.getIamPolicy",
    ])
    error_message = "Expected arRepoIamReader to be read-only on repository IAM policies"
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.ci_plan_crawler_repo_iam_read.member == "principalSet://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/github-devgist/attribute.ci_scope/terraform-plan-dev"
    error_message = "Expected AR repo IAM read member to be the terraform-plan-dev ci_scope principalSet"
  }
}
