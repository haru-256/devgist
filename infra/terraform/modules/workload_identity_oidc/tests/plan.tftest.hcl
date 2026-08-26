mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id  = "mock-project"
  pool_id     = "cursor"
  provider_id = "oidc"
  issuer_uri  = "https://api.cursor.com"
  attribute_mapping = {
    "google.subject" = "assertion.sub"
  }
  attribute_condition = "assertion.agent_runtime == \"managed\""
}

run "accept_pool_and_provider_ids" {
  command = plan

  assert {
    condition     = output.pool_id == "cursor"
    error_message = "Expected pool_id to match the input pool_id"
  }

  assert {
    condition     = output.provider_id == "oidc"
    error_message = "Expected provider_id to match the input provider_id"
  }

  assert {
    condition     = google_iam_workload_identity_pool_provider.oidc.oidc[0].issuer_uri == "https://api.cursor.com"
    error_message = "Expected OIDC issuer_uri to match the input"
  }

  assert {
    condition     = google_iam_workload_identity_pool_provider.oidc.attribute_mapping["google.subject"] == "assertion.sub"
    error_message = "Expected google.subject to map from assertion.sub"
  }
}

run "accept_custom_audiences" {
  command = plan

  variables {
    allowed_audiences = ["https://example.invalid"]
  }

  assert {
    condition     = output.pool_id == "cursor"
    error_message = "Expected pool_id to remain cursor when allowed_audiences is set"
  }
}
