# [ADR-002] Terraform構成: ドメイン駆動モジュールとマルチプロジェクト戦略の採用

## Status (ステータス)

* Accepted (2026-02-17)

## Context (背景・課題)

### 背景

DevGistプロジェクトのPhase 1（Deep Search）および将来のPhase 2（Discovery Feed）を見据えたインフラ構築を行う。
システムは「論文収集（Crawler）」「構造化・分析（Intelligence）」「検索・提供（App）」の3つの異なるワークロードを持ち、それぞれデータの性質やライフサイクルが異なる。

### 課題と制約

1. **データの性質の分離**: アプリケーションが参照するトランザクションデータ（OLTP）と、クローラーが蓄積する分析用データ（OLAP/Data Lake）が混在しており、これらを適切に管理する必要がある。
2. **学習目的（Hard Mode）**: 個人開発ではあるが、エンタープライズ環境の実践的なスキル習得のため、単一プロジェクトではなく「環境および役割によるプロジェクト分割」を行いたい。
3. **スケーラビリティ**: 将来的にデータ分析基盤（BigQueryなど）や新しいワーカーが増えた際、アプリ本体に影響を与えずに拡張できる構成が求められる。

### 検討した選択肢

* Option A: モノリス構成 (Single Project / Single State)
    * 全てのリソースを1つの `main.tf` と1つのGCPプロジェクトで管理する。
    * 簡単だが、破壊的変更のリスクが高く、権限管理が雑になる。

* Option B: 技術レイヤー分割 (Network / Storage / Compute)
    * リソースの種類で分割する。一般的だが、DevGistのように「アプリ用DB」と「分析用DB」のライフサイクルが異なる場合、管理が複雑になる。

* Option C: ドメイン駆動分割 (App / Data Platform) ✅ **採用**
    * 「誰が使うデータか」「ライフサイクルはどうか」に基づいて分割する。

## Decision (決定事項)

我々は Option C: ドメイン駆動分割 を採用し、以下の構成で実装することを決定した。

### 1. GCPプロジェクト構成 (5プロジェクト体制)

役割と環境を物理的に分離し、堅牢なセキュリティと運用フローを確立する。

* Ops Project: `haru256-devgist-tf`
    * Terraform State 保存用バケット
    * Artifact Registry
    * Cloud Build

* Data Project: `haru256-devgist-data-{env}`（dev/staging/prod 環境ごと）
    * VPC, Subnet, Firewall
    * Cloud SQL（OLTP用）
    * GCS Data Lake（Raw Data 一時保管）
    * BigQuery（分析基盤）

* App Project: `haru256-devgist-app-{env}`（dev/staging/prod 環境ごと）
    * VPC, Subnet, Firewall
    * Cloud Run（Frontend / Backend API）

### 2. Terraform モジュール構成

責務（Responsibility）とデータの性質（OLTP/OLAP）に基づき、以下のモジュールに分割する。

| モジュール | 役割 | リソース種別 | 環境 |
|-----------|------|-----------|------|
| `google_project_services` | API有効化（依存関係解決） | Service Activation | 全環境 |
| `tfstate_gcs_bucket` | Terraform State バケット管理 | GCS Bucket | Ops のみ |
| `network_base` | VPC ネットワーク基盤 | VPC, Subnet, Firewall | Data / App 各環境 |
| `app_databases` (OLTP) | アプリケーション用DB | Cloud SQL | Data 各環境 |
| `data_platform` (OLAP) | 分析・バッチ処理基盤 | GCS, BigQuery, Pub/Sub | Data 各環境 |
| `collector` / `intelligence` / `backend_api` | ワークロード (Compute層) | Cloud Run | App 各環境 |

#### モジュール責務の詳細

`data_platform` モジュール

* クローラーが生成する Raw Data を一時保管する GCS Datalake バケット
* 生データのライフサイクル: STANDARD → NEARLINE (30日無アクセス) → COLDLINE (90日無アクセス) → ARCHIVE（autoclass）
* `prevent_destroy = true` で誤削除防止

`app_databases` モジュール

* アプリケーションが直接依存するトランザクションDB（Cloud SQL）
* Vector Search Index（将来）

### 3. デプロイメントとState管理

* 2段階デプロイ: Data Project (土台) → App Project (上物) の順に適用

  ```bash
  # Step 1: Data インフラ構築
  cd infra/terraform/environments/devgist-data/dev
  terraform apply
  
  # Step 2: App インフラ構築
  cd infra/terraform/environments/devgist-app/dev
  terraform apply
  ```

* Remote State参照: App側のTerraformは、Data側のState (`outputs`) を参照してVPC IDやDB接続情報を取得

  ```hcl
  data "terraform_remote_state" "data" {
    backend = "gcs"
    config = {
      bucket = "haru256-devgist-tf-state"
      prefix = "dev/data"
    }
  }
  
  resource "google_cloud_run_service" "backend" {
    # ... 
    environment_variables = {
      DB_HOST = data.terraform_remote_state.data.outputs.cloud_sql_private_ip_address
    }
  }
  ```

### 4. ネットワーク接続戦略

* Cloud SQL Auth Proxy (Plan A): Public IP + IAM認証を採用
    * プロジェクト間のVPC Peering（推移的ルーティング問題）を回避
    * Identity-Awareなセキュリティを担保

* VPC Peering (Plan B): 将来的に検討
    * より厳密なネットワークアイソレーションが必要な場合

## Consequences (結果・影響)

### Positive (メリット)

* 責務の明確化
    * 「検索が遅いなら `app_databases`」
    * 「分析基盤の容量なら `data_platform`」
    * 修正すべき箇所が直感的に分かる

* 安全性の向上 (Reduced Blast Radius)
    * 分析基盤（Data Lake）を操作しても、本番アプリのDB設定を誤って破壊するリスクが物理的に遮断される
    * プロジェクト分離により権限管理が厳密化

* スケーラビリティ
    * 新しいワークロード（新しいCrawler、BatchJob等）を追加する際、既存モジュールに影響なく `data_platform` を拡張可能
    * 分析基盤への要件変更が App 側に波及しない

* 実践的な経験値
    * クロスプロジェクトでの権限管理
    * Remote State 間参照
    * エンタープライズレベルの Terraform パターン習得

### Negative (デメリット)

* 初期構築コスト
    * 5つのGCPプロジェクト作成と初期設定
    * State バケット (tfstate_gcs_bucket) のBootstrap 作業
    * 書き始めるまでの準備に手間がかかる

* デプロイの手間
    * インフラ全体を更新する場合、Data → App の順序で複数回 `terraform apply` を実行する必要がある
    * 自動化（CI/CD）が必須になる

* 学習曲線
    * Remote State 参照の理解が必要
    * デバッグが単一プロジェクト構成より複雑になる可能性

### Risks / Future Review (将来の課題)

* ネットワーク要件の厳格化
    * 将来的に「Public IP完全禁止」となった場合、Private Service Connect (PSC) への移行を検討する必要がある

* VPC Peering管理
    * 現状は疎通確認用としているが、将来的にGCE等が追加された場合、CIDR管理とルーティング設計の再考が必要になる可能性がある

* Cost分析の複雑化
    * 複数プロジェクトにリソースが分散するため、請求書の追跡と最適化がやや複雑になる
    * 定期的なコスト監査（GCP Cost Analysis）が必要

## Next Steps

1. Ops Project (haru256-devgist-tf) の初期構築
   * State バケット作成
   * IAM ロール設定

2. Data Project の Terraform 環境構築
   * `network_base` モジュール実装
   * `data_platform` モジュール実装（GCS Datalake）
   * `app_databases` モジュール実装（Cloud SQL）

3. App Project の Terraform 環境構築
   * Remote State 参照設定
   * Cloud Run リソース定義

4. CI/CD パイプライン構築
   * Cloud Build による自動デプロイ
   * Policy as Code (Terraform Cloud/Sentinel) 導入検討

## Related Documents

* [ADR-001] GCP Project Structure
* [Module: data_platform](../../modules/data_platform/README.md)
* [Module: app_databases](../../modules/app_databases/README.md)
