# Terraform

GCP 向けインフラを Terraform で管理するディレクトリです。  
Google Cloud の公式ベストプラクティスに沿って、環境ごとの root module と再利用可能な module を分離しています。

参照:
- https://cloud.google.com/docs/terraform/best-practices/root-modules?hl=ja

## Overview

- `environments/` に環境ごとの root module を配置
- `modules/` に再利用可能な module を配置
- リポジトリ直下の `make/` に共通の Makefile 断片を配置

## Directory Structure

```
infra/terraform/
├── .tflint.hcl
├── README.md
├── environments/
│   ├── .gitignore
│   ├── devgist-app/
│   │   └── dev/
│   │       ├── Makefile
│   │       ├── backend.tf
│   │       ├── config.gcs.tfbackend
│   │       ├── main.tf
│   │       ├── outputs.tf
│   │       ├── providers.tf
│   │       ├── terraform.tfvars
│   │       └── variables.tf
│   ├── devgist-data/
│   │   └── dev/
│   │       ├── Makefile
│   │       ├── backend.tf
│   │       ├── config.gcs.tfbackend
│   │       ├── main.tf
│   │       ├── outputs.tf
│   │       ├── providers.tf
│   │       ├── terraform.tfvars
│   │       └── variables.tf
│   ├── devgist-ops/
│   │   ├── Makefile
│   │   ├── backend.tf
│   │   ├── config.gcs.tfbackend
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── terraform.tfvars
│   │   └── variables.tf
│   └── devgist-tf/
│       ├── Makefile
│       ├── backend.tf
│       ├── config.gcs.tfbackend
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── terraform.tfvars
│       └── variables.tf
├── modules/
│   ├── artifact_registry/
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   └── README.md
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
│   ├── service_accounts/
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   └── README.md
│   ├── tfstate_gcs_bucket/
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   └── README.md
│   └── workload_identity_oidc/
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── variables.tf
│       └── README.md
make/
├── help.mk
└── terraform.mk
```

## 各ディレクトリの役割

### `environments/`
環境ごとの root module を配置します。  
GCP project ごとに root module を配置し、必要に応じて `dev/` などの環境サブディレクトリを切ります。

- `devgist-tf/`: Terraform state 管理用 project の root module
- `devgist-ops/`: Artifact Registry、Cursor 用 WIF、共通 Service Account などの運用基盤 project の root module
- `devgist-data/dev/`: 開発環境の data project 用 root module
- `devgist-app/dev/`: 開発環境の app project 用 root module

### `modules/`
複数の環境で再利用する module を配置します。

- `artifact_registry/`: Artifact Registry repository を作成する module
- `datalake/`: GCP のデータレイク用 GCS バケットを作成する module
- `google_project_services/`: GCP の API 有効化を行う module
- `service_accounts/`: Service Account と IAM（project role / actAs / WIF impersonation）をまとめる module
- `tfstate_gcs_bucket/`: Terraform の state 管理用 GCS バケットを作成する module
- `workload_identity_oidc/`: 汎用 OIDC Workload Identity Federation の pool と provider を作る module

### `make/`
リポジトリ直下にあり、リポジトリ全体で再利用する Makefile 断片を配置します。

- `help.mk`: 共通の `help` ターゲット
- `terraform.mk`: Terraform 向けの共通ターゲット

## 運用メモ

- root module は `environments/<env>/<service>` に配置し、環境ごとの入力値は `terraform.tfvars` で管理します。
- module の追加・更新は `modules/` 配下に集約し、root module 側で呼び出します。
- `terraform.tfstate` は環境ごとの状態を保持します。リモート backend を使う場合は `backend.tf` で設定します。
- Cursor Cloud 用 WIF（pool `cursor` / provider `oidc`）は `devgist-ops` で定義する。datalake への `objectViewer` / `objectCreator` は `devgist-app/dev` が federated principal に直接付与する。apply 順は ops → app。`cursor_wif_audience` は後続の OIDC mint で使う。credential config に SA impersonation は入れない。

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
