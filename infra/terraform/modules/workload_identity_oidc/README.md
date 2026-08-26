# workload_identity_oidc

Generic OIDC Workload Identity Federation pool and provider.

This module creates one pool and one OIDC provider. It does not create service accounts or resource IAM. Callers mint a JWT whose `aud` matches the `audience` output, then impersonate a Service Account that grants `roles/iam.workloadIdentityUser` to the federated subject.

## Resources

- `google_iam_workload_identity_pool.pool`
- `google_iam_workload_identity_pool_provider.oidc`

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `project_id` | GCP project that owns the pool | `string` | n/a | yes |
| `pool_id` | Workload identity pool ID | `string` | n/a | yes |
| `provider_id` | Provider ID inside the pool | `string` | n/a | yes |
| `issuer_uri` | OIDC issuer URI | `string` | n/a | yes |
| `attribute_mapping` | Claim to Google STS attribute mapping | `map(string)` | n/a | yes |
| `attribute_condition` | CEL condition that tokens must satisfy | `string` | n/a | yes |
| `allowed_audiences` | Extra JWT audiences. Empty keeps the provider default audience only | `list(string)` | `[]` | no |
| `pool_display_name` | Pool display name. Empty uses `pool_id` | `string` | `""` | no |
| `provider_display_name` | Provider display name. Empty uses `provider_id` | `string` | `""` | no |
| `description` | Description for the pool and provider | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| `pool_id` | Pool ID |
| `provider_id` | Provider ID |
| `pool_name` | Full pool resource name |
| `provider_name` | Full provider resource name |
| `audience` | Default JWT audience (`https://iam.googleapis.com/<provider_name>`). Use this as `aud` when minting tokens |

## Usage

```hcl
module "cursor_oidc" {
  source = "../../modules/workload_identity_oidc"

  project_id  = var.gcp_project_id
  pool_id     = "cursor"
  provider_id = "oidc"
  issuer_uri  = "https://api.cursor.com"
  attribute_mapping = {
    "google.subject"    = "assertion.sub"
    "attribute.repo"    = "assertion.repo_url"
    "attribute.runtime" = "assertion.agent_runtime"
  }
  attribute_condition = "assertion.repo_url == \"github.com/haru-256/devgist\" && assertion.agent_runtime == \"managed\""
}
```

Leave `allowed_audiences` empty so GCP accepts only the default provider audience. That value is `audience` in the module outputs.
