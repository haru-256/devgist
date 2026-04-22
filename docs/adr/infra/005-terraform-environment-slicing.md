# INFRA-ADR-005 Terraform environments は GCP project ごとに分割する

## Conclusion (結論)

- Terraform の `environments/` 配下の root module は、基本的に `GCP project` ごとに分割する。
- `service` ごとに跨る workload は 1 つの root module に閉じ込めず、各 project 側の責務に分解して管理する。
- service 全体の見通しや apply 順序は、README や Makefile などの運用導線で補う。

## Status (ステータス)

Accepted

## Context (背景・課題)

### 背景

DevGist では `crawler` のように、1 つの service が複数の GCP project に跨る構成を採る。

- image store は `Ops Project`
- 実行基盤は `App Project`
- datalake は `Data Project`

この状態で Terraform の `environments/` を `service` ごとに切るか、`project` ごとに切るかを決める必要がある。

### 要件と制約

1. **state 境界の明確化**
   - どこまでが 1 つの Terraform state なのかを明確にしたい
   - blast radius を project 境界に揃えたい

2. **責務の一貫性**
   - API 有効化、IAM、backend 設定、リソース所有者を project ごとに閉じたい
   - 共通基盤を service ごとの root module が横取りしないようにしたい

3. **service の見通し**
   - project ごとに分けると、1 つの service の全体像が追いづらくなる
   - 依存関係や apply 順序が人間に分かる必要がある

4. **運用性**
   - apply 対象と順序が曖昧にならないこと
   - 将来、service や project が増えても拡張しやすいこと

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: project ごとに分割 | project が state 境界と一致する場合 | state と責務が一致する。blast radius が明確。IAM/API/backend を project 単位で閉じられる。 | service 全体の見通しは別途補助が必要。 | 採用 |
| Option B: service ごとに分割 | 1 service がほぼ 1 project に閉じる場合 | service の全体像が 1 箇所で見やすい。 | 複数 project に跨る service で責務が混ざる。共通基盤を service が抱え込みやすい。 | 非採用 |
| Option C: project と service の二重 root module | 両方の見通しを root module で直接持ちたい場合 | 見た目上は分かりやすい。 | state の責務が重複しやすい。所有境界が曖昧。運用負荷が高い。 | 非採用 |

### 選定観点

- Terraform state の責務境界が自然か
- 複数 project に跨る service を無理なく表現できるか
- apply 対象と blast radius が読みやすいか
- service の見通しを別レイヤで補えるか

## Considered Options

### Option A: `environments/` を project ごとに切る [採用]

`devgist-tf`, `devgist-ops`, `devgist-data/dev`, `devgist-app/dev` のように、GCP project ごとに root module を配置する。

採用理由:

- **state 境界が明確**
  - Terraform state を project の責務に一致させやすい。
  - どの apply がどの project に影響するかが読みやすい。

- **複数 project に跨る service と相性がよい**
  - crawler のような workload を、`ops/app/data` の各責務に分解して自然に配置できる。
  - `Artifact Registry`、`Cloud Run Jobs`、`GCS` を別 state で管理できる。

- **基盤責務を service 側に漏らさない**
  - API enablement、backend、IAM、共通基盤の ownership を project 側に保てる。
  - service ごとの root module が共通基盤を抱え込む設計を避けられる。

### Option B: `environments/` を service ごとに切る [却下]

`crawler`, `api`, `frontend` のように workload 名で root module を切る。

却下理由:

- 1 service が複数 project に跨ると、1 root module に複数責務が混ざる。
- `ops` の Artifact Registry や `data` の GCS まで service 側 state に入れたくなり、境界が崩れる。
- 一部だけ更新したいときでも service 全体の state を触ることになりやすい。

### Option C: project と service の両方で root module を持つ [却下]

project ごとの root module と service ごとの root module を並立させる。

却下理由:

- 同じ責務を複数の root module が参照・管理し始める危険がある。
- source of truth が曖昧になり、どこから apply すべきか分かりにくい。
- 初期フェーズとしては運用コストが高すぎる。

## Decision (決定事項)

Terraform の `environments/` 配下は、`GCP project` ごとに root module を切る。

### 採用方針

- root module は project 単位で持つ
  - 例: `devgist-tf`, `devgist-ops`, `devgist-data/dev`, `devgist-app/dev`

- service は root module の単位にはしない
  - 1 つの service が複数 project に跨る場合は、各 project 側に責務を分解して配置する

- service の全体像は別レイヤで補う
  - `infra/README.md` に service-to-project 対応表を置く
  - `workflows/crawler/README.md` のような service README に依存先を書く
  - Makefile や運用コマンドで apply 順序を定義する

### 初期構成

- `devgist-tf`
  - Terraform state bucket 管理

- `devgist-ops`
  - Artifact Registry など共通運用基盤

- `devgist-data/dev`
  - datalake など stateful data

- `devgist-app/dev`
  - Cloud Run Jobs / API など stateless compute

- `crawler`
  - 単独 environment ではなく、`ops`, `app`, `data` に分散配置される workload として扱う

### Clarifications

- `project ごとに切る` のは state 境界のためであり、service の見通しまで project 単位に限定する意図ではない
- service 全体の設計説明と apply 導線は、README や task runner で補助する

### 再検討条件

- 将来、1 service がほぼ単一 project に閉じ、独立 state のメリットが大きくなった場合
- project 境界よりも service 境界で apply した方が明らかに運用コストが低いと判明した場合
- Terraform 以外の deployment tooling で service 単位 orchestration を十分に吸収できる場合

## Consequences (結果・影響)

### Positive (メリット)

- Terraform state と GCP project の責務が揃う
- apply 対象と blast radius が読みやすい
- 共有基盤を service ごとの state に混ぜずに済む
- project を増やしても root module のルールが崩れにくい

### Negative (デメリット)

- service 単位の全体像は root module だけでは見えにくい
- 1 つの service を有効化するために複数 project を順に apply する必要がある
- README や Makefile など、補助的な運用ドキュメントが必要になる

### Risks / Future Review (将来の課題)

- README や運用導線を整備しないと「どこに設定があるか分からない」問題が残る
- apply 順序が暗黙のままだと、project ごとの分割が逆に分かりにくさを生む
- service README と infra README の内容が乖離しないように維持が必要

## Next Steps

1. `infra/terraform/environments/` の root module を project 単位へ揃える
2. 旧 `crawler` environment の役割を `ops/app/data` 側へ段階的に移す
3. `infra/README.md` に service-to-project 対応表と apply 順序を追加する
4. `workflows/crawler/README.md` に crawler が依存する project と基盤を明記する
5. 必要なら Makefile で service 単位の apply 導線を提供する

## Related Documents

- [INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略
- [INFRA-ADR-002] Terraform構成: ドメイン駆動モジュールとマルチプロジェクト戦略の採用
- [INFRA-ADR-004] Terraform State Project と Ops Project を分離する
- [ADR運用ガイド](../../../docs/adr/README.md)
- [Infrastructure README](../../../infra/README.md)
