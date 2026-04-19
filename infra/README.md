# Infrastructure

アプリケーションを稼働させるためのインフラ構成コードを管理するディレクトリです。

## 役割

- **Terraform**: クラウドプロバイダー（AWS/GCPなど）のリソース管理。
- **Kubernetes**: アプリケーションのデプロイメント設定（Manifests, Helm Chartsなど）。
- CI/CDパイプラインに関連するスクリプトや設定。

## 関連 ADR

インフラに関する Architecture Decision Record (ADR) は `docs/adr/` 配下で管理します。

- 運用ガイド: `docs/adr/README.md`
- テンプレート: `docs/adr/_template.md`
- `INFRA-ADR-001`: `docs/adr/infra/001-gcp-project-structure.md`
- `INFRA-ADR-002`: `docs/adr/infra/002-terraform-module-structure.md`
- `INFRA-ADR-003`: `docs/adr/infra/003-crawler-execution-platform.md`

このディレクトリ配下の `infra/docs/adr/` は互換性維持のための参照パスであり、正本は `docs/adr/` 側です。
