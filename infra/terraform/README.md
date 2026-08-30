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
│   │   ├── variables.tf
│   │   └── tests/
│   ├── devgist-tf/
│   │   ├── Makefile
│   │   ├── backend.tf
│   │   ├── config.gcs.tfbackend
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── terraform.tfvars
│   │   └── variables.tf
│   └── devgist-github/
│       ├── Makefile
│       ├── backend.tf
│       ├── config.gcs.tfbackend
│       ├── main.tf
│       ├── providers.tf
│       ├── variables.tf
│       └── tests/
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
- `devgist-ops/`: Artifact Registry、Cursor 用 WIF、GitHub Actions 用 WIF、GitHub Actions CI principal の IAM、共通 Service Account などの運用基盤 project の root module
- `devgist-data/dev/`: 開発環境の data project 用 root module
- `devgist-app/dev/`: 開発環境の app project 用 root module
- `devgist-github/`: GitHub Environment / repository variable / repository secret を管理する root module。GCP project を持たない。plan / apply はローカル限定（[INFRA-ADR-019](../../docs/adr/infra/019-github-actions-terraform-plan-apply.md)）

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
- Cursor Cloud 用 WIF（pool `cursor` / provider `oidc`）は `devgist-ops` で定義する。datalake への `objectViewer` / `objectCreator` は依存の下流（ops）が federated principal に直接付与する（[INFRA-ADR-015](../../docs/adr/infra/015-guest-iam-downstream.md)）。apply 順は data → ops → app。`cursor_wif_audience` は後続の OIDC mint で使う。credential config に SA impersonation は入れない。
- GitHub Actions 用 WIF（pool `github-devgist` / provider `oidc`）も `devgist-ops` で定義する。issuer は GitHub。IAM の identity class は `attribute.ci_scope`（plan / apply / crawler）である（[INFRA-ADR-019](../../docs/adr/infra/019-github-actions-terraform-plan-apply.md)）。crawler Artifact Registry への writer は `crawler-push-dev` に直接付与する。GitHub Environment `dev`、repository variable（`GCP_GITHUB_WIF_PROVIDER`、`CRAWLER_REPO_URL`、`CRAWLER_IMAGE_NAME`）、repository secret（`CURSOR_OIDC_SUBJECTS`、`SERVICE_ACCOUNT_USER_EMAILS`）は `environments/devgist-github` root が書く（[INFRA-ADR-017](../../docs/adr/infra/017-github-actions-terraform-managed-variables.md)。置き場は 019 が ops から `devgist-github` root に変えた）。GitHub リソースの write と WIF mapping の変更は手元。credential config に SA impersonation は入れない。terraform plan / apply の CI は 019。
- `environments/**/terraform.tfvars` は非 secret 値に限り version 管理する（019）。secret 値（`cursor_oidc_subjects`、`service_account_user_emails`）は gitignore 済みの `secrets.tfvars` が正本。`devgist-github` が repository secret として書き、CI はそれを `TF_VAR_*` で読む。ops / app-dev のローカル apply は各 root の `secrets.tfvars` を使う（`make plan` / `make apply` が `-var-file=secrets.tfvars` を付ける。Terraform は `*.auto.tfvars` 以外を自動では読まない）。これらの variable に default はなく、未設定では plan / apply が失敗する。GitHub UI から secret を手で作らない。

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
