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
│       └── crawler/
│           ├── Makefile
│           ├── backend.tf
│           ├── main.tf
│           ├── outputs.tf
│           ├── providers.tf
│           ├── terraform.tfstate
│           ├── terraform.tfvars
│           └── variables.tf
├── modules/
│   ├── google_project_services/
│   │   ├── main.tf
│   │   ├── providers.tf
│   │   └── variables.tf
│   └── tfstate_gcs_bucket/
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       └── variables.tf
└── scripts/
    └── common.mk
```

## 各ディレクトリの役割

### `environments/`
環境ごとの root module を配置します。  
`dev/` 配下に環境別の構成を置き、さらにサービス単位で分割しています。

- `dev/crawler/`: 開発環境の crawler 用 root module

### `modules/`
複数の環境で再利用する module を配置します。

- `google_project_services/`: GCP の API 有効化を行う module
- `tfstate_gcs_bucket/`: Terraform の state 管理用 GCS バケットを作成する module

### `scripts/`
Makefile からインクルードされる共通ターゲットなどを配置します。

- `common.mk`: 共通のコマンド定義

## 運用メモ

- root module は `environments/<env>/<service>` に配置し、環境ごとの入力値は `terraform.tfvars` で管理します。
- module の追加・更新は `modules/` 配下に集約し、root module 側で呼び出します。
- `terraform.tfstate` は環境ごとの状態を保持します。リモート backend を使う場合は `backend.tf` で設定します。
