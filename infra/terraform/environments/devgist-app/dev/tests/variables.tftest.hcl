mock_provider "google" {}

override_data {
  target = data.terraform_remote_state.ops
  values = {
    outputs = {
      ops_project_id                                = "mock-ops-project"
      crawler_artifact_registry_repository_id       = "mock-crawler-repo"
      crawler_artifact_registry_repository_location = "us-central1"
      cursor_cloud_service_account_member           = "serviceAccount:cursor-cloud@mock-ops-project.iam.gserviceaccount.com"
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

run "grant_cursor_cloud_datalake_read_write" {
  command = plan

  variables {
    crawler_conference_names = "recsys"
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_cloud["roles/storage.objectViewer"].member == "serviceAccount:cursor-cloud@mock-ops-project.iam.gserviceaccount.com"
    error_message = "Expected cursor-cloud objectViewer member from ops remote state"
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_cloud["roles/storage.objectCreator"].member == "serviceAccount:cursor-cloud@mock-ops-project.iam.gserviceaccount.com"
    error_message = "Expected cursor-cloud objectCreator member from ops remote state"
  }

  assert {
    condition     = google_storage_bucket_iam_member.cursor_cloud["roles/storage.objectViewer"].bucket == "mock-datalake-bucket"
    error_message = "Expected cursor-cloud IAM on the data-dev datalake bucket"
  }
}

