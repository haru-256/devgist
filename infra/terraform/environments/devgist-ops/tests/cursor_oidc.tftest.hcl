mock_provider "google" {}
mock_provider "google-beta" {}
mock_provider "github" {}

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

variables {
  gcp_project_id     = "ops"
  gcp_default_region = "us-central1"
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

  variables {
    cursor_oidc_subjects = []
  }

  assert {
    condition     = length(google_storage_bucket_iam_member.cursor_oidc) == 0
    error_message = "Expected no Cursor OIDC datalake IAM when the subject allowlist is empty"
  }
}
