---
name: adr-workflow
description: Use when making or revising architecture decisions that affect system boundaries, infrastructure, data models, execution platforms, authentication, deployment, or long-lived operational policy. Also use when taking stock of accumulated ADRs (棚卸し) or when docs/architecture/ needs to be reconciled with docs/adr/.
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
2. **現行方針を `docs/architecture/` で確認する。** ADR 群から現状を組み立てない。
3. 経緯や却下理由が必要なら、そこからリンクされている ADR を読む。
4. 主なトレードオフと、少なくとも 1 つの有力な代替案を整理する。
5. 影響の大きい判断は、実装前にユーザーと合意する。
6. 長期的な設計や運用に影響するなら、ADR を追加するか、未確定 ADR のみ更新する。
7. 新しい ADR を追加したら `docs/adr/README.md` の一覧も更新する。
8. **同じ PR で、対応する `docs/architecture/*.md` を更新する。**

## Architecture Doc の更新（ADR を書くたび）

`docs/adr/` は追記のみの決定ログであり、それ単体では「今どうなっているか」を答えられない。
現行方針の正本は `docs/architecture/` である。ADR を書いたら必ず反映する。

反映のしかた。

- 新しい ADR が決めた**結論だけ**を、断定形で該当ファイルに書く。経緯・比較・却下理由は書かない
- 打ち消した記述は**削除する**。「以前は X だったが今は Y」と並べない
- 部分的な supersede なら、生き残る側と捨てる側を ADR 側に書き、architecture 側には**畳んだ結果だけ**を書く
- 誤読しやすい部分 supersede は、architecture 側に引用ブロックで 1〜2 行の注意書きを残してよい
  （例: 「ADR-014 が IAM を app-dev に置いた判断は捨てられている」）
- 根拠 ADR へのリンクを添える

領域と ADR の対応は [`docs/architecture/README.md`](../../../docs/architecture/README.md) の一覧を参照する。

## Architecture Doc の棚卸し

ADR が増えて相互参照が追えなくなったとき、または architecture doc の鮮度が疑わしいときに行う。
「ADR を棚卸しして」「現行方針を更新して」と言われた場合もこれ。

対象範囲をユーザーと合意してから始める（全体か、特定領域だけか）。

1. **差分を取る**
   `git log --oneline -- docs/adr/` で、architecture doc の最終更新以降に追加・変更された ADR を洗い出す。
   全体棚卸しなら全 ADR が対象。

2. **ステータスの実態を確認する**
   ファイル本文の `## Status` を読む。`docs/adr/README.md` の一覧の値を信用しない。
   `Superseded` のスタンプが付いていても、本文の一部が現行方針として生きていることがある。

3. **打ち消しの範囲を特定する**
   新しい ADR ごとに「何を捨て、何を維持したか」を書き出す。
   ADR の `## Status` 直下と `## Conclusion` に書かれていることが多い。
   全体を supersede しているのか、一部だけなのかを必ず区別する。

4. **矛盾と迷子を洗い出す**
   - 現行方針が `Superseded` の ADR にしか書かれていないもの
   - architecture doc の記述と、より新しい ADR の結論が食い違うもの
   - どの architecture ファイルにも畳まれていない ADR
   - `docs/adr/` の外に残った ADR の複製

5. **実装と突き合わせる**
   ADR が決めたことが実際に入っているかを確認する。
   Terraform / workflow / コードを見て、ADR が Next Steps のまま未実装なら architecture doc にそう書く。
   「決めたこと」と「動いていること」を混同しない。

6. **畳んで書き直す**
   該当ファイルを更新する。古い記述は削除する。追記で済ませない。

7. **報告する**
   見つかった矛盾、未実装の ADR、判断が必要な点をユーザーに提示する。
   ステータスの訂正や ADR 本文の修正が必要なら、それは別途合意を取る（`Accepted` な ADR の本文は勝手に書き換えない）。

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

- 決定記録の正本は `docs/adr/`。**現行方針の正本は `docs/architecture/`**
- 運用ガイドは `docs/adr/README.md`
- テンプレートは `docs/adr/_template.md`
- `INFRA-ADR-001` や `CRAWLER-ADR-002` のような namespace 付き ID を使う
- `Accepted` な ADR は履歴として残し、方針変更時は新しい ADR を追加して supersede する
- 既存 ADR を更新するのは、`Proposed` 段階の追記や誤記修正、リンク修正など履歴を壊さない変更に限る

### 部分 supersede の書き方

既存 ADR の一部だけを置き換えるときは、`## Status` に**両方**を明記する。

- 何を捨てるか（どの判断が無効になるか）
- 何を維持するか（引き続き有効な部分）

置き換えられる側の ADR にも、`## Status` に 1〜2 行で対応を書く。
本文は書き換えず、当時の判断の記録として残す。

`Superseded` のスタンプだけを付けて済ませない。
全体が無効だと誤読され、実際には生きている判断まで捨てられる。

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
- ADR だけ追加して `docs/architecture/` を更新せず、現行方針を追えなくする
- 部分的にしか置き換えていないのに `Superseded` とだけ書く
- `docs/architecture/` に経緯を書き足して、決定ログの複製にしてしまう
