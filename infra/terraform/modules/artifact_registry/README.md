# artifact_registry

GCP の Docker 用 `Artifact Registry repository` を作成するモジュールです。

このモジュールは単一の repository を作ることだけを責務に持ちます。DevGist では project は共有しつつ、application / service ごとに repository を分けて運用する前提で使います。課金抑制として vulnerability scanning を `DISABLED` にし、cleanup policy で古い version を消す（[INFRA-ADR-018](../../../../docs/adr/infra/018-artifact-registry-cost-controls.md)）。

## Resources

- `google_artifact_registry_repository.repository`

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `project_id` | repository を作成する GCP Project ID | `string` | n/a | yes |
| `location` | repository のリージョン | `string` | n/a | yes |
| `repository_id` | repository ID | `string` | n/a | yes |
| `description` | repository の説明 | `string` | `""` | no |
| `cleanup_keep_count` | パッケージごとに残す直近 version 数 | `number` | `5` | no |
| `cleanup_delete_older_than` | KEEP 対象外で削除する年齢（例: `30d`） | `string` | `"30d"` | no |
| `cleanup_policy_dry_run` | true なら削除せず dry-run のみ | `bool` | `false` | no |

## Outputs

| Name | Description | Type |
|------|-------------|------|
| `repository_id` | Artifact Registry repository ID | `string` |
| `name` | Artifact Registry repository resource name | `string` |
| `location` | Artifact Registry repository location | `string` |
| `repository_url` | Docker push 用 URL | `string` |

## Cost controls

- `vulnerability_scanning_config.enablement_config = DISABLED`（プロジェクトで Container Scanning API を有効にしても、この repository はスキャンしない）
- cleanup:
  - `keep-minimum-versions`: 直近 `cleanup_keep_count` 世代を KEEP
  - `delete-older-than`: `cleanup_delete_older_than` より古い version を DELETE（KEEP が勝つ）

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
