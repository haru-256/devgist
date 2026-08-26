resource "google_iam_workload_identity_pool" "pool" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = var.pool_display_name == "" ? var.pool_id : var.pool_display_name
  description               = var.description
}

resource "google_iam_workload_identity_pool_provider" "oidc" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.pool.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = var.provider_display_name == "" ? var.provider_id : var.provider_display_name
  description                        = var.description
  attribute_mapping                  = var.attribute_mapping
  attribute_condition                = var.attribute_condition

  oidc {
    issuer_uri        = var.issuer_uri
    allowed_audiences = length(var.allowed_audiences) > 0 ? var.allowed_audiences : null
  }
}
