mock_provider "google" {}

override_data {
  target = data.terraform_remote_state.ops
  values = {
    outputs = {
      ops_project_id                                = "mock-ops-project"
      crawler_artifact_registry_repository_id       = "mock-crawler-repo"
      crawler_artifact_registry_repository_location = "us-central1"
      ops_project_number                            = "123456789"
      cursor_wif_pool_id                            = "cursor"
    }
  }
}

override_data {
  target = data.terraform_remote_state.data
  values = {
    outputs = {
      datalake_bucket_name = "mock-datalake-bucket"
      datalake_project_id  = "mock-data-project"
    }
  }
}

variables {
  gcp_project_id     = "app-dev"
  gcp_default_region = "us-central1"
  crawler_image      = "us-central1-docker.pkg.dev/ops/crawler/crawler@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}

run "accept_single_conference_name" {
  command = plan

  variables {
    crawler_conference_names = "recsys"
  }
}

run "accept_multiple_comma_separated_names" {
  command = plan

  variables {
    crawler_conference_names = "recsys,kdd,www"
  }
}

run "reject_unknown_conference_names" {
  command = plan

  variables {
    crawler_conference_names = "www2023,rec-sys,ml_conf"
  }

  expect_failures = [
    var.crawler_conference_names,
  ]
}

run "reject_leading_comma" {
  command = plan

  variables {
    crawler_conference_names = ",recsys"
  }

  expect_failures = [
    var.crawler_conference_names,
  ]
}

run "reject_trailing_comma" {
  command = plan

  variables {
    crawler_conference_names = "recsys,"
  }

  expect_failures = [
    var.crawler_conference_names,
  ]
}

run "reject_empty_string" {
  command = plan

  variables {
    crawler_conference_names = ""
  }

  expect_failures = [
    var.crawler_conference_names,
  ]
}

run "reject_space_separated_crawler_conference_names" {
  command = plan

  variables {
    crawler_conference_names = "recsys hdd www"
  }

  expect_failures = [
    var.crawler_conference_names,
  ]
}

run "grant_cursor_oidc_datalake_read_write" {
  command = plan

  variables {
    crawler_conference_names = "recsys"
    cursor_oidc_subjects     = ["user:308716925"]
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
    crawler_conference_names = "recsys"
    cursor_oidc_subjects     = []
  }

  assert {
    condition     = length(google_storage_bucket_iam_member.cursor_oidc) == 0
    error_message = "Expected no Cursor OIDC datalake IAM when the subject allowlist is empty"
  }
}

