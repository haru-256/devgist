# tfstate_gcs_bucket

`tfstate_gcs_bucket` は、**Terraform の state を保管するための GCS バケットだけを管理する専用モジュール**です。  
最終構成（Bootstrap / Data / App 分離）における責務は、**Bootstrap レイヤーの state 基盤提供**です。

## このモジュールの責務（Role in Target Architecture）

このモジュールは次の 1 点に責務を限定します。

- Terraform backend（`gcs`）で利用する **state 保管バケットの作成と保護設定**

対象アーキテクチャ上の位置づけ:

- `bootstrap/`（例: `haru256-devgist-tf`）から呼び出す
- `envs/dev/data`, `envs/dev/app`, `envs/prod/data`, `envs/prod/app` の state 保存先を提供する

> 重要:  
> このモジュールは **アプリデータ（Rawデータ、業務データ、ログ）を保管しません**。  
> それらは `data_platform` など別モジュールの責務です。

## 何を作るモジュールか（What it stores）

このモジュールが作成するバケットに保存されるもの:

- Terraform の state ファイル（`.tfstate`）
- Terraform の state の世代（versioning）
- 必要に応じた state lock 関連メタデータ（backend 実行時）

保存しないもの:

- クローラの収集データ
- 分析データ
- アプリ本体のアップロードファイル
- DBバックアップ本体

## Resource Summary

- `google_storage_bucket.tfstate_bucket`

主な設定:

- `name = "${var.tfstate_gcp_project_id}-tfstate"`
- `force_destroy = false`
- `uniform_bucket_level_access = true`
- `versioning { enabled = true }`
- `lifecycle_rule` で古い世代を削除（`num_newer_versions = 3`）
- `autoclass` 有効化（`terminal_storage_class = "NEARLINE"`）

## Input / Output

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~>1.14.4 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~>7.18.0 |
| <a name="requirement_google-beta"></a> [google-beta](#requirement\_google-beta) | ~>7.18.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | ~>7.18.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_storage_bucket.tfstate_bucket](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_bucket_gcp_project_id"></a> [bucket\_gcp\_project\_id](#input\_bucket\_gcp\_project\_id) | The ID of the GCP project where the GCS bucket for tfstate will be created. | `string` | n/a | yes |
| <a name="input_tfstate_gcp_project_id"></a> [tfstate\_gcp\_project\_id](#input\_tfstate\_gcp\_project\_id) | The ID of the GCP project to be managed by Terraform. | `string` | n/a | yes |
| <a name="input_bucket_location"></a> [bucket\_location](#input\_bucket\_location) | The location of the GCS bucket for tfstate. | `string` | `"US"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_tfstate_gcs_bucket_id"></a> [tfstate\_gcs\_bucket\_id](#output\_tfstate\_gcs\_bucket\_id) | The ID of the bucket used to store terraform state |
<!-- END_TF_DOCS -->

## 使い方（Bootstrap から呼び出す想定）

```hcl
module "tfstate_bucket" {
  source = "../../../modules/tfstate_gcs_bucket"

  bucket_gcp_project_id  = "haru256-devgist-tf"
  tfstate_gcp_project_id = "haru256-devgist-tf"
  bucket_location        = "US"
}
```

複数の対象プロジェクトを管理する場合（`for_each`）:

```hcl
module "tfstate_bucket" {
  for_each = toset(local.tfstate_gcp_project_ids)

  source = "../../../modules/tfstate_gcs_bucket"

  bucket_gcp_project_id  = var.gcp_project_id
  tfstate_gcp_project_id = each.value
}
```

`for_each` 利用時の output 例（list）:

```hcl
output "tfstate_bucket_ids" {
  value       = [for _, m in module.tfstate_bucket : m.tfstate_gcs_bucket_id]
  description = "List of tfstate bucket IDs"
}
```

## Backend 設定例（各 env から参照）

```hcl
terraform {
  backend "gcs" {
    bucket = "haru256-devgist-tf-tfstate"
    prefix = "terraform/dev/data"
  }
}
```

`prefix` は環境・役割ごとに分離します（例）:

- `terraform/dev/data`
- `terraform/dev/app`
- `terraform/prod/data`
- `terraform/prod/app`

## 運用上の注意

- 先に Storage API（`storage.googleapis.com`）を有効化してから作成する
- state バケットは削除事故の影響が大きいため、`force_destroy = false` を維持する
- バケット名はグローバル一意制約があるため、命名衝突に注意する
- このモジュールは state 専用。データレイク用途のバケットとは分離する