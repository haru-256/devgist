# Infrastructure

アプリケーションを稼働させるためのインフラ構成コードを管理するディレクトリです。

## 役割

- **Terraform**: クラウドプロバイダー（AWS/GCPなど）のリソース管理。
- **Kubernetes**: アプリケーションのデプロイメント設定（Manifests, Helm Chartsなど）。
- CI/CDパイプラインに関連するスクリプトや設定。
