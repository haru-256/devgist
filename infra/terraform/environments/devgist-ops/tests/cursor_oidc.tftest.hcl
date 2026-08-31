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

run "grant_cursor_oidc_datalake_read_write" {
  command = plan

  variables {
    cursor_oidc_subjects = ["user:308716925"]
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_oidc["user:308716925|roles/storage.objectViewer"].member == "principal://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/cursor/subject/user:308716925"
    error_message = "Expected Cursor OIDC objectViewer member to be the WIF federated principal"
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_oidc["user:308716925|roles/storage.objectCreator"].member == "principal://iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/cursor/subject/user:308716925"
    error_message = "Expected Cursor OIDC objectCreator member to be the WIF federated principal"
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_oidc["user:308716925|roles/storage.objectViewer"].bucket == "mock-datalake-bucket"
    error_message = "Expected Cursor OIDC IAM on the data-dev datalake bucket"
  }
}

run "skip_cursor_oidc_datalake_when_allowlist_empty" {
  command = plan

  assert {
    condition     = length(google_storage_bucket_iam_member.cursor_oidc) == 0
    error_message = "Expected no Cursor OIDC datalake IAM when the subject allowlist is empty"
  }
}
