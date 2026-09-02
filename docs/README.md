# Docs

このディレクトリは、DevGist プロジェクト全体のドキュメントを管理します。

## Design Doc

プロダクトの設計思想と全体像については、[design_doc.md](design_doc.md) を参照してください。

ここには、何を達成したいのか（What）、なぜ達成したいのか（Why）、どうやって達成するか（How の概要）を記述しています。

## Architecture — 現行方針

**実装や変更に着手する前に読むのはここです。** [architecture/](architecture/) に領域ごとの現行方針をまとめています。

- [gcp-projects.md](architecture/gcp-projects.md) — GCP プロジェクトの分割と責務
- [terraform.md](architecture/terraform.md) — root module、state、cross-project 参照、tfvars、静的 CI
- [iam.md](architecture/iam.md) — Service Account、WIF、guest IAM の置き場
- [cicd.md](architecture/cicd.md) — GitHub Actions、Artifact Registry
- [crawler-runtime.md](architecture/crawler-runtime.md) — Cloud Run Job、crawler 実装の前提

## ADR (Architecture Decision Record)

技術的な設計判断の**経緯**は、[adr/](adr/) 配下で管理します。

- **運用ガイド**: [adr/README.md](adr/README.md)
- **テンプレート**: [adr/_template.md](adr/_template.md)

現在、以下のドメインの ADR が存在します。

- **infra/**: GCP プロジェクト構成、Terraform 構成、実行基盤、IAM など
- **crawler/**: クローラーの実装言語、XML パース戦略など

ADR は追記のみで運用しており、部分的な supersede が積み重なります。  
そのため ADR 群だけを読んでも現行方針は分かりません。  
「今どうなっているか」は [architecture/](architecture/)、「なぜそうしたか」は [adr/](adr/) を見てください。

各ドメインの詳細な一覧と運用ルールについては、[adr/README.md](adr/README.md) を参照してください。

## Runbooks

手順の正本は [runbooks/](runbooks/) にあります。
