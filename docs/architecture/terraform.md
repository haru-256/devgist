# Terraform 構成

## root module は GCP project ごとに切る

service（crawler など）では切らない。1 つの service が複数 project にまたがる場合は、各 project 側に責務を分解する（[INFRA-ADR-005](../adr/infra/005-terraform-environment-slicing.md)）。

| root | 対象 | plan / apply |
|---|---|---|
| `environments/devgist-tf` | 全 root の state bucket | **ローカルのみ** |
| `environments/devgist-ops` | Artifact Registry、WIF、CI の guest IAM | CI |
| `environments/devgist-data/dev` | GCS datalake（箱） | CI |
| `environments/devgist-app/dev` | Cloud Run Job、crawler SA | CI |
| `environments/devgist-github` | GitHub Environment / repository variable | **ローカルのみ** |

`devgist-tf` と `devgist-github` を CI に載せないのは、前者が state 基盤そのもので、後者が GitHub 向けの長寿命 credential を CI に置くことになるためです（[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md)）。
両方とも静的 CI（fmt / validate / tflint / test）の対象にはなる。

**一般原則**: CI 化のセキュリティ対処コストが自動化のメリットを上回るものは、ローカル管理にする。

## apply 順

```
tf → data → ops → app
```

`ops` の identity（Cursor WIF）が `data` の箱へ grant する辺があるため、`data` が `ops` より先（[INFRA-ADR-015](../adr/infra/015-guest-iam-downstream.md)）。
`app` は sink。CI の apply もこの順で直列に実行する。

## module

`infra/terraform/modules/` に置く。分割は責務とデータの性質（OLTP / OLAP）で行う。技術レイヤ（network / storage / compute）では割らない（[INFRA-ADR-002](../adr/infra/002-terraform-module-structure.md)）。

実装済み（`.tf` がある）:

| module | 役割 |
|---|---|
| `google_project_services` | API 有効化 |
| `tfstate_gcs_bucket` | state bucket（`tf` root のみ） |
| `data_platform` | GCS datalake。BigQuery は未実装 |
| `artifact_registry` | Docker repository。scanning / cleanup policy 込み |
| `service_accounts` | Service Account。`generate_keys = false` |
| `workload_identity_oidc` | WIF pool / provider |

README だけの stub（`.tf` は無い。呼ばない）:

| module | 想定する役割 |
|---|---|
| `network_base` | VPC / Subnet / Firewall |
| `app_databases` | Cloud SQL（OLTP） |

Terraform root には必ず `providers.tf` を置く。CI の root 自動検出がこれを目印にするため、無いと CI 対象から漏れる（[INFRA-ADR-011](../adr/infra/011-terraform-ci-for-monorepo.md)）。

## cross-project の値の受け渡し

**非 secret な識別子は `terraform_remote_state` で upstream の `outputs` を読む。** 手で転記しない（[INFRA-ADR-006](../adr/infra/006-cross-project-output-sharing.md)）。

| 値の種類 | 受け渡し方 |
|---|---|
| 非 secret な識別子（bucket 名、AR URL、connection name） | `terraform_remote_state` |
| 環境差分（project ID、region） | variables |
| project 内で完結する固定値（`repository_id = "crawler"`） | コードに直書き |
| true secret | Secret Manager。Terraform outputs / tfvars に載せない |

downstream は upstream の `outputs` だけに依存する。内部の resource 名を決め打ちしない。

現在の remote state 参照:

- `devgist-ops` → `devgist-tf`, `devgist-data/dev`
- `devgist-app/dev` → `devgist-ops`, `devgist-data/dev`
- `devgist-github` → `devgist-ops`

## tfvars

- `environments/**/terraform.tfvars` は **version 管理する**。gitignore にこのパスの例外を置いてある
- それ以外の `*.tfvars` は引き続き gitignore
- 人が特定される値（`cursor_oidc_subjects`、`service_account_user_emails`）は principal identifier であって true secret ではないため、committed tfvars に置く。値を知っても OIDC token の偽造も IAM principal としての認証もできない
- true secret は Terraform に渡さない。GitHub Repository Secret や `TF_VAR_*` は使わない
- 上記の list 変数は `default = []` を持つ。空なら grant が付かないだけで plan / apply は失敗しない

**true secret を扱う HCL を書く前に、[cicd.md の「secret の扱い」](cicd.md#secret-の扱い)を読んでください。**
`sensitive = true` は表示抑制であって state / plan からの排除ではありません。
Secret Manager 参照 → `ephemeral` + write-only → Terraform 管理外 → `sensitive`、の順に検討します。

根拠: [INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md)、[INFRA-ADR-020](../adr/infra/020-terraform-cicd-secret-management.md)

## 静的 CI

`.github/workflows/terraform-ci.yml`。**GCP 認証を持たない**（[INFRA-ADR-011](../adr/infra/011-terraform-ci-for-monorepo.md)）。

- `terraform init -backend=false`。backend にも state lock にも触らない
- `mock_provider "google" {}` で provider リソースをモック
- `terraform_remote_state` などの外部依存は `override_data` でモック。新しく足したら test 側にも追加する
- 対象 root は `.github/scripts/find_terraform_roots.py` が自動検出する。matrix を YAML に手書きしない
  - environment root: `environments/**/providers.tf` を持つディレクトリ
  - module test root: `modules/**/*.tftest.hcl` を持つディレクトリ
- 検証手順は Composite Action `.github/actions/terraform-check` に集約する

plan / apply は別 workflow。[cicd.md](cicd.md) を参照。

## ネットワーク

Cloud SQL は Public IP + IAM 認証（Cloud SQL Auth Proxy）。project 間の VPC Peering は使わない（[INFRA-ADR-002](../adr/infra/002-terraform-module-structure.md)）。
Public IP 全面禁止が要件になったら Private Service Connect を検討する。
