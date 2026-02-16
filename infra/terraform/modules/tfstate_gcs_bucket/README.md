# tfstate_gcs_bucket

Terraform の state 管理用 GCS バケットを作成するモジュールです。  
`google_storage_bucket` を作成し、バージョニング・ライフサイクル・Autoclass を設定します。

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

## 機能

- **バージョニング**: 複数世代の state を保持し、ロールバック時に対応可能
- **ライフサイクル管理**: 古いバージョン（3 世代以上前）は自動削除
- **Autoclass**: アクセスパターンに基づいて自動的にストレージクラスを最適化

## 使用例

### 単一プロジェクトの場合

```hcl
module "tfstate_bucket" {
  source = "../../../modules/tfstate_gcs_bucket"

  bucket_gcp_project_id  = var.gcp_project_id
  tfstate_gcp_project_id = "my-project-id"
  bucket_location        = "US"
}

output "tfstate_bucket_id" {
  value = module.tfstate_bucket.tfstate_gcs_bucket_id
}
```

### 複数プロジェクトを管理する場合（for_each）

```hcl
locals {
  tfstate_gcp_project_ids = [
    "project-a-id",
    "project-b-id",
  ]
}

module "tfstate_bucket" {
  for_each = toset(local.tfstate_gcp_project_ids)

  source = "../../../modules/tfstate_gcs_bucket"

  bucket_gcp_project_id  = var.gcp_project_id
  tfstate_gcp_project_id = each.value
  bucket_location        = "US"
}

# 複数バケットの ID を list で出力
output "tfstate_bucket_ids" {
  value = [for key, bucket in module.tfstate_bucket : bucket.tfstate_gcs_bucket_id]
}

# より詳しい情報を出力する場合
output "tfstate_buckets" {
  value = [for key, bucket in module.tfstate_bucket : {
    project_id = key
    bucket_id  = bucket.tfstate_gcs_bucket_id
  }]
}
```

## 注意事項

- Storage API（`storage.googleapis.com`）を有効化してからバケットを作成します。
- バケット名は `${tfstate_gcp_project_id}-tfstate` で自動生成されます。
- バージョニングは有効化され、古いバージョンは一定数を超えると削除されます。
- `force_destroy = false` で、バケット削除時の誤削除を防止しています。
- `uniform_bucket_level_access = true` で、バケットレベルのアクセス制御を統一しています。

## バックエンド設定例

作成したバケットを Terraform backend として使う場合：

```hcl
# backend.tf
terraform {
  backend "gcs" {
    bucket = "my-project-id-tfstate"
    prefix = "terraform/state"
  }
}
```
