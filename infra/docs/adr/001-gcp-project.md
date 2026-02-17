# ADR-001 GCPプロジェクト構成と環境分離戦略

## Status

Accepted

## Context

### 背景

個人開発プロダクト「DevGist (Phase 1-1)」のインフラ構築を開始するにあたり、Terraformによる管理を前提としたGoogle Cloud Platform (GCP) のプロジェクト構成を決定する必要がある。

### 要件と制約

1. 環境分離: 本番環境（Prod）と開発環境（Dev）を確実に分離し、操作ミスによるデータ損失リスクを排除する。
2. 現場感のある設計: 個人開発の枠を超え、実務レベルの堅牢なセキュリティ設計（IAM管理、最小権限の原則）を実践し、学習効果を高める。
3. 開発効率の維持: インフラの複雑性により、本来の目的であるアプリケーション開発が停滞することを防ぐ。
4. 将来の拡張性: データ基盤（Data Platform）を独立させ、将来的にDevGist以外のアプリからも利用可能にする。

## Considered Options

### Option A: データ分離型（Data Decoupled）[採用]

構成: `app` (Web/API/Crawler) + `data` (DB/Storage) の2プロジェクト構成 × 2環境（Dev/Prod）

採用理由:

- バランスが最適: データ基盤を物理的に分離することでセキュリティと拡張性を担保しつつ、アプリケーション層（Frontend/Backend）は同居させることで、過度なネットワーク複雑性を回避できる。
- 学習効果: クロスプロジェクトのIAM設計という「現場でよくある課題」に取り組みつつ、挫折しないレベルの難易度に収まる。

### Option B: マイクロサービス型（Microservices）[却下]

構成: `web` (Frontend) + `backend` (API/Crawler) + `data` (DB/Storage) の3プロジェクト構成 × 2環境

却下理由:

- 通信コストが過大: FrontendとBackendを別プロジェクトにすると、Cloud Run間のセキュアな通信（Service-to-Service認証）や、CORS（Cross-Origin Resource Sharing）の設定難易度が跳ね上がる。個人開発の初期フェーズにおいて、この「配管工事」に時間を割くのはROIが低い。
- 移行容易性: アプリケーション層はStatelessであるため、将来的にトラフィックが増大してから分割しても移行コストは低い（コンテナを移動するだけ）。最初から分ける必要性がない。

### Option C: 完全統合型（Monolithic Project）[却下]

構成: `devgist` (All-in-one) の1プロジェクト構成 × 2環境

却下理由:

- "Database Migration Hell" の回避: 将来的にデータ基盤を切り出したくなった場合、稼働中のデータベースを別プロジェクトへ移行する作業は、ダウンタイムやデータ欠損リスクを伴う高難易度な作業となる。Statefulなリソース（データ）は最初から独立させておくべきである。
- 権限管理の限界: すべてのリソースが同居すると、IAM権限が「なんでもできる」状態になりがちで、セキュリティの粒度が粗くなる。

## Decision

Option A（データ分離型）を採用し、以下の5プロジェクト構成とする。

### 1. プロジェクト構成マップ

| 環境 | Data Project (Stateful) | App Project (Stateless) |
| :--- | :--- | :--- |
| Prod | `haru256-devgist-data-prod` | `haru256-devgist-app-prod` |
| Dev | `haru256-devgist-data-dev` | `haru256-devgist-app-dev` |
| Mgmt | `haru256-devgist-tf` (Terraform State管理用) | 該当なし |

### 2. アーキテクチャ原則

- Data Project: 「DevGist共通データ基盤」として定義。Cloud SQL, GCS, Vertex AI Search等を配置。他アプリからの参照も許容する設計とする。
- App Project: 「DevGistアプリケーション基盤」として定義。Next.js (Web), Python API, Crawler Jobs等を配置。
- IAM連携: AppプロジェクトのService Accountに対し、Dataプロジェクトのリソースへのアクセス権を付与する「クロスプロジェクトIAM」を採用する。

## Consequences

### Positive

- データ基盤の独立性が保たれ、将来のマルチアプリ展開にスムーズに対応できる。
- アプリ層の通信（Web⇔API）が同一プロジェクト内で完結するため、開発体験（DX）が良い。
- 本番環境と開発環境が完全に分離され、心理的安全性が高い状態で開発できる。

### Negative

- 単一プロジェクト構成に比べ、Terraformコードの記述量（特にIAM周り）が増加する。
- 開発時のgcloudコマンド操作において、プロジェクトの切り替え（`gcloud config set project`）を意識する必要がある。

### Risks / Future Review

将来、開発チーム規模が拡大し、FrontendチームとBackendチームが分かれるような状況になった場合は、Option Bへの移行（Appプロジェクトの分割）を再検討する。
