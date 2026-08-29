# INFRA-ADR-016 GitHub Actions から crawler image を Artifact Registry へ push する

## Conclusion (結論)

- GitHub Actions が GCP を操作するときは、GitHub OIDC JWT を WIF で federated token に換え、その federated principal へリソース IAM を直接付ける。Service Account を impersonate しない。CI 用の新しい SA も作らない。
- GitHub Actions 用 WIF は Cursor 用 pool `cursor` と分ける。ops に pool `github-devgist` / provider `oidc` を置く。issuer は `https://token.actions.githubusercontent.com`。
- pool `github-devgist` は GitHub リポジトリ `haru-256/devgist` 専用である。別リポジトリは別 pool にする。ops は prod と dev の両方を担うので、prod と dev はこの pool を共有する。
- IAM の principalSet は pool 単位で、`attribute.NAME/VALUE` を 1 段しか取れない。crawler Artifact Registry の writer は `attribute.environment/dev` に付ける。provider の condition は `repository_id` と `repository_owner_id` にする。environment と workflow は condition に入れない。
- この identity の初期権限は crawler Artifact Registry への `roles/artifactregistry.writer` に限る。terraform apply の CI は本 ADR では作らない。[INFRA-ADR-010](./010-cloud-run-job-management.md) の apply は手元のまま。

## Status (ステータス)

Accepted (承認済み) - 2026-08-28

[INFRA-ADR-015](./015-guest-iam-downstream.md) の Next Steps 3 を、crawler image push の範囲で実装する。010 を supersede しない。

[INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md) の AR 1 本 / SHA pin / workload SA は維持する。007 の「push する SA は `github-actions`」と「初期は全リポジトリ writer」は本 ADR が置き換える。007 本文は履歴として残す。

## Context (背景・課題)

### 背景

crawler のコンテナイメージは Artifact Registry に置き、Cloud Run Job は Terraform の `crawler_image`（digest 必須）で参照する（[INFRA-ADR-003](./003-crawler-execution-platform.md)、[INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md)、[INFRA-ADR-010](./010-cloud-run-job-management.md)）。

build / push はまだ手元の `make build-push-image` である。GitHub Actions にあるのは Python lint/test と Terraform の静的検証だけである。apply も plan も無い（[INFRA-ADR-011](./011-terraform-ci-for-monorepo.md)）。

Cursor Cloud 用 WIF は pool `cursor` として ops にある。認証は federated principal への direct resource access である（[INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md)）。guest IAM の置き場は [INFRA-ADR-015](./015-guest-iam-downstream.md) の表である。013 / 014 / 015 は GitHub Actions 用 WIF を別 ADR に送った。Cursor 用 WIF への相乗りは禁止である。

ops には `github-actions` SA があり、project 全体の `roles/artifactregistry.writer` を持つ。WIF は付いていない。本 ADR の CI はこの SA を使わない。

010 は CI の責務を build、push、digest 渡し、apply まで含む。apply は tfstate と Cloud Run まで権限が広がる。今回は image push までで止め、apply の CI は別 ADR に残す。

[INFRA-ADR-004](./004-separate-tf-and-ops-projects.md) の ops は Artifact Registry と CI/CD の置き場である。app / data は環境ごとに分かれるが、ops は prod と dev の両方を担う。principalSet は provider 単位ではなく pool 単位である。

### 要件と制約

1. **長寿命の秘密を GitHub に置かない**
   - JSON キーを repo secret にしない
2. **Cursor 用 WIF と混ぜない**
   - issuer も信頼条件も違う
3. **crawler runtime と CI の blast radius を分ける**
   - crawler SA は借りない
4. **初期権限を crawler AR への push に限る**
   - tfstate、datalake、app-dev、Cloud Run には付けない
5. **guest IAM の置き場は 015 の表**
   - identity は ops。crawler AR は ops 同一 root。ops が書く
6. **010 を壊さない**
   - Job は Terraform 管理のまま。`gcloud run jobs deploy/update` は使わない
   - apply の CI は後続。本 ADR では作らない
7. **ops の WIF は prod と dev で共有する**
   - 環境ごとの pool にはしない
8. **GitHub リポジトリごとに WIF pool を分ける**
   - 別リポジトリの identity を同じ pool に乗せない
9. **IAM principalSet は GCP の文法に従う**
   - `attribute.NAME/VALUE` を 2 段つなぐ書き方は使えない

### 比較した選択肢

#### WIF の置き場

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: Cursor の pool `cursor` を共有する | issuer が同じ IdP のとき | pool が増えない | GitHub と Cursor で issuer も claim も違う。013 / 014 が混ぜないと書いた | 非採用 |
| Option B: ops に pool `github-devgist` を新設する | GitHub と Cursor を別 IdP として扱う場合 | 信頼条件が分かれる。blast radius を IAM で切れる | pool が 1 本増える | 採用 |

#### 認証モデル

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `github-actions` SA を impersonate する | 監査を SA email に揃えたい場合。federated identity 非対応 API がある場合 | 権限追加は SA に 1 回 | hop が増える。014 が Cursor で捨てた経路を CI に残す | 非採用 |
| Option B: federated principal へ direct resource access | Artifact Registry など対応済み API だけを触る場合 | hop が無い。CI 用 SA が増えない。監査が GitHub の claim のまま | リソースを足すたびに principalSet へ IAM を足す | 採用 |

#### pool の分割

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: GitHub 全体で 1 pool | 全リポジトリの CI を 1 箇所で見たい場合 | pool が増えない | principalSet が repo をまたぐ。condition と IAM の両方で repo を足し続ける | 非採用 |
| Option B: prod / dev で pool を分ける | GCP 環境ごとに identity を物理分割したい場合 | IAM が環境で混ざらない | ops が両環境を担う前提と食い違う。WIF が倍になる | 非採用 |
| Option C: GitHub リポジトリごとに pool を分け、prod / dev は共有する | repo の境界と環境の境界を別レイヤにしたい場合 | repo は pool、環境は IAM の `attribute.environment` で切れる | リポジトリが増えると pool が増える | 採用 |

#### IAM principal

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `attribute.repository_id/<id>` | 同じ pool に 1 リポジトリしか乗せず、環境も 1 つのとき | 単純 | 同じ pool に prod identity が乗ると、dev AR の writer が prod にも付く | 非採用 |
| Option B: `attribute.repository_id/<id>/attribute.environment/dev` と 2 段つなぐ | 2 条件を IAM だけで AND したい場合 | 意図は明快 | GCP の principalSet は attribute を 1 段しか取れない。値として解釈されて誰にも付かない | 非採用 |
| Option C: `attribute.repo_env/<id>:<env>` の合成 attribute | 同じ pool に複数 repo と複数環境が乗るとき | IAM 1 本で repo と環境を切れる | pool を repo ごとに分けるなら repository_id は principal に不要。合成が余る | 非採用 |
| Option D: `attribute.environment/dev` | pool が 1 リポジトリ専用で、環境だけ IAM で分けたいとき | principalSet の文法に合う。prod は別 binding を足せる | 同じ GitHub Environment `dev` を使う全 workflow が同じ IAM を共有する | 採用 |

#### provider の attribute condition

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `repository_id` + `environment` + `workflow_ref` | この provider を crawler image 専用にしたい場合 | token 交換の時点で workflow と env が閉じる | 別 workflow / 別 env を足すたびに condition を広げる。prod が同じ WIF を使えない | 非採用 |
| Option B: `repository_id` だけ | この pool をリポジトリの GitHub Actions 入口にしたい場合 | 別 workflow / 別 env が同じ provider を使える。権限は IAM で足す | owner が変わっても通る | 非採用 |
| Option C: `repository_id` + `repository_owner_id` | この pool をリポジトリの GitHub Actions 入口にしつつ、owner も id で固定したい場合 | 別 workflow / 別 env が同じ provider を使える。rename でも id は変わらない | transfer すると condition を直す必要がある。今回は transfer しない | 採用 |

#### 今回実装する範囲

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: build / push と apply の CI を同時に作る | 010 の最終形を一度に閉じたい場合 | Job まで自動化される | tfstate と Cloud Run まで権限が広がる。IAM と tfvars の設計が先に要る | 非採用 |
| Option B: build / push まで。apply は手元 | 権限を AR に閉じたまま CI を始めたい場合 | blast radius が小さい。010 の apply は後続に残せる | digest を手元 apply し忘れると Job が古いまま | 採用 |

### 選定観点

- Cursor と同じ direct resource access に揃えること
- issuer の違う IdP を 1 つの pool に入れないこと
- ops が prod / dev を共有する前提を崩さないこと
- GitHub リポジトリの境界と GCP 環境の境界を混同しないこと
- principalSet を GCP が解釈できる形にすること
- 初期 IAM を crawler AR writer に限ること
- 010 の apply を否定せず、実装だけ後回しにすること

## Considered Options

### Option A: Cursor の pool `cursor` を共有する [却下]

GitHub OIDC の provider を pool `cursor` に足す、または Cursor の provider 条件を広げる方式。

却下理由:

- Cursor の issuer は `https://api.cursor.com`。GitHub の issuer は `https://token.actions.githubusercontent.com`
- Cursor の claim は `repo_url` と `agent_runtime`。GitHub の claim は `repository_id` と `environment`
- 013 / 014 は GitHub Actions 用 WIF を混ぜないと書いた

### Option B: ops に GitHub リポジトリ専用の pool `github-devgist` を置く [採用]

GitHub 専用の pool と provider を ops に置く。Cursor の pool には触れない。prod と dev は同じ pool を使う。別 GitHub リポジトリは別 pool にする。

採用理由:

- 信頼条件が IdP ごとに分かれる
- ops は両環境の配布基盤なので、環境で pool を分けない
- principalSet は pool 単位なので、リポジトリの分離は pool でやる。環境の分離は IAM の `attribute.environment` でやる
- 既存の `workload_identity_oidc` module を再利用できる

prod / dev で pool を分ける案は、ops が両方を担う前提と食い違うので却下する。全 GitHub リポジトリで 1 pool にする案は、principalSet が repo をまたぐので却下する。

### Option C: `github-actions` SA を impersonate する [却下]

WIF のあとに `roles/iam.workloadIdentityUser` で既存 SA を借り、SA に AR writer を付ける方式。

却下理由:

- GCP は direct access を推奨し、impersonation は API 制限があるときの代替である
- Artifact Registry の IAM はその制限に当たらない
- 014 が Cursor で捨てた hop を CI に残す
- 監査ログの principal が SA email に畳まり、GitHub の claim が見えなくなる
- `google-github-actions/auth` は `service_account` を省略すれば federated token をそのまま使う

CI 用の新しい SA も作らない。既存の `github-actions` SA は本 ADR の pipeline では使わない。削除は対象外である。

### Option D: 今回 apply の CI まで作る [却下]

build / push のあと、digest を `crawler_image` に渡して app-dev を apply する方式。010 の最終形である。

却下理由:

- CI identity が tfstate、Cloud Run、crawler SA の actAs まで持つ
- gitignore の `terraform.tfvars` を CI へ渡す設計が先に要る
- image push だけ先に通す方が、失敗したときの権限範囲が小さい

010 は維持する。実装は別 ADR に送る。

### Option E: IAM を `attribute.environment` にする [採用]

crawler Artifact Registry の writer を

`principalSet://.../workloadIdentityPools/github-devgist/attribute.environment/dev`

に付ける。

採用理由:

- principalSet は pool 単位で、attribute は 1 段しか書けない
- pool が 1 リポジトリ専用なら、IAM で切る必要があるのは環境だけである
- prod を足すときは同じ pool に `attribute.environment/prod` の binding を足す。dev の binding には乗せない

却下した案:

- `attribute.repository_id/<id>`。同じ pool の prod identity にも writer が付く
- `.../attribute.repository_id/<id>/attribute.environment/dev`。GCP が 2 段目を値の一部と解釈する
- `attribute.repo_env/<id>:<env>`。pool を repo ごとに分けるなら repository_id を principal に載せる必要が無い

repository_id と repository_owner_id は IAM ではなく provider の attribute condition に置く。rename で変わらない id を使い、repository 名と owner login は使わない。transfer は想定しないが、owner_id も条件に残す。

## Decision (決定事項)

GitHub Actions から crawler image を Artifact Registry へ push するときは、GitHub OIDC と ops の WIF pool `github-devgist` による federated principal への direct resource access を使う。初期 IAM は crawler リポジトリの writer だけである。terraform apply の CI は作らない。

### 採用方針

- WIF pool / provider は `haru256-devgist-ops` に置く。pool ID は `github-devgist`。provider ID は `oidc`。リポジトリ名は `pool_id` に載せる。`provider_id` と display_name には載せない。owner login は `pool_id` に入れない。リポジトリと owner の固定は condition の `repository_id` と `repository_owner_id`
- この pool は GitHub リポジトリ `haru-256/devgist` 専用。別リポジトリは別 pool。prod と dev はこの pool を共有する
- issuer は `https://token.actions.githubusercontent.com`
- JWT の `aud` は WIF provider の既定 audience に固定する
- attribute mapping は `google.subject` = `assertion.sub`、`attribute.repository_id` = `assertion.repository_id`、`attribute.repository_owner_id` = `assertion.repository_owner_id`、`attribute.environment` = `assertion.environment`。`attribute.environment` は IAM 用。GitHub Environment の無い job は claim が無く、token 交換に失敗する
- attribute condition は `repository_id` と `repository_owner_id` にする。environment と workflow は入れない。prod / 別 workflow が同じ provider を使うため。権限の分割は IAM の `attribute.environment` で行う
- `assertion.ref` は condition に入れない。dev の image は branch を問わず、image に効く `workflows/crawler/**` の push で作る。README だけでは作らない。ops を apply する前は repository variable が空なので job は skip する
- IAM member は `principalSet://iam.googleapis.com/projects/<ops_number>/locations/global/workloadIdentityPools/github-devgist/attribute.environment/dev`
- `google-github-actions/auth` に `service_account` を渡さない。credential config に `service_account_impersonation_url` を入れない
- `google-github-actions/auth` に `project_id` として `haru256-devgist-ops` を渡す。WIF provider からは project number しか取れないため、gcloud の quota project に使う
- crawler Artifact Registry リポジトリへ `roles/artifactregistry.writer` を付ける。置き場は ops 同一 root（015）
- tfstate、datalake、app-dev、Cloud Run には付けない
- 既存の `github-actions` SA には `workload_identity_users` を足さない
- CI は image を build / push し、digest 参照を `image_ref:` として出す。Job の更新は手元で `crawler_image` に渡して apply する
- image tag は `GITHUB_SHA`。同じ tag があっても build し直す
- `gcloud run jobs deploy` と `gcloud run jobs update` は使わない

### 初期構成

```
haru256-devgist-ops
├── WIF
│   ├── pool: github-devgist   # haru-256/devgist 専用。prod / dev 共有
│   └── provider: oidc
│       ├── issuer: https://token.actions.githubusercontent.com
│       └── condition: repository_id + repository_owner_id
└── Artifact Registry repository crawler
    └── roles/artifactregistry.writer
        └── member: principalSet://.../workloadIdentityPools/github-devgist/attribute.environment/dev

GitHub Actions
└── crawler image（image に効く `workflows/crawler/**` の push と workflow_dispatch。README だけでは走らない。GitHub Environment `dev`。ops apply 前は skip）: build / push

手元
└── terraform apply（app-dev の crawler_image に digest を渡す）
```

GitHub の repository variable は ops Terraform が書く（[INFRA-ADR-017](./017-github-actions-terraform-managed-variables.md)）。workflow は `GCP_GITHUB_WIF_PROVIDER` を `workload_identity_provider` に渡す。

### 再検討条件

- 使いたい Google Cloud API が federated identity に対応していない場合。その API だけ SA impersonation に寄せる
- GitHub Actions から terraform apply するとき。guest IAM は 015 の表に従い、別 ADR で書く
- 同じ pool に別 GitHub リポジトリを乗せるとき。そのときは IAM principal に repository_id を戻すか、合成 attribute を検討する
- prod を足すとき。同じ pool `github-devgist` を使う。IAM は `attribute.environment/prod` を別 binding にする
- 同じ GitHub Environment を使う workflow 同士で IAM を分けたくなったとき。Environment 名を分けるか、そのときだけ workflow を condition に戻す

## Consequences (結果・影響)

### Positive (メリット)

- Cursor と同じ認証モデルになる。hop が無い
- JSON キーが GitHub に残らない
- Cursor 用 WIF と信頼条件が混ざらない
- リポジトリの境界と環境の境界が、pool と IAM で分かれる
- CI の初期権限が crawler AR に閉じる
- 010 の apply を否定せず、後から principalSet へ IAM を足せる

### Negative (デメリット)

- digest を手元 apply し忘れると、Job は古い image のままである。010 が受け入れた中間状態が、この ADR の通常運用になる
- WIF 自体の apply は手元に残る。CI が自分の identity を作れない
- 既存の `github-actions` SA が残る。本 pipeline は使わない
- 同じ GitHub Environment `dev` を使う全 workflow が、crawler AR writer を共有する。権限を分けたいときは Environment 名を分ける

### Risks / Future Review (将来の課題)

- public repo なので、この provider を呼ぶ workflow は default branch に入ったものが federate できる。`environment: dev` を付けた job は crawler AR writer を共有する。権限を分けたいときは GitHub Environment 名を分ける
- GitHub Environment `dev` は OIDC claim と IAM の `attribute.environment` の契約であり、image の行き先ではない。protection rule は付けない。prod 用 Environment はまだ作らない。本体は ops Terraform が書く（[INFRA-ADR-017](./017-github-actions-terraform-managed-variables.md)）
- Artifact Registry の retention は [INFRA-ADR-018](./018-artifact-registry-cost-controls.md) で決めた（直近 5 世代 KEEP / 30 日超 DELETE。scanning は `DISABLED`）
- apply の CI を足すときは、tfstate と Cloud Run の IAM がこの principalSet に乗る。そのときの blast radius を別 ADR で書く

## Next Steps

1. Terraform で ops の GitHub 用 WIF pool / provider と、crawler AR への writer を定義する
2. 手元で ops を apply する。GitHub Environment と repository variable も同じ apply で書く（[INFRA-ADR-017](./017-github-actions-terraform-managed-variables.md)）
3. crawler image の build / push workflow で token 交換と push を確認する
4. GitHub Actions から terraform apply するための IAM と workflow は、別 ADR で設計する

## Related Documents

- [[INFRA-ADR-004] Terraform State Project と Ops Project を分離する](./004-separate-tf-and-ops-projects.md)
- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [[INFRA-ADR-010] Cloud Run Job の管理責務を Terraform に集約する](./010-cloud-run-job-management.md)
- [[INFRA-ADR-011] Terraform monorepo における CI 対象検出と検証方針](./011-terraform-ci-for-monorepo.md)
- [[INFRA-ADR-014] Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする](./014-cursor-oidc-wif-direct-resource-access.md)（superseded。認証モデルは 015 が維持する）
- [[INFRA-ADR-015] data は箱とし、guest IAM は依存の下流が書く](./015-guest-iam-downstream.md)
- [[INFRA-ADR-017] GitHub Actions の Terraform 由来設定は ops が repository variable として書く](./017-github-actions-terraform-managed-variables.md)
- [[INFRA-ADR-018] Artifact Registry の vulnerability scanning と image retention](./018-artifact-registry-cost-controls.md)
- [Crawler Deploy workflow](../../../.github/workflows/crawler-deploy.yaml)
- [crawler README](../../../workflows/crawler/README.md)
- [Infrastructure README](../../../infra/README.md)
- [issue #60](https://github.com/haru-256/devgist/issues/60)
