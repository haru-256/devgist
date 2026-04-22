# INFRA-ADR-004 Terraform State Project と Ops Project を分離する

## Conclusion (結論)

- DevGist の GCP project 構成として、`Terraform State` を保持する project と、`Artifact Registry` や CI/CD 基盤を保持する `Ops Project` を分離する。
- `haru256-devgist-tf` は Terraform state 専用 project とし、`haru256-devgist-ops` を別途運用基盤 project として設ける。
- `Artifact Registry`、GitHub Actions 連携、将来の WIF / 共通 CI 用 Service Account は `Ops Project` に配置する。

## Status (ステータス)

Accepted

## Context (背景・課題)

### 背景

既存の ADR では、Terraform state を保持する管理用 project と、Artifact Registry や CI/CD 基盤の置き場が明確に分離されていなかった。

- `INFRA-ADR-001` では `Mgmt Project` として `haru256-devgist-tf` を定義している
- `INFRA-ADR-002` では `Ops Project` に `Terraform State 保存用バケット` と `Artifact Registry` を同居させている

一方で、Terraform state を保持する project は「最後まで削除してはいけない基盤」であり、コンテナ配布や CI/CD の変更対象となる運用 project と同居させると、役割が混ざる。

### 要件と制約

1. **Terraform state の保護**
   - tfstate bucket を保持する project は最小限の責務に限定したい
   - 他の運用基盤変更に巻き込まれて削除・再構成対象になることを避けたい

2. **配布基盤の独立性**
   - `Artifact Registry` は app/data どちらにも属さない共通基盤として扱いたい
   - crawler, API, frontend など複数 workload から共有可能にしたい

3. **運用変更の分離**
   - CI/CD, WIF, 共通 Service Account, イメージ配布まわりは独立に変更できるようにしたい
   - tfstate project には不要な変更を入れたくない

4. **既存方針との整合**
   - `App Project` は stateless compute、`Data Project` は stateful data という既存整理は維持したい
   - crawler は `App Project` 上の `Cloud Run Jobs` とする前提を保ちたい

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `tf` と `ops` を分離 | 管理基盤を長期保護しつつ、運用基盤を拡張したい場合 | tfstate の保護がしやすい。Artifact Registry と CI/CD を独立運用しやすい。責務が明確。 | project 数が増える。Terraform root module も増える。 | 採用 |
| Option B: `tf` と `ops` を統合 | 小規模で project 数を最小化したい場合 | シンプルで初期構築が速い。 | tfstate と配布基盤が同居し、削除や変更の blast radius が広がる。 | 非採用 |
| Option C: `Artifact Registry` を App Project に置く | app 単位で閉じた配布運用をしたい場合 | app と image store の関係が単純。 | 共有基盤として扱いづらい。将来の workload 追加時に責務が崩れる。 | 非採用 |

### 選定観点

- tfstate project を最も保守的に扱えるか
- Artifact Registry を共通運用基盤として自然に配置できるか
- 将来の CI/CD 拡張に耐えられるか
- 既存の App / Data 分離と矛盾しないか

## Considered Options

### Option A: `tf` と `ops` を分離する [採用]

`haru256-devgist-tf` を Terraform state 専用 project とし、`haru256-devgist-ops` を運用基盤 project として別途設ける。

採用理由:

- **tfstate project の責務を極小化できる**
  - 最も重要な state 管理基盤を、Artifact Registry や CI/CD の日常的な変更から切り離せる。
  - 「tfstate がある project は消してはいけない」という運用ルールを徹底しやすい。

- **Ops 基盤の拡張余地が自然**
  - Artifact Registry, WIF, GitHub Actions 連携、共通 Service Account などを 1 つの運用 project に集約できる。
  - 将来 app や worker が増えても、共通配布基盤として再利用しやすい。

- **既存 ADR と大きく衝突しない**
  - `App Project` を stateless compute、`Data Project` を stateful data とする整理は維持できる。
  - 変更対象は `Mgmt/Ops` の切り分けだけに閉じる。

### Option B: `tf` と `ops` を統合する [却下]

`haru256-devgist-tf` に tfstate bucket と Artifact Registry を同居させる。

却下理由:

- tfstate を保持する project に、日常的に変更される配布基盤を同居させることになる。
- 「tfstate project は極力不変に保つ」という運用ポリシーを取りにくい。
- project 名としても `tf` が過度に狭い意味になり、役割の誤解を招きやすい。

### Option C: `Artifact Registry` を App Project に置く [却下]

各 app project 側に image store を置き、Cloud Run から同一 project 内で参照する。

却下理由:

- Artifact Registry が app 専用基盤になり、複数 workload 間の共通配布基盤として扱いづらい。
- crawler, API, frontend などが増えたときに、どの app project が image store の責任を持つか曖昧になる。
- app project の責務が「compute」から「配布基盤」まで広がりすぎる。

## Decision (決定事項)

DevGist の GCP project 構成として、`Terraform State Project` と `Ops Project` を分離する。

### 採用方針

- `haru256-devgist-tf`
  - Terraform state bucket 専用 project とする
  - 原則として、tfstate 管理以外の常設リソースは置かない

- `haru256-devgist-ops`
  - Artifact Registry を配置する
  - GitHub Actions 連携、WIF、共通 CI/CD 用 Service Account などの運用基盤を配置する

- `haru256-devgist-data-{env}`
  - GCS datalake, Cloud SQL, BigQuery などの stateful data を配置する

- `haru256-devgist-app-{env}`
  - Cloud Run Jobs, API, frontend などの stateless compute を配置する

### 初期構成

- `tf` project は remote state 管理専用
- `ops` project に crawler 用を含む Artifact Registry repository を配置
- crawler は `app-dev` などの App Project 上の `Cloud Run Jobs` として実行
- crawler の保存先 datalake は `data-dev` などの Data Project に配置

### Supersedes / Clarifications

- `INFRA-ADR-001` の `Mgmt Project` は、以後 `Terraform State Project` として解釈する
- `INFRA-ADR-002` の `Ops Project` に `Terraform State 保存用バケット` を同居させる記述は、本 ADR で supersede する

### 再検討条件

- 組織的に project 数をさらに削減する必要が出た場合
- Artifact Registry や CI/CD を別組織・別 billing 単位で管理する必要が出た場合
- Terraform state の管理方式自体を GCS bucket 以外へ移行する場合

## Consequences (結果・影響)

### Positive (メリット)

- tfstate project を保守的に運用しやすい
- Ops 基盤の変更が tfstate 管理へ波及しにくい
- Artifact Registry の責務が明確になり、複数 workload で共有しやすい
- App / Data / Ops / Tf の境界が明文化される

### Negative (デメリット)

- project 数が増え、初期セットアップがやや重くなる
- Terraform root module、IAM、CI/CD 設定の記述量が増える
- cross-project 参照の設計を意識する必要がある

### Risks / Future Review (将来の課題)

- `ops` project への共通基盤集約が進みすぎると、今度は `ops` の責務が肥大化する可能性がある
- IAM 設計を雑にすると、分離した project 境界が形骸化する
- CI/CD 導入時に、`ops` project と `app/data` project の権限境界を明示的に設計する必要がある

## Next Steps

1. `infra/README.md` に current project responsibilities を明記する
2. Terraform root module を `tf`, `ops`, `data`, `app` の責務に沿って整理する
3. Artifact Registry は `ops` project から apply する構成へ移す
4. crawler の deploy/runtime 設計で、`ops` の image store を `app` project から参照する
5. GitHub Actions / WIF / Service Account の責務分担を別ドキュメントまたは次の ADR で明確化する

## Related Documents

- [INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略
- [INFRA-ADR-002] Terraform構成: ドメイン駆動モジュールとマルチプロジェクト戦略の採用
- [INFRA-ADR-003] Crawler実行基盤として Cloud Run Jobs を採用する
- [ADR運用ガイド](../../../docs/adr/README.md)
- [Infrastructure README](../../../infra/README.md)
