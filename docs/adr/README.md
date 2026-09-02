# ADR 運用ガイド

このディレクトリは、DevGist 全体の Architecture Decision Record (ADR) を管理するための正本ディレクトリです。  
インフラ、クローラー、バックエンドなど、個別ディレクトリに閉じない設計判断をここに集約します。

> **「今どうなっているか」を知りたい場合は、[`docs/architecture/`](../architecture/) を読んでください。**
>
> ADR は追記のみで運用します。新しい ADR が既存の ADR を**部分的にしか**打ち消さないことがあり、
> `Accepted` / `Superseded` のステータスだけでは現行方針を判断できません。
> ADR 群を横断して現状を組み立てるのではなく、畳んだ結果である `docs/architecture/` を参照してください。
>
> | | 何を持つか |
> |---|---|
> | `docs/architecture/` | **今こうする**。断定形の現行ルール |
> | `docs/adr/` | **なぜそうしたか**。判断時点の記録 |

## ADR 一覧

| ID | ドメイン | タイトル | ステータス | 正本パス |
|---|---|---|---|---|
| `INFRA-ADR-001` | `infra` | GCPプロジェクト構成と環境分離戦略 | Accepted | [docs/adr/infra/001-gcp-project-structure.md](infra/001-gcp-project-structure.md) |
| `INFRA-ADR-002` | `infra` | Terraform構成: ドメイン駆動モジュールとマルチプロジェクト戦略の採用 | Accepted | [docs/adr/infra/002-terraform-module-structure.md](infra/002-terraform-module-structure.md) |
| `INFRA-ADR-003` | `infra` | Crawler実行基盤として Cloud Run Jobs を採用する | Accepted | [docs/adr/infra/003-crawler-execution-platform.md](infra/003-crawler-execution-platform.md) |
| `INFRA-ADR-004` | `infra` | Terraform State Project と Ops Project を分離する | Accepted | [docs/adr/infra/004-separate-tf-and-ops-projects.md](infra/004-separate-tf-and-ops-projects.md) |
| `INFRA-ADR-005` | `infra` | Terraform environments は GCP project ごとに分割する | Accepted | [docs/adr/infra/005-terraform-environment-slicing.md](infra/005-terraform-environment-slicing.md) |
| `INFRA-ADR-006` | `infra` | Cross-project Terraform output 共有戦略 | Accepted | [docs/adr/infra/006-cross-project-output-sharing.md](infra/006-cross-project-output-sharing.md) |
| `INFRA-ADR-007` | `infra` | Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計 | Accepted (一部 superseded) | [docs/adr/infra/007-artifact-registry-and-sa-strategy.md](infra/007-artifact-registry-and-sa-strategy.md) |
| `INFRA-ADR-008` | `infra` | Service Account 命名規則 | Accepted | [docs/adr/infra/008-service-account-naming.md](infra/008-service-account-naming.md) |
| `INFRA-ADR-009` | `infra` | Cross-project IAM binding の ownership | Accepted | [docs/adr/infra/009-cross-project-iam-ownership.md](infra/009-cross-project-iam-ownership.md) |
| `INFRA-ADR-010` | `infra` | Cloud Run Job の管理責務を Terraform に集約する | Accepted | [docs/adr/infra/010-cloud-run-job-management.md](infra/010-cloud-run-job-management.md) |
| `INFRA-ADR-011` | `infra` | Terraform monorepo における CI 対象検出と検証方針 | Accepted | [docs/adr/infra/011-terraform-ci-for-monorepo.md](infra/011-terraform-ci-for-monorepo.md) |
| `INFRA-ADR-012` | `infra` | Cloud Run Job の実行粒度と実行時パラメータ設計 | Accepted | [docs/adr/infra/012-crawler-execution-parameters.md](infra/012-crawler-execution-parameters.md) |
| `INFRA-ADR-013` | `infra` | Cursor Cloud から GCP への認証に Cursor OIDC と WIF を採用する | Superseded (一部有効) | [docs/adr/infra/013-cursor-oidc-workload-identity-federation.md](infra/013-cursor-oidc-workload-identity-federation.md) |
| `INFRA-ADR-014` | `infra` | Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする | Superseded (一部有効) | [docs/adr/infra/014-cursor-oidc-wif-direct-resource-access.md](infra/014-cursor-oidc-wif-direct-resource-access.md) |
| `INFRA-ADR-015` | `infra` | data は箱とし、guest IAM は依存の下流が書く | Accepted | [docs/adr/infra/015-guest-iam-downstream.md](infra/015-guest-iam-downstream.md) |
| `INFRA-ADR-016` | `infra` | GitHub Actions から crawler image を Artifact Registry へ push する | Accepted (一部 superseded) | [docs/adr/infra/016-github-actions-wif-and-crawler-image-push.md](infra/016-github-actions-wif-and-crawler-image-push.md) |
| `INFRA-ADR-017` | `infra` | GitHub Actions の Terraform 由来設定は ops が repository variable として書く | Accepted (一部 superseded) | [docs/adr/infra/017-github-actions-terraform-managed-variables.md](infra/017-github-actions-terraform-managed-variables.md) |
| `INFRA-ADR-018` | `infra` | Artifact Registry の vulnerability scanning と image retention | Accepted | [docs/adr/infra/018-artifact-registry-cost-controls.md](infra/018-artifact-registry-cost-controls.md) |
| `INFRA-ADR-019` | `infra` | GitHub Actions から terraform plan / apply する | Accepted | [docs/adr/infra/019-github-actions-terraform-plan-apply.md](infra/019-github-actions-terraform-plan-apply.md) |
| `INFRA-ADR-020` | `infra` | Terraform CI/CD と Secret Management 方針 | Accepted | [docs/adr/infra/020-terraform-cicd-secret-management.md](infra/020-terraform-cicd-secret-management.md) |
| `INFRA-ADR-021` | `infra` | crawler image digest の置換 PR を crawler-deploy が作成する | Accepted | [docs/adr/infra/021-crawler-image-digest-pr.md](infra/021-crawler-image-digest-pr.md) |
| `CRAWLER-ADR-001` | `crawler` | 論文収集クローラーの実装言語としてPythonを採用 | Accepted | [docs/adr/crawler/001-language-selection.md](crawler/001-language-selection.md) |
| `CRAWLER-ADR-002` | `crawler` | XMLパースにdefusedxmlを採用 | Accepted | [docs/adr/crawler/002-xml-parsing-security.md](crawler/002-xml-parsing-security.md) |

ステータスの読み方:

- `Accepted (一部 superseded)` — 後続 ADR が一部を置き換えている。残りは有効
- `Superseded (一部有効)` — 全体としては置き換え済みだが、一部の判断は現行方針として生きている

どこが生きているかは、各 ADR の `## Status` 本文に書いてあります。  
現行方針だけを知りたい場合は [`docs/architecture/`](../architecture/) を読んでください。

新しい ADR を追加したら、この一覧と、対応する [`docs/architecture/`](../architecture/) のファイルも更新してください。

## 目的

ADR は「なぜその設計判断をしたのか」を残すためのドキュメントです。  
単なる実装メモではなく、以下を将来の自分や他の開発者
が追跡できるようにすることを目的とします。

- 何を決めたか
- なぜその案を選んだか
- 何を比較したか
- どのようなトレードオフを受け入れたか
- どの条件で再検討するか

## 基本方針

- ADR の正本は `docs/adr/` 配下に置く
- テンプレートの正本は `docs/adr/_template.md` とする
- 各サブシステム配下に ADR を分散配置しない
- 必要であれば、各サブシステムの README から関連 ADR を参照する
- ADR はコード配置ではなく、**意思決定の責務単位**で分類する

## ディレクトリ構成

ADR はドメインごとのサブディレクトリに配置します。

```text
docs/adr/
├── README.md
├── _template.md
├── infra/
│   ├── 001-...
│   └── 002-...
└── crawler/
    ├── 001-...
    └── 002-...
```

必要に応じて、将来的に以下のようなドメインを追加できます。

- `backend/`
- `frontend/`
- `data/`
- `platform/`
- `security/`
- `search/`

ただし、最初から細かく分けすぎず、実際に ADR が増えてから追加することを推奨します。

## namespace ルール

ADR はドメインごとに namespace を持ちます。  
参照時は単なる `ADR-001` ではなく、**namespace 付きの識別子**を使います。

### 例

- `INFRA-ADR-001`
- `INFRA-ADR-002`
- `CRAWLER-ADR-001`
- `CRAWLER-ADR-002`

これにより、ドメイン別連番を採用しても識別子の衝突を防げます。

## 採番ルール

採番は **ドメインごとの連番** とします。

### 例

- `docs/adr/infra/001-gcp-project-structure.md`
- `docs/adr/infra/002-terraform-module-structure.md`
- `docs/adr/crawler/001-language-selection.md`
- `docs/adr/crawler/002-xml-parsing-security.md`

ルールは以下です。

- 3 桁ゼロ埋めの連番を使う
- 連番はドメインごとに独立させる
- 欠番は埋めない
- 既存 ADR の番号は原則として変更しない
- ファイル名は `NNN-topic.md` とする

## タイトルルール

ADR のタイトルには namespace を含めます。

### 例

- `# INFRA-ADR-001 GCPプロジェクト構成と環境分離戦略`
- `# INFRA-ADR-003 Crawler実行基盤として Cloud Run Jobs を採用`
- `# CRAWLER-ADR-001 論文収集クローラーの実装言語としてPythonを採用`

これにより、ファイルパスを見なくても ADR の所属が分かります。

## どのドメインに置くかの判断基準

分類は、コードの物理配置ではなく、**主に何を決めているか**で判断します。

### `infra/` に置くもの

- GCP プロジェクト構成
- Terraform 構成
- Cloud Run / Cloud Batch / Cloud Scheduler などの実行基盤
- IAM、ネットワーク、Artifact Registry などの基盤設計
- 監視、デプロイ、CI/CD の基盤方針

### `crawler/` に置くもの

- クローラーの実装言語
- XML / RSS / HTML パース戦略
- クロール状態管理の方式
- shard 戦略、checkpoint 戦略
- レート制御、重複排除、再開性などのアプリケーション設計

## 境界が曖昧な場合のルール

複数ドメインにまたがる ADR もあります。  
その場合は、**主たる意思決定の責務**で配置先を決めます。

### 例

- `Cloud Run Jobs vs Cloud Batch`
  - 主に実行基盤の選定なので `infra/`
- `Python vs Go`
  - 主に crawler 実装の選定なので `crawler/`

迷った場合は、以下の順で判断します。

1. 何を最終的に決めているか
2. どのチーム・責務が主に影響を受けるか
3. 将来その ADR を最も参照するのは誰か

## テンプレート運用

ADR を新規作成する場合は、必ず `docs/adr/_template.md` をベースにします。

テンプレートでは以下を必須とします。

- `Conclusion (結論)` を冒頭に書く
- `Context` に要件・制約・比較表を含める
- `Considered Options` で採用案と却下案を残す
- `Decision` に採用方針・初期構成・再検討条件を書く
- `Consequences` にメリット・デメリット・将来課題を書く
- `Next Steps` を明記する

## 比較表のルール

ADR では、比較した選択肢を**表でも整理する**ことを推奨します。  
文章だけでなく、比較表を入れることで判断軸を俯瞰しやすくなります。

推奨フォーマット:

```text
| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A | ... | ... | ... | 採用 |
| Option B | ... | ... | ... | 非採用 |
| Option C | ... | ... | ... | 非採用 |
```

## ステータスの扱い

ADR のステータスには以下を使います。

- `Proposed`
- `Accepted`
- `Deprecated`
- `Superseded`

必要に応じて日付を付けます。

### 例

- `Accepted (承認済み) - 2026-02-17`

### 部分 supersede を明記する

既存 ADR の一部だけを置き換えることは頻繁に起こります。  
そのとき、ステータスのラベルだけでは「どこまでが無効か」が伝わりません。

置き換える側の `## Status` には、**何を捨て、何を維持するか**を必ず書きます。

```text
Accepted (承認済み) - 2026-08-27

INFRA-ADR-014 を supersede する。014 が差し替えたのは impersonation から direct access への権限の付け方である。本 ADR が差し替えるのは guest IAM の置き場である。014 の認証モデルは維持する。
```

置き換えられる側の `## Status` にも、同じ内容を 1〜2 行で書きます。  
本文は書き換えず、当時の判断の記録として残します。

`Superseded` のスタンプだけで済ませないでください。  
全体が無効だと誤読され、実際には生きている判断まで捨てられます。

## 参照ルール

他のドキュメントや Issue、PR、README から ADR を参照する場合は、可能な限り namespace 付きで記載します。

### 例

- `INFRA-ADR-001 を参照`
- `CRAWLER-ADR-002 に従う`
- `この設計判断は INFRA-ADR-003 で記録している`

## 運用上の注意

- ADR は「実装後の感想」ではなく、**意思決定時点の判断記録**として書く
- 採用理由だけでなく、却下理由も残す
- 将来の再検討条件を明示する
- 実装詳細に寄りすぎず、設計判断のレベルを保つ
- 変更があった場合は既存 ADR を上書きするのではなく、新しい ADR で supersede することを基本とする
- ADR を追加・変更したら、**同じ PR で対応する [`docs/architecture/`](../architecture/) のファイルも更新する**
- ADR は `docs/adr/` 配下にのみ置く。サブシステム配下に複製を残さない

## 棚卸し

ADR が増えて相互参照が追えなくなったとき、`docs/architecture/` の鮮度が疑わしいときは棚卸しを行います。  
手順の正本は [`.agents/skills/adr-workflow/SKILL.md`](../../.agents/skills/adr-workflow/SKILL.md) の「Architecture Doc の棚卸し」です。

要点は次の通りです。

1. `docs/adr/README.md` の一覧ではなく、各 ADR ファイルの `## Status` 本文を読む
2. 新しい ADR ごとに「何を捨て、何を維持したか」を書き出し、全体 supersede と部分 supersede を区別する
3. 現行方針が `Superseded` の ADR にしか書かれていないものを探す
4. ADR が決めたことが実装に入っているかを突き合わせる（未実装なら architecture 側にそう書く）
5. `docs/architecture/` を畳んで書き直す。追記で済ませず、古い記述は削除する

## まとめ

DevGist の ADR は、以下のルールで運用します。

- 決定記録の正本は `docs/adr/`、**現行方針の正本は `docs/architecture/`**
- テンプレート正本は `docs/adr/_template.md`
- ドメインごとにサブディレクトリを切る
- 採番はドメイン別連番
- 参照は `INFRA-ADR-001` のように namespace 付き
- 分類はコード配置ではなく、意思決定の責務単位で行う
- 部分 supersede は `## Status` に「捨てるもの / 維持するもの」を明記する
