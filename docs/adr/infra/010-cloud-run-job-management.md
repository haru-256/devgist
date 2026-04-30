# INFRA-ADR-010 Cloud Run Job の管理責務を Terraform に集約する

## Conclusion (結論)

Cloud Run Job は Terraform で完全管理する。

CI/CD は crawler のコンテナイメージを build し、Artifact Registry に push したうえで、image digest を Terraform に渡して apply する責務を持つ。

Cloud Run Job の memory、CPU、timeout、retry、env、secret、service account、scheduler などの実行定義は Terraform 以外から変更しない。

## Status (ステータス)

Accepted (承認済み) - 2026-04-29

## Context (背景・課題)

### 背景

DevGist では、arXiv、ACL、Zenn、Qiita、企業テックブログなどの外部情報源からデータを収集し、Raw Data Lake に保存したうえで、後続の構造化・品質評価・RAG 用データ生成につなげる。

このデータインジェクション処理の入口として crawler を実行する必要がある。crawler は HTTP request/response 型の常駐 API ではなく、定期実行・手動再実行・失敗時のリトライ・将来的な shard 分割を伴う batch workload である。

そのため、crawler の実行基盤として Cloud Run Job を採用する前提で、Cloud Run Job を Terraform で管理するか、CI/CD から `gcloud run jobs deploy/update` によって管理するかを検討する。

今回の論点は Cloud Run Job 自体の採用可否ではなく、Cloud Run Job の管理責務をどこに置くかである。

### 要件と制約

1. **再現性**

   Cloud Run Job の実行定義を Git 上で管理し、別環境や再作成時にも同じ構成を再現できる必要がある。

2. **二重管理の回避**

   Terraform と CI/CD の両方が同じ Cloud Run Job 属性を変更すると、設定の所有者が曖昧になる。

   特に memory、CPU、timeout、retry、env、secret、service account などを CI/CD からも更新できる状態にすると、Terraform state と実リソースの drift が発生しやすい。

3. **アプリケーション更新の容易さ**

   crawler のコードは初期フェーズで頻繁に変更される。CI/CD によってテスト、image build、Artifact Registry への push を自動化し、手作業 deploy を避ける必要がある。

4. **tfstate drift の抑制**

   CI/CD から `gcloud run jobs deploy/update` で image を直接更新すると、Terraform が保持する state/config と実リソースの image がずれる可能性がある。

   drift を許容する場合は `ignore_changes` などで明示的に設計する必要があるが、初期フェーズでは運用を単純化するため、Cloud Run Job の desired state を Terraform に集約する。

5. **将来の拡張性**

   crawler は将来的に Science Collector、Engineering Collector、Career Collector など複数 Job に分かれる可能性がある。

   Job 数が増えても責務境界が明確で、IAM、Secret、Scheduler、実行パラメータを一貫して管理できる構成が望ましい。

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: Cloud Run Job を Terraform で完全管理し、CI/CD は image build/push と Terraform apply を行う | 再現性と責務境界を重視する batch workload | Cloud Run Job の desired state が Terraform に集約される。tfstate drift と二重管理を避けやすい | image 更新時にも Terraform apply が必要 | 採用 |
| Option B: Terraform で Job を作成し、CI/CD で `gcloud run jobs update --image` のみ実行する | deploy 速度を優先し、image drift を許容できる場合 | image 更新が軽い。アプリ更新のたびに Terraform apply しなくてよい | image が Terraform 管理外になり、state と実リソースが drift する。`ignore_changes` が必要 | 却下 |
| Option C: CI/CD の `gcloud run jobs deploy/update` で Job 全体を管理する | PoC や手早い検証 | tfstate 管理が不要。初期構築は簡単 | IAM、Secret、Scheduler、実行定義の再現性が弱い。設定変更履歴が分散しやすい | 却下 |
| Option D: Cloud Run functions として deploy する | 小さな HTTP/event-driven function | 実装開始が簡単 | crawler の batch workload と責務が合いにくい。Job execution 単位の再実行・管理に向かない | 却下 |

### 選定観点

今回の意思決定では、以下を重視する。

- Cloud Run Job の実行定義を Git/Terraform 上で再現可能にする
- Terraform と CI/CD の二重管理を避ける
- memory、CPU、timeout、retry、env、secret、service account、scheduler の所有者を Terraform に固定する
- CI/CD はアプリケーション成果物である container image の生成と登録に集中させる
- image 更新も Terraform 経由にして、Cloud Run Job の実リソースと Terraform state/config の drift を避ける
- 将来的に crawler job が増えても同じ運用モデルを適用できるようにする

## Considered Options

### Option A: Cloud Run Job を Terraform で完全管理する [採用]

Cloud Run Job の定義を Terraform に集約する。

CI/CD は crawler のコンテナイメージを build し、Artifact Registry に push する。その後、push された image の immutable な digest を Terraform 変数として渡し、Terraform apply によって Cloud Run Job の image 参照を更新する。

CI/CD から `gcloud run jobs deploy` や `gcloud run jobs update` を使って Cloud Run Job を直接更新しない。

採用理由:

- Cloud Run Job の desired state が Terraform に集約される
- memory、CPU、timeout、retry、env、secret、service account などの所有者が Terraform に固定される
- image も Terraform state/config と整合するため、drift が発生しにくい
- CI/CD に Cloud Run Job の実行設定を持たせないため、二重管理を避けられる
- 複数 crawler job に拡張しても同じ構成を横展開しやすい
- Artifact Registry、Cloud Run Job、Cloud Scheduler、IAM、Secret Manager の関係を Terraform 上で一貫して表現できる

受け入れるトレードオフ:

- crawler の image 更新時にも Terraform apply が必要になる
- CI/CD には Terraform 実行権限と state access が必要になる
- apply 失敗時には image は Artifact Registry に存在するが、Cloud Run Job には反映されない状態が起こり得る

このトレードオフは、初期フェーズでは許容する。Cloud Run Job はデータインジェクション基盤の入口であり、短期的な deploy 速度よりも再現性と責務境界を優先する。

### Option B: Terraform で Job を作成し、CI/CD で image だけ更新する [却下]

Terraform は Cloud Run Job の土台を作成し、CI/CD は `gcloud run jobs update --image` によって image だけを更新する方式。

この方式では、Terraform が memory、CPU、timeout、retry、env、secret、service account などを管理し、CI/CD が image のみを管理する。

却下理由:

- image が Terraform 管理外になり、Terraform state/config と実リソースが drift する
- drift を避けるには `ignore_changes` が必要になる
- Terraform コードを見ても現在実行されている image digest が分からなくなる
- CI/CD のコマンドに image 以外の flag が追加されると、二重管理が発生する
- Cloud Run Job v2 resource の nested field に対する `ignore_changes` は provider schema への依存が強く、初期フェーズで余計な複雑性を持ち込みやすい

deploy 速度を優先する段階になれば再検討余地はあるが、現時点では採用しない。

### Option C: CI/CD の `gcloud run jobs deploy/update` で Job 全体を管理する [却下]

Terraform を使わず、CI/CD から `gcloud run jobs deploy` または `gcloud run jobs update` を実行し、Cloud Run Job を管理する方式。

却下理由:

- tfstate 管理は不要になるが、Cloud Run Job の実行定義が CI/CD script に埋まりやすい
- memory、CPU、timeout、retry、env、secret、service account などの変更履歴が Terraform ではなく CI/CD に分散する
- IAM、Secret Manager、Scheduler、Artifact Registry などの周辺リソースとの関係が追いにくくなる
- 複数環境や複数 crawler job に拡張したときに管理が破綻しやすい
- 手動変更や console 変更との差分検知が弱い

PoC としては成立するが、DevGist の継続開発における標準構成としては採用しない。

### Option D: Cloud Run functions として deploy する [却下]

crawler を Cloud Run functions として deploy する方式。

却下理由:

- crawler は HTTP/event-driven function より batch workload に近い
- 定期実行、手動再実行、失敗時リトライ、将来的な task/shard 分割を考えると Cloud Run Job の方が適している
- functions deploy は source deploy の性質が強く、container image を明示的な成果物として扱う設計と相性が弱い
- DevGist では crawler をデータインジェクション基盤の一部として扱うため、Job execution 単位で管理できる実行基盤を優先する

## Decision (決定事項)

Cloud Run Job は Terraform で完全管理し、CI/CD は crawler image の build、Artifact Registry への push、Terraform apply の実行を担当する。

CI/CD から Cloud Run Job に対して `gcloud run jobs deploy` または `gcloud run jobs update` を実行しない。

### 採用方針

- Cloud Run Job の定義は Terraform に集約する
- Cloud Run Job の image 参照も Terraform で管理する
- CI/CD は crawler の Docker image を build し、Artifact Registry に push する
- CI/CD は push された image digest を Terraform 変数として渡す
- Terraform apply によって Cloud Run Job の image を更新する
- Cloud Run Job が参照する image は digest 形式を必須とする
- image tag は `${GITHUB_SHA}` などの一意な tag を付与してよいが、可読性と追跡性のためだけに使う
- memory、CPU、timeout、retry、env、secret、service account、scheduler は Terraform のみが管理する
- 緊急対応を除き、Cloud Console や `gcloud run jobs update` による直接変更は行わない

### 初期構成

- Job Runtime
  - Cloud Run Job
- Image Registry
  - Artifact Registry
- IaC
  - Terraform
- CI/CD
  - GitHub Actions
  - lint / test
  - Docker build
  - Artifact Registry push
  - Terraform apply
- Scheduler
  - Cloud Scheduler
- Secret
  - Secret Manager
- IAM
  - crawler 実行用 Service Account
  - CI/CD 用 deploy Service Account
  - Artifact Registry push/pull 権限
  - Secret Manager access 権限
- Observability
  - Cloud Logging
  - Cloud Monitoring

### CI/CD の責務

CI/CD は以下を担当する。

1. crawler の lint/test を実行する
2. Docker image を build する
3. image を Artifact Registry に push する
4. push された image の digest を取得する
5. Terraform に `crawler_image` として image digest を渡す
6. Terraform apply を実行する

CI/CD は以下を担当しない。

- `gcloud run jobs deploy`
- `gcloud run jobs update`
- Cloud Run Job の memory 変更
- Cloud Run Job の CPU 変更
- Cloud Run Job の timeout 変更
- Cloud Run Job の retry 変更
- Cloud Run Job の env / secret 変更
- Cloud Run Job の service account 変更
- Cloud Scheduler の変更
- IAM の変更

### Terraform の責務

Terraform は以下を担当する。

- Cloud Run Job の作成・更新
- container image digest 参照
- memory
- CPU
- timeout
- retry
- task count
- parallelism
- env
- secret reference
- service account
- IAM
- Artifact Registry
- Cloud Scheduler
- Secret Manager の参照権限
- 必要な API enablement

### 再検討条件

以下の条件に該当した場合は、管理方式を再検討する。

- image 更新の頻度が高く、Terraform apply が開発速度の明確なボトルネックになった場合
- deploy pipeline と infrastructure pipeline を分離する必要が強くなった場合
- staging / production など複数環境への promotion flow が必要になった場合
- Cloud Deploy などを使った release 管理が必要になった場合
- 複数 crawler job の image 更新を独立して高速に回す必要が出た場合
- Terraform state lock 待ちが頻発する場合
- Cloud Run Job の実行定義と image release のライフサイクルを分離した方が運用上明確になった場合

この場合、Option B のように image のみ CI/CD 管理とし、Terraform 側で image drift を明示的に許容する方式を再検討する。

## Consequences (結果・影響)

### Positive (メリット)

- Cloud Run Job の desired state が Terraform に集約される
- tfstate と実リソースの drift を避けやすい
- CI/CD と Terraform の二重管理を避けられる
- memory、CPU、timeout、retry、env、secret、service account の変更箇所が Terraform に固定される
- Cloud Run Job の再作成や別環境への展開が容易になる
- Job 数が増えても Terraform module 化しやすい
- Git history 上で Cloud Run Job の実行定義変更を追跡できる
- Artifact Registry、Cloud Run Job、Scheduler、IAM、Secret の関係を一貫して管理できる

### Negative (デメリット)

- image 更新にも Terraform apply が必要になる
- CI/CD に Terraform 実行権限が必要になる
- Terraform state へのアクセス管理が必要になる
- image build/push は成功したが Terraform apply が失敗する、という中間状態が起こり得る
- deploy のたびに Terraform plan/apply の時間がかかる
- アプリケーション deploy とインフラ apply の境界がやや近くなる

### Risks / Future Review (将来の課題)

- Terraform apply の失敗時に、Artifact Registry に未使用 image が残る可能性がある
- 古い image の retention policy を検討する必要がある
- CI/CD 用 Service Account の権限が広くなりすぎないようにする必要がある
- Terraform state bucket の IAM を適切に分離する必要がある
- 複数 job / 複数 environment に増えたとき、Terraform module の抽象化粒度を見直す必要がある
- crawler の冪等性、checkpoint、重複排除、rate limit 対応はアプリケーション側で設計する必要がある
- Cloud Run Job の失敗通知、retry 上限、部分失敗時の再実行方法を別途設計する必要がある

## Next Steps

1. Terraform に Cloud Run Job 用 module または resource を追加する
2. Artifact Registry repository を Terraform で作成する
3. crawler 実行用 Service Account を Terraform で作成する
4. crawler 実行用 Service Account に必要な IAM を付与する
5. Secret Manager の secret 参照権限を Terraform で付与する
6. Cloud Scheduler から Cloud Run Job を起動する構成を Terraform で追加する
7. CI/CD に Docker build と Artifact Registry push を追加する
8. CI/CD で image digest を取得し、Terraform に `crawler_image` として渡す
9. Terraform apply によって Cloud Run Job の image を更新する
10. Cloud Run Job の手動実行手順を README に記載する
11. crawler の冪等性、checkpoint、重複排除、rate limit 対応をアプリケーション側で設計する
12. Cloud Logging / Cloud Monitoring の確認手順を README に記載する

## Related Documents

- [Design Doc: DevGist](../../../docs/design_doc.md)
- [INFRA-ADR-003 Crawler実行基盤として Cloud Run Jobs を採用する](./003-crawler-execution-platform.md)
- [Infrastructure README](../../../infra/README.md)
