# google_project_services

GCP プロジェクトで **必要な API を有効化する専用モジュール** です。  
このモジュールは、インフラ本体（Cloud Run / GCS / BigQuery / Cloud SQL など）を作る前に実行し、依存 API の未有効化による失敗を防ぐ責務を持ちます。

## このモジュールが格納・管理するもの（責務）

`google_project_services` は **「API 有効化」という初期化責務のみ** を担当します。

- `google_project_service` による API 有効化
- API 有効化後の伝播待機（`time_sleep`）

> つまり、このモジュールは「アプリやデータ基盤のリソース」そのものは作成しません。  
> **各レイヤーの前提条件（API有効化）を整えるための共通基盤モジュール** です。

## 何を作るモジュールか（作成リソース）

- `google_project_service.api_services`  
  指定された API 群を `for_each` で有効化
- `time_sleep.wait_for_api_propagation`  
  API 有効化直後の伝播遅延を吸収する待機リソース

## 想定される利用シーン

- `bootstrap` で共通 API を有効化
- `envs/dev/data` / `envs/dev/app` の apply 前に必要 API を有効化
- 新しいサービス（例: BigQuery, Pub/Sub, Cloud Run, Secret Manager）を導入する際に API を追加

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_google"></a> [google](#requirement_google) | ~>7.18.0 |
| <a name="requirement_google-beta"></a> [google-beta](#requirement_google-beta) | ~>7.18.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider_google) | ~>7.18.0 |
| <a name="provider_time"></a> [time](#provider_time) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_project_service.api_services](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_service) | resource |
| [time_sleep.wait_for_api_propagation](https://registry.terraform.io/providers/hashicorp/time/latest/docs/resources/sleep) | resource |

## Inputs

| 名前 | 説明 | 型 | 必須 |
|------|------|------|------|
| <a name="input_project_id"></a> [project_id](#input_project_id) | API を有効化する対象 GCP プロジェクト ID | `string` | ○ |
| <a name="input_required_services"></a> [required_services](#input_required_services) | 有効化する API 名のリスト（例: `run.googleapis.com`） | `list(string)` | ○ |
| <a name="input_wait_seconds"></a> [wait_seconds](#input_wait_seconds) | API 有効化後に待機する秒数（伝播待ち） | `number` | ○ |

## Outputs

No outputs.

## 使用例

```hcl
module "required_project_services" {
  source = "../../../modules/google_project_services"

  project_id = var.gcp_project_id
  required_services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
  ]
  wait_seconds = 30
}
```

## 運用上のポイント

- `disable_on_destroy = false` のため、`terraform destroy` 時に API は無効化されません。  
  （意図しないサービス停止を避けるため）
- このモジュールは多くの module の `depends_on` 対象にするのが推奨です。
- API 追加時は `required_services` に追記するだけで再利用できます。

## DevGist 構成における位置づけ

Hard Mode 構成（Ops / Data / App 分離）において、`google_project_services` は各プロジェクトに対して次を担います。

- **Ops (bootstrap)**: state 管理・共通基盤に必要な API の有効化
- **Data**: GCS / BigQuery / PubSub / SQL などデータ基盤 API の有効化
- **App**: Cloud Run / Secret Manager 等アプリ実行 API の有効化

このモジュールを最初に適用することで、後続の `network_base` / `data_platform` / `app_databases` / `collector` / `backend_api` などの適用を安定化できます。