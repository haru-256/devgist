# google_project_services

GCP のプロジェクトで必要な API を有効化するための Terraform モジュールです。  
`google_project_service` をまとめて有効化し、必要に応じて API 有効化後の待機時間も入れます。

## Inputs

| Name | Type | Description | Required |
| --- | --- | --- | --- |
| `project_id` | `string` | GCP プロジェクトの ID | Yes |
| `required_services` | `list(string)` | 有効化するサービス名のリスト（例: `compute.googleapis.com`） | Yes |
| `wait_seconds` | `number` | API 有効化後の待機秒数 | Yes |

## Outputs

このモジュールは出力を提供しません。

## Notes

- `disable_on_destroy = false` のため、`terraform destroy` 時に API を無効化しません。
- `wait_seconds` は API 有効化直後の依存関係エラーを避けるための待機に使います。