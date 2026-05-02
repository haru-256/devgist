mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id = "mock-project"
}

run "accept_empty_service_accounts" {
  command = plan

  variables {
    service_accounts = {}
  }

  assert {
    condition     = length(output.emails) == 0
    error_message = "Expected no service accounts to be created"
  }
}

run "accept_single_sa_with_project_roles" {
  command = plan

  variables {
    service_accounts = {
      crawler = {
        project_roles = [
          { project = "mock-project", role = "roles/storage.objectCreator" },
          { project = "mock-project", role = "roles/storage.objectViewer" },
        ]
      }
    }
  }

  assert {
    condition     = length(output.emails) == 1
    error_message = "Expected one service account to be created"
  }
}

run "accept_multiple_sas_with_all_binding_types" {
  command = plan

  variables {
    service_accounts = {
      crawler = {
        project_roles = [
          { project = "mock-project", role = "roles/storage.objectCreator" },
        ]
        token_creators        = ["serviceAccount:deployer@mock-project.iam.gserviceaccount.com"]
        service_account_users = ["user:admin@example.com"]
      }
      api-server = {
        project_roles = [
          { project = "mock-project", role = "roles/run.invoker" },
        ]
        service_account_users = ["user:admin@example.com"]
      }
    }
  }

  assert {
    condition     = length(output.emails) == 2
    error_message = "Expected two service accounts to be created"
  }
}
