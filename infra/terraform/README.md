# Terraform

GCP 向けインフラを Terraform で管理するディレクトリです。  
Google Cloud の公式ベストプラクティスに沿って、環境ごとの root module と再利用可能な module を分離しています。

参照:
- https://cloud.google.com/docs/terraform/best-practices/root-modules?hl=ja

## Overview

- `environments/` に環境ごとの root module を配置
- `modules/` に再利用可能な module を配置
- `scripts/` に共通の Makefile 断片など補助スクリプトを配置

## Directory Structure

```
infra/terraform/
├── .tflint.hcl
├── README.md
├── environments/
│   ├── .gitignore
│   └── dev/
│       ├── crawler/
│       │   ├── Makefile
│       │   ├── backend.tf
│       │   ├── main.tf
│       │   ├── outputs.tf
│       │   ├── providers.tf
│       │   ├── terraform.tfstate
│       │   ├── terraform.tfvars
│       │   └── variables.tf
│       └── tfstate/
│           ├── backend.tf
│           ├── main.tf
│           ├── outputs.tf
│           ├── providers.tf
│           ├── variables.tf
│           └── terraform.tfvars
├── modules/
│   ├── datalake/
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   └── README.md
│   ├── google_project_services/
│   │   ├── main.tf
│   │   ├── providers.tf
│   │   └── variables.tf
│   └── tfstate_gcs_bucket/
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── variables.tf
│       └── README.md
└── scripts/
    └── common.mk
```

## 各ディレクトリの役割

### `environments/`
環境ごとの root module を配置します。  
`dev/` 配下に環境別の構成を置き、さらにサービス単位で分割しています。

- `dev/crawler/`: 開発環境の crawler 用 root module
- `dev/tfstate/`: Terraform state 管理用インフラを構築する root module

### `modules/`
複数の環境で再利用する module を配置します。

- `datalake/`: GCP のデータレイク用 GCS バケットを作成する module
- `google_project_services/`: GCP の API 有効化を行う module
- `tfstate_gcs_bucket/`: Terraform の state 管理用 GCS バケットを作成する module

### `scripts/`
Makefile からインクルードされる共通ターゲットなどを配置します。

- `common.mk`: 共通のコマンド定義

## 運用メモ

- root module は `environments/<env>/<service>` に配置し、環境ごとの入力値は `terraform.tfvars` で管理します。
- module の追加・更新は `modules/` 配下に集約し、root module 側で呼び出します。
- `terraform.tfstate` は環境ごとの状態を保持します。リモート backend を使う場合は `backend.tf` で設定します。

## for_each を使う場合の outputs 出力

module やリソースを `for_each` でループさせている場合、複数の属性を list で出力するには以下のように記述します：

```hcl
# 複数のリソース/モジュールを list で出力する例
output "bucket_ids" {
  value       = [for key, bucket in module.tfstate_bucket : bucket.tfstate_gcs_bucket_id]
  description = "List of all tfstate bucket IDs"
}

# より詳しい情報を含める場合
output "buckets" {
  value = [for key, bucket in module.tfstate_bucket : {
    project_id = key
    bucket_id  = bucket.tfstate_gcs_bucket_id
  }]
  description = "List of all tfstate buckets with their project IDs"
}
```
