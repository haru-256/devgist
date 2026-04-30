# AGENTS Guide

このファイルは、DevGist リポジトリで作業するエージェント向けの共通ガイドです。

## 基本方針

- ローカル最適ではなく、プロジェクト全体の整合性を優先する
- 設計判断と実装詳細を混同しない
- 長期的に残る設計判断は、後から追跡できる形で残す

## 設計判断の扱い

以下に当てはまる変更は、実装前にユーザーと合意を取ること。

- インフラや実行基盤を選定・変更する
- データモデル、状態管理、責務境界を大きく変える
- 認証、認可、セキュリティ方針に影響する
- デプロイ方式、運用負荷、互換性保証を変える
- 既存 ADR を supersede する

一方で、以下はユーザー確認なしに進めてよい。

- 合意済み設計の範囲での実装
- 小さなリファクタリングや命名整理
- 挙動や責務境界を変えないドキュメント更新

## ADR

設計判断を伴う変更では、ADR の要否を確認すること。

- ADR の正本: [`docs/adr/`](docs/adr/)
- 詳細な進め方: [`.agents/skills/adr-workflow/SKILL.md`](.agents/skills/adr-workflow/SKILL.md)
- ADR 運用ガイド: [`docs/adr/README.md`](docs/adr/README.md)
- ADR テンプレート: [`docs/adr/_template.md`](docs/adr/_template.md)

ADR の判断基準、相談の境界、記録ルールなどの詳細は skill を参照すること。

## やってはいけないこと

- ユーザーの合意なしに設計判断を変更すること
- タスクの計画時に、supoerpowers:writing-plans を使わず、タスクの目的やステップを明確にせずに進めること。また、ユーザーからの明確な同意なしにタスクを開始すること。
- タスクの実行時に、supoerpowers:subagent-driven-development や superpowers:executing-plans を使わず、タスク管理や進捗報告を怠ること。
- サブエージェントを使う場合は、タスクの難易度や複雑さに応じてmodelやreasoningを適切に選択せず、タスクの内容や進捗をユーザーに報告しないこと。
- terraform apply やリソース変更を伴うタスクを、ユーザーの明確な同意なしに実行すること。必ずterraform plan の内容をユーザーに提示し、承認を得てから apply を実行すること。
