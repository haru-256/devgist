# Crawler Cloud Run Job 構築計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ADR-010 に従い、Crawler を Cloud Run Job として動かすための Terraform コードを実装し、ローカルでビルドした Docker image を Artifact Registry に push して、Terraform apply まで完了させる。

**Architecture:** Terraform で Cloud Run Job と Cloud Scheduler を管理し、CI/CD は image build/push と Terraform apply のみを担当する。image 参照は digest 形式で Terraform 変数として渡す。

**Tech Stack:** Terraform, Google Cloud Run Jobs, Cloud Scheduler, Artifact Registry, Docker

---

## 前提・現状確認

- **Project 構成:**
  - `haru256-devgist-ops`: Artifact Registry (`crawler` repo 作成済み)
  - `haru256-devgist-app-dev`: Cloud Run Job 実行環境
  - `haru256-devgist-data-dev`: GCS datalake
- **既存リソース:**
  - `devgist-ops` に `crawler` Artifact Registry repository あり
  - `devgist-app/dev` に `crawler` Service Account あり（GCS 書き込み・AR 読み取り権限付与済み）
  - `devgist-data/dev` に GCS datalake bucket あり
- **未作成:**
  - Cloud Run Job リソース
  - Cloud Scheduler リソース
  - Dockerfile
  - crawler image

---

## Phase 1: Docker Image ビルドと Artifact Registry への Push

Terraform から Cloud Run Job を作成する際、`crawler_image` 変数に存在しない image を指定するとエラーになる可能性があるため、**先に image を build/push する**。

### Task 1: Dockerfile を作成

**Files:**
- Create: `workflows/crawler/Dockerfile`

- [ ] **Step 1: Python ベースの Dockerfile を作成**

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 依存ファイルをコピー
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# PYTHONPATH を設定して src/ 配下のモジュールを解決できるようにする
ENV PYTHONPATH=/app/src

# システム Python に依存をインストール（venv は不要）
RUN uv pip install --no-dev --system .

# エントリーポイント
CMD ["python", "-m", "crawler.main"]
```

- [ ] **Step 2: ビルドテスト**

Run:
```bash
cd workflows/crawler
docker build -t crawler:test .
```

### Task 2: Image を Artifact Registry に Push

**Files:**
- Modify: `infra/terraform/environments/devgist-app/dev/terraform.tfvars`（Phase 3 で実施）

- [ ] **Step 1: Docker 認証設定**

Run:
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

- [ ] **Step 2: Image ビルド・タグ付け**

Run:
```bash
cd workflows/crawler
export IMAGE_TAG=$(git rev-parse --short HEAD)
export REPO_URL="us-central1-docker.pkg.dev/haru256-devgist-ops/crawler"
docker build -t "${REPO_URL}/crawler:${IMAGE_TAG}" .
```

- [ ] **Step 3: Image Push**

Run:
```bash
docker push "${REPO_URL}/crawler:${IMAGE_TAG}"
```

- [ ] **Step 4: Digest 取得**

Run:
```bash
gcloud artifacts docker images describe "${REPO_URL}/crawler:${IMAGE_TAG}" \
  --format='value(image_summary.digest)'
```

Expected output: `sha256:xxxxxxxx...`

---

## Phase 2: Terraform コード実装

image が push 済みであることを確認してから Terraform コードを追加する。

### Task 3: Cloud Run Job 用 Terraform リソースを追加

**Files:**
- Modify: `infra/terraform/environments/devgist-app/dev/main.tf`
- Modify: `infra/terraform/environments/devgist-app/dev/variables.tf`
- Modify: `infra/terraform/environments/devgist-app/dev/outputs.tf`

- [ ] **Step 1: `cloudscheduler.googleapis.com` を required_services に追加**

```hcl
locals {
  required_services = [
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com", # 追加
  ]
  ...
}
```

- [ ] **Step 2: `crawler_image` 変数を `variables.tf` に追加**

```hcl
variable "crawler_image" {
  type        = string
  description = "Container image digest for the crawler Cloud Run Job (e.g. us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@sha256:...)"
}
```

- [ ] **Step 3: Cloud Run Job リソースを `main.tf` に追加**

Secret にするほどでない環境変数は `env` block で直接設定する。

```hcl
resource "google_cloud_run_v2_job" "crawler" {
  name     = "crawler"
  location = var.gcp_default_region
  project  = data.google_project.project.project_id

  template {
    template {
      service_account = module.service_accounts.emails["crawler"]
      containers {
        image = var.crawler_image
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
        env {
          name  = "GCS_BUCKET_NAME"
          value = data.terraform_remote_state.data.outputs.datalake_bucket_name
        }
        env {
          name  = "GCP_PROJECT_ID"
          value = data.google_project.project.project_id
        }
        env {
          name  = "LOG_LEVEL"
          value = "INFO"
        }
      }
    }
  }

  depends_on = [module.required_project_services]
}
```

- [ ] **Step 4: Cloud Scheduler リソースを `main.tf` に追加（一旦コメントアウト）**

初期フェーズでは手動実行とし、Scheduler は後で有効化する。

```hcl
# TODO: 手動実行で問題なければ有効化する
# resource "google_cloud_scheduler_job" "crawler" {
#   name             = "crawler-scheduler"
#   description      = "Trigger crawler Cloud Run Job periodically"
#   schedule         = "0 2 * * *" # 毎日午前2時（例）
#   time_zone        = "Asia/Tokyo"
#   project          = data.google_project.project.project_id
#   region           = var.gcp_default_region
#
#   http_target {
#     http_method = "POST"
#     uri         = "https://${var.gcp_default_region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${data.google_project.project.project_id}/jobs/crawler:run"
#     oauth_token {
#       service_account_email = module.service_accounts.emails["crawler"]
#     }
#   }
#
#   depends_on = [google_cloud_run_v2_job.crawler]
# }
```

- [ ] **Step 5: `outputs.tf` に Cloud Run Job 情報を追加**

```hcl
output "crawler_job_name" {
  value       = google_cloud_run_v2_job.crawler.name
  description = "The name of the crawler Cloud Run Job"
}

output "crawler_job_id" {
  value       = google_cloud_run_v2_job.crawler.id
  description = "The ID of the crawler Cloud Run Job"
}
```

- [ ] **Step 6: Terraform fmt & validate**

Run:
```bash
cd infra/terraform/environments/devgist-app/dev
terraform fmt
terraform validate
```

---

## Phase 3: Terraform Apply

### Task 4: Terraform 変数に image digest を設定して apply

**Files:**
- Modify: `infra/terraform/environments/devgist-app/dev/terraform.tfvars`

- [ ] **Step 1: `terraform.tfvars` に `crawler_image` を追加**

```hcl
gcp_project_id              = "haru256-devgist-app-dev"
gcp_default_region          = "us-central1"
service_account_user_emails = ["yohei.okabayashi@haru256.dev", "admin@haru256.dev"]
crawler_image               = "us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@sha256:xxxxxxxx..."
```

- [ ] **Step 2: Terraform Plan**

Run:
```bash
cd infra/terraform/environments/devgist-app/dev
terraform plan -var-file=terraform.tfvars
```

- [ ] **Step 3: Terraform Apply**

Run:
```bash
terraform apply -var-file=terraform.tfvars
```

- [ ] **Step 4: Cloud Run Job 手動実行テスト**

Run:
```bash
gcloud run jobs execute crawler --project=haru256-devgist-app-dev --region=us-central1
```

- [ ] **Step 5: ログ確認**

Run:
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crawler" \
  --project=haru256-devgist-app-dev --limit=50
```

---

## 実行後の確認事項

- [ ] Cloud Run Job の実行が成功すること
- [ ] Cloud Scheduler からの定期実行が設定されていること
- [ ] GCS datalake にデータが書き込まれること
- [ ] ログにエラーが出ていないこと

---

## リスクと注意点

- `crawler_image` は digest 形式（`@sha256:...`）で指定すること
- Cloud Scheduler の oauth_token には crawler SA を使うため、SA に `run.jobs.run` 権限が必要
- 初期フェーズでは Terraform apply 失敗時に「image は push 済みだが Job に反映されていない」状態になりうる
- 旧 `environments/crawler` は最終的に整理・削除するが、今回のスコープでは変更しない
