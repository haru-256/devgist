# Infrastructure

アプリケーションを稼働させるためのインフラ構成コードを管理するディレクトリです。

## 役割

- **Terraform**: クラウドプロバイダー（AWS/GCPなど）のリソース管理。
- **Kubernetes**: アプリケーションのデプロイメント設定（Manifests, Helm Chartsなど）。
- CI/CDパイプラインに関連するスクリプトや設定。

## 関連 ADR

インフラに関する Architecture Decision Record (ADR) は [docs/adr/](../docs/adr/) 配下で管理します。

- 運用ガイド: [docs/adr/README.md](../docs/adr/README.md)
- テンプレート: [docs/adr/_template.md](../docs/adr/_template.md)
- `INFRA-ADR-001`: [docs/adr/infra/001-gcp-project-structure.md](../docs/adr/infra/001-gcp-project-structure.md)
- `INFRA-ADR-002`: [docs/adr/infra/002-terraform-module-structure.md](../docs/adr/infra/002-terraform-module-structure.md)
- `INFRA-ADR-003`: [docs/adr/infra/003-crawler-execution-platform.md](../docs/adr/infra/003-crawler-execution-platform.md)
- `INFRA-ADR-004`: [docs/adr/infra/004-separate-tf-and-ops-projects.md](../docs/adr/infra/004-separate-tf-and-ops-projects.md)
- `INFRA-ADR-005`: [docs/adr/infra/005-terraform-environment-slicing.md](../docs/adr/infra/005-terraform-environment-slicing.md)
- `INFRA-ADR-006`: [docs/adr/infra/006-cross-project-output-sharing.md](../docs/adr/infra/006-cross-project-output-sharing.md)
- `INFRA-ADR-009`: [docs/adr/infra/009-cross-project-iam-ownership.md](../docs/adr/infra/009-cross-project-iam-ownership.md)
- `INFRA-ADR-015`: [docs/adr/infra/015-guest-iam-downstream.md](../docs/adr/infra/015-guest-iam-downstream.md)
- `INFRA-ADR-016`: [docs/adr/infra/016-github-actions-wif-and-crawler-image-push.md](../docs/adr/infra/016-github-actions-wif-and-crawler-image-push.md)
- `INFRA-ADR-017`: [docs/adr/infra/017-github-actions-terraform-managed-variables.md](../docs/adr/infra/017-github-actions-terraform-managed-variables.md)
- `INFRA-ADR-018`: [docs/adr/infra/018-artifact-registry-cost-controls.md](../docs/adr/infra/018-artifact-registry-cost-controls.md)
- `INFRA-ADR-019`: [docs/adr/infra/019-github-actions-terraform-plan-apply.md](../docs/adr/infra/019-github-actions-terraform-plan-apply.md)

このディレクトリ配下の `infra/docs/adr/` は互換性維持のための参照パスであり、正本は [docs/adr/](../docs/adr/) 側です。

## Current GCP Project Responsibilities

現時点の想定 GCP project 構成は、`tf` と `ops` を分離した 4 系統です。

```mermaid
graph TD
    TF[haru256-devgist-tf<br/>Terraform state only]
    OPS[haru256-devgist-ops<br/>Artifact Registry / CI-CD / Cursor WIF]
    DATA[haru256-devgist-data-{env}<br/>Stateful data]
    APP[haru256-devgist-app-{env}<br/>Stateless compute]

    OPS --> APP
    APP --> DATA
```

- `haru256-devgist-tf`
  - Terraform state bucket 専用 project
  - 原則として tfstate 管理以外の常設リソースは置かない

- `haru256-devgist-ops`
  - Artifact Registry
  - GitHub Actions 連携、WIF、共通 CI/CD 用 Service Account などの運用基盤
  - Cursor Cloud 用 OIDC WIF pool / provider（認証は [INFRA-ADR-014](../docs/adr/infra/014-cursor-oidc-wif-direct-resource-access.md)、guest IAM の置き場は [INFRA-ADR-015](../docs/adr/infra/015-guest-iam-downstream.md)）
  - GitHub Actions 用 OIDC WIF pool / provider（認証は [INFRA-ADR-016](../docs/adr/infra/016-github-actions-wif-and-crawler-image-push.md)。初期 IAM は crawler Artifact Registry への push のみ）

- `haru256-devgist-data-{env}`
  - GCS datalake
  - Cloud SQL / BigQuery など stateful data

- `haru256-devgist-app-{env}`
  - Cloud Run Jobs
  - frontend / backend API など stateless compute

### Responsibility Notes

- crawler の image store は `ops` project 側の `Artifact Registry` に置く
- crawler の実行先は `app` project 側の `Cloud Run Jobs` とする
- crawler の保存先 datalake は `data` project 側に置く。data は箱であり、guest IAM は持たない
- datalake の guest IAM は identity と箱の下流が書く。crawler SA は app、Cursor WIF は ops（[INFRA-ADR-015](../docs/adr/infra/015-guest-iam-downstream.md)）
- project 構成の判断根拠は `INFRA-ADR-001` から `INFRA-ADR-006` を参照する

## Service To Project Mapping

`crawler` は 1 つの environment に閉じず、`ops / app / data` の各 project に責務を分解して配置します。

| Service | Project | Responsibility | Source of Truth |
|---|---|---|---|
| `crawler` | `haru256-devgist-ops` | `Artifact Registry` repository | `devgist-ops` Terraform state |
| `crawler` | `haru256-devgist-app-dev` | `Cloud Run Jobs` / app runtime | `devgist-app/dev` Terraform state |
| `crawler` | `haru256-devgist-data-dev` | `GCS datalake` などの保存先 | `devgist-data/dev` Terraform state |

## Terraform Apply Order

project ごとに state を分けているため、`crawler` 関連の apply は依存順に実行します。

```mermaid
graph LR
    TF[devgist-tf] --> DATA[devgist-data/dev]
    TF --> OPS[devgist-ops]
    DATA --> OPS
    OPS --> APP[devgist-app/dev]
    DATA --> APP
```

### Order

1. `devgist-tf`
   - tfstate bucket を先に作成する
2. `devgist-data/dev`
   - datalake など crawler の保存先を箱として作成する
3. `devgist-ops`
   - `Artifact Registry`、Cursor 用 WIF、GitHub Actions 用 WIF を作成する
   - Cursor Cloud の federated principal へ data-dev datalake の `objectViewer` / `objectCreator` を付与する
   - GitHub Actions の CI principal（`attribute.ci_scope`）へ crawler Artifact Registry の writer と plan / apply 用の IAM を付与する（[INFRA-ADR-019](../docs/adr/infra/019-github-actions-terraform-plan-apply.md)）
4. `devgist-app/dev`
   - `terraform_remote_state` で `ops/data` の outputs を参照しながら app 側 compute を作成する
   - crawler SA へ同じ datalake の読書きを付与する
5. `devgist-github`（ローカルのみ）
   - GitHub Environment / repository variable を書く。`ops` の outputs を `terraform_remote_state` で参照する

`main` への merge 後は `devgist-data/dev` → `devgist-ops` → `devgist-app/dev` が CI で自動 apply される（[INFRA-ADR-019](../docs/adr/infra/019-github-actions-terraform-plan-apply.md)）。`devgist-tf` と `devgist-github` は CI に載せず、ローカルで apply する。

### Notes

- `devgist-ops` は `devgist-data/dev` の bucket 名を `terraform_remote_state` で参照する。ops の identity が箱へ grant するあいだ、箱を先に apply する（[INFRA-ADR-015](../docs/adr/infra/015-guest-iam-downstream.md)）
- `devgist-app/dev` は `devgist-ops` と `devgist-data/dev` の outputs を `terraform_remote_state` で参照する
- secret は Terraform outputs では渡さず、`GCP Secret Manager` を app runtime から参照する
- 旧 `environments/crawler` は legacy 扱いで、最終的には `ops/app/data` 側へ整理する
- Cursor Cloud の subject allowlist（`cursor_oidc_subjects`）は ops の `terraform.tfvars` に書く。空なら datalake IAM member が付かない
- Cursor 用 WIF は federated principal への direct resource access である。GitHub Actions 用 WIF も direct resource access だが、pool は分ける（[INFRA-ADR-016](../docs/adr/infra/016-github-actions-wif-and-crawler-image-push.md)）。GitHub Actions の認可は `attribute.ci_scope` 単位（[INFRA-ADR-019](../docs/adr/infra/019-github-actions-terraform-plan-apply.md)）。terraform plan / apply の CI は 019 を参照
- GitHub Actions の `workload_identity_provider` と crawler image の `REPO_URL` / `IMAGE_NAME` は、`environments/devgist-github` root の Terraform が GitHub の repository variable として書く（[INFRA-ADR-017](../docs/adr/infra/017-github-actions-terraform-managed-variables.md)。置き場は 019 が ops から `devgist-github` root に変えた）
