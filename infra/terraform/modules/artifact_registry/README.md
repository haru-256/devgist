# artifact_registry

GCP の Docker 用 `Artifact Registry repository` を作成するモジュールです。

このモジュールは単一の repository を作ることだけを責務に持ちます。DevGist では project は共有しつつ、application / service ごとに repository を分けて運用する前提で使います。

## Resources

- `google_artifact_registry_repository.repository`

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `project_id` | repository を作成する GCP Project ID | `string` | n/a | yes |
| `location` | repository のリージョン | `string` | n/a | yes |
| `repository_id` | repository ID | `string` | n/a | yes |
| `description` | repository の説明 | `string` | `""` | no |

## Outputs

| Name | Description | Type |
|------|-------------|------|
| `repository_id` | Artifact Registry repository ID | `string` |
| `name` | Artifact Registry repository resource name | `string` |
| `location` | Artifact Registry repository location | `string` |
| `repository_url` | Docker push 用 URL | `string` |

## Usage

```hcl
locals {
  artifact_registries = {
    crawler = {
      description = "Docker images for the crawler job"
    }
    api = {
      description = "Docker images for the API service"
    }
  }
}

module "artifact_registries" {
  for_each = local.artifact_registries
  source   = "../../../modules/artifact_registry"

  project_id    = var.gcp_project_id
  location      = var.gcp_default_region
  repository_id = each.key
  description   = each.value.description
}
```
