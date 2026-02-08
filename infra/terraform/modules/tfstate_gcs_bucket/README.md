# tfstate_gcs_bucket

Terraform の state 管理用 GCS バケットを作成するモジュールです。  
`google_storage_bucket` を作成し、バージョニング・ライフサイクル・Autoclass を設定します。

## Inputs

| Name | Type | Description | Required |
| --- | --- | --- | --- |
| `gcp_project_id` | `string` | GCP プロジェクトの ID | Yes |

## Outputs

| Name | Type | Description |
| --- | --- | --- |
| `tfstate_gcs_bucket_id` | `string` | 生成した GCS バケットの ID |

## Notes

- Storage API（`storage.googleapis.com`）を有効化してからバケットを作成します。
- バケット名は `${gcp_project_id}-tfstate` です。
- バージョニングを有効化し、古いバージョンは一定数を超えると削除します。