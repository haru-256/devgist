---
name: adr-workflow
description: Use when making or revising architecture decisions that affect system boundaries, infrastructure, data models, execution platforms, authentication, deployment, or long-lived operational policy
---

# ADR Workflow

## Overview

この skill は、単なる実装ではなく、後から追跡できる形で残すべき設計判断を扱うときに使います。

目的は明確です。長期的な設計や運用に影響する判断について、先に合意を取り、その後 ADR に記録します。

## When to Use

以下のいずれかを含むタスクで使います。

- インフラ、実行基盤、デプロイ方式、セキュリティ方針を選定または変更する
- データモデル、状態管理、サービス境界を変える
- 既存 ADR を supersede する
- 将来の開発者が判断経緯を参照する必要がある

以下では使いません。

- 合意済み設計の範囲に収まるローカルなリファクタリング
- 命名整理、ヘルパー抽出、小さな interface 整理
- システムレベルの方針を変えない実装詳細

## Workflow

1. 判断対象が設計判断か、実装詳細かを切り分ける。
2. 既存 ADR と関連ドキュメントを確認する。
3. 主なトレードオフと、少なくとも 1 つの有力な代替案を整理する。
4. 影響の大きい判断は、実装前にユーザーと合意する。
5. 長期的な設計や運用に影響するなら、ADR を追加するか、未確定 ADR のみ更新する。
6. 新しい ADR を追加したら `docs/adr/README.md` の一覧も更新する。

## Consultation Boundary

以下に影響する変更では、ユーザーとの合意が必要です。

- インフラや実行基盤
- 外部 interface や互換性保証
- 認証、認可、セキュリティ方針
- 永続データの構造や状態の責務
- デプロイ、ロールバック、運用負荷

以下は停止せず進めてよい範囲です。

- 合意済み設計の範囲でのローカルな実装判断
- アーキテクチャ影響のない小さなリファクタリング
- 既存判断を明確にするだけのドキュメント更新

## ADR Rules

- ADR の正本は `docs/adr/`
- 運用ガイドは `docs/adr/README.md`
- テンプレートは `docs/adr/_template.md`
- `INFRA-ADR-001` や `CRAWLER-ADR-002` のような namespace 付き ID を使う
- `Accepted` な ADR は履歴として残し、方針変更時は新しい ADR を追加して supersede する
- 既存 ADR を更新するのは、`Proposed` 段階の追記や誤記修正、リンク修正など履歴を壊さない変更に限る

## Minimum ADR Content

- conclusion
- status
- context と constraints
- considered options
- decision
- consequences
- next steps
- related documents

## Common Mistakes

- すべてのリファクタリングを ADR レベルの判断として扱う
- 影響の大きい設計変更を、合意前に実装してしまう
- ADR を意思決定記録ではなく実装日誌として書く
- ADR ルールを複数箇所に重複記載して乖離させる
