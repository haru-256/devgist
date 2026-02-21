# data_platform

DevGist の **Data Layer（OLAP/基盤系）** を担当するモジュールです。  
このモジュールは、アプリのトランザクション処理そのもの（OLTP）ではなく、**収集データの保存・分析基盤** を提供します。

現在の実装では、クローラーなどが出力するデータの一時保存先/蓄積先として使う **GCS バケット** を作成します。

## このモジュールが格納・管理するもの

- **データ基盤用ストレージ**
    - GCS バケット（`<gcp_project_id>-datalake`）
- **データ保持と安全性の基本設定**
    - Uniform bucket-level access
    - Google 管理暗号化（デフォルト）
    - ライフサイクルルール（90日→NEARLINE、180日→COLDLINE）
    - Autoclass（自動的に ARCHIVE へ遷移）
    - `prevent_destroy = true`（誤削除防止）

> 補足: 将来的には BigQuery や Pub/Sub などをこのモジュールに統合し、Data Platform 全体を管理する想定です。  
> 現時点のコードは「GCS datalake バケット作成」が責務です。

## 責務（Role）

- Data Project 側で呼び出し、データ保存先となるバケットを提供する
- App Layer / Collector から参照される「データ置き場」を一元管理する
- Stateful なデータ基盤リソース（まずは GCS）を分離して管理する

## Resources

- `google_storage_bucket.datalake`

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `gcp_project_id` | バケットを作成する GCP Project ID | `string` | n/a | yes |
| `datalake_bucket_location` | データレイク用 GCS バケットのロケーション | `string` | `"US"` | no |

## Outputs

| Name | Description | Type |
|------|-------------|------|
| `bucket_name` | データレイク GCS バケット名 | `string` |
| `bucket_id` | データレイク GCS バケットID | `string` |
| `bucket_self_link` | データレイク GCS バケット self link | `string` |

## 実装上のポイント

### セキュリティ & 保護

- バケット名: `${var.gcp_project_id}-datalake`
- `force_destroy = false`: オブジェクトが残っている状態での破壊を防止
- `lifecycle.prevent_destroy = true`: Terraform からの誤削除を防止
- `uniform_bucket_level_access = true`: バケットレベルアクセス制御の統一

### データ管理

- `versioning = false`: 生データは追記のみ、バージョニング不要
crawler 環境での使用例（[infra/terraform/environments/crawler/main.tf](infra/terraform/environments/crawler/main.tf)）:

```hcl
module "data_platform" {
  source = "../../modules/data_platform"

  gcp_project_id            = data.google_project.project.project_id
  datalake_bucket_location  = var.datalake_bucket_location
  depends_on                = [module.required_project_services]
}
```

出力値の使用:

```hcl
output "datalake_bucket_name" {
  description = "Name of the crawler datalake bucket"
  value       = module.data_platform.bucket_name
}
- **Datalake バケット**: Crawler の出力データ → 処理 → BigQuery への流れを想定
- Kafka/Pub-Sub を追加する場合は本モジュール内に統合予定

## 使用例

```devgist/infra/terraform/environments/dev/data/main.tf#L1-12
module "data_platform" {
  source = "../../../modules/data_platform"

  gcp_project_id           = var.gcp_project_id
  datalake_bucket_location = "US"
}

output "datalake_bucket_name" {
  value = module.data_platform.datalake_bucket_name
}
```

## 関連モジュールとの役割分担

- `network_base`（今後）: VPC/Subnet/Peering など通信基盤
- `app_databases`（今後）: Cloud SQL/Redis など OLTP
- `data_platform`（このモジュール）: GCS/BigQuery/PubSub など OLAP 基盤
- `collector` / `backend_api`（今後）: Cloud Run ベースのアプリ層

この分離により、データ基盤の変更（保存先・分析基盤の拡張）がアプリ本体へ与える影響を最小化できます。
