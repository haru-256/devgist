# Docs

このディレクトリは、DevGist プロジェクト全体のドキュメントを管理します。

## Design Doc

プロダクトの設計思想と全体像については、[design_doc.md](design_doc.md) を参照してください。

ここには、何を達成したいのか（What）、なぜ達成したいのか（Why）、どうやって達成するか（How の概要）を記述しています。

## ADR (Architecture Decision Record)

技術的な設計判断は、[adr/](adr/) 配下で管理します。

- **運用ガイド**: [adr/README.md](adr/README.md)
- **テンプレート**: [adr/_template.md](adr/_template.md)

現在、以下のドメインの ADR が存在します。

- **infra/**: GCP プロジェクト構成、Terraform 構成、実行基盤、IAM など（9件）
- **crawler/**: クローラーの実装言語、XML パース戦略など（2件）

各ドメインの詳細な一覧と運用ルールについては、[adr/README.md](adr/README.md) を参照してください。
