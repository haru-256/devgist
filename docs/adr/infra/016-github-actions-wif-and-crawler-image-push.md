# INFRA-ADR-016 GitHub Actions から crawler image を Artifact Registry へ push する

## Conclusion (結論)

- GitHub Actions が GCP を操作するときは、GitHub OIDC JWT を WIF で federated token に換え、その federated principal へリソース IAM を直接付ける。Service Account を impersonate しない。CI 用の新しい SA も作らない。
- GitHub Actions 用 WIF は Cursor 用 pool `cursor` と分ける。ops に pool `github` / provider `oidc` を置く。issuer は `https://token.actions.githubusercontent.com`。
- この identity の初期権限は ops の crawler Artifact Registry リポジトリに対する `roles/artifactregistry.writer` に限定する。terraform apply、tfstate、datalake、Cloud Run Job 起動はこの identity に含めない。
- [INFRA-ADR-010](./010-cloud-run-job-management.md) の「CI が digest を渡して apply する」は維持する。apply の CI は本 ADR では作らない。Job の更新は手元 apply のまま。

## Status (ステータス)

Accepted (承認済み) - 2026-08-28

[INFRA-ADR-015](./015-guest-iam-downstream.md) の Next Steps 3 を、crawler image push の範囲で実装する。010 を supersede しない。

## Context (背景・課題)

### 背景

crawler のコンテナイメージは Artifact Registry に置き、Cloud Run Job は Terraform の `crawler_image`（digest 必須）で参照する（[INFRA-ADR-003](./003-crawler-execution-platform.md)、[INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md)、[INFRA-ADR-010](./010-cloud-run-job-management.md)）。

build / push はまだ手元の `make build-push-image` である。GitHub Actions にあるのは Python lint/test と Terraform の静的検証だけである。apply も plan も無い（[INFRA-ADR-011](./011-terraform-ci-for-monorepo.md)）。

Cursor Cloud 用 WIF は pool `cursor` として ops にある。認証は federated principal への direct resource access である（[INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md)）。guest IAM の置き場は [INFRA-ADR-015](./015-guest-iam-downstream.md) の表である。013 / 014 / 015 は GitHub Actions 用 WIF を別 ADR に送った。Cursor 用 WIF への相乗りは禁止である。

ops には `github-actions` SA があり、project 全体の `roles/artifactregistry.writer` を持つ。WIF は付いていない。本 ADR の CI はこの SA を使わない。

010 は CI の責務を build、push、digest 渡し、apply まで含む。apply は tfstate と Cloud Run まで権限が広がる。今回は image push までで止め、apply の CI は別 ADR に残す。

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

### 比較した選択肢

#### WIF の置き場

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: Cursor の pool `cursor` を共有する | issuer が同じ IdP のとき | pool が増えない | GitHub と Cursor で issuer も claim も違う。013 / 014 が混ぜないと書いた | 非採用 |
| Option B: ops に pool `github` を新設する | GitHub と Cursor を別 IdP として扱う場合 | 信頼条件が分かれる。blast radius を IAM で切れる | pool が 1 本増える | 採用 |

#### 認証モデル

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `github-actions` SA を impersonate する | 監査を SA email に揃えたい場合。federated identity 非対応 API がある場合 | 権限追加は SA に 1 回 | hop が増える。014 が Cursor で捨てた経路を CI に残す | 非採用 |
| Option B: federated principal へ direct resource access | Artifact Registry など対応済み API だけを触る場合 | hop が無い。CI 用 SA が増えない。監査が GitHub の repository claim のまま | リソースを足すたびに principalSet へ IAM を足す | 採用 |

#### 今回実装する範囲

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: build / push と apply の CI を同時に作る | 010 の最終形を一度に閉じたい場合 | Job まで自動化される | tfstate と Cloud Run まで権限が広がる。IAM と tfvars の設計が先に要る | 非採用 |
| Option B: build / push まで。apply は手元 | 権限を AR に閉じたまま CI を始めたい場合 | blast radius が小さい。010 の apply は後続に残せる | digest を手元 apply し忘れると Job が古いまま | 採用 |

### 選定観点

- Cursor と同じ direct resource access に揃えること
- issuer の違う IdP を 1 つの pool に入れないこと
- 初期 IAM を crawler AR writer に限ること
- 010 の apply を否定せず、実装だけ後回しにすること

## Considered Options

### Option A: Cursor の pool `cursor` を共有する [却下]

GitHub OIDC の provider を pool `cursor` に足す、または Cursor の provider 条件を広げる方式。

却下理由:

- Cursor の issuer は `https://api.cursor.com`。GitHub の issuer は `https://token.actions.githubusercontent.com`
- Cursor の claim は `repo_url` と `agent_runtime`。GitHub の claim は `repository` と `ref`
- 013 / 014 は GitHub Actions 用 WIF を混ぜないと書いた

### Option B: ops に pool `github` を新設する [採用]

GitHub 専用の pool と provider を ops に置く。Cursor の pool には触れない。

採用理由:

- 信頼条件が IdP ごとに分かれる
- 既存の `workload_identity_oidc` module を再利用できる
- 後から apply 用 IAM を足すときも、同じ principalSet に binding を足せばよい

### Option C: `github-actions` SA を impersonate する [却下]

WIF のあとに `roles/iam.workloadIdentityUser` で既存 SA を借り、SA に AR writer を付ける方式。

却下理由:

- GCP は direct access を推奨し、impersonation は API 制限があるときの代替である
- Artifact Registry の IAM はその制限に当たらない
- 014 が Cursor で捨てた hop を CI に残す
- 監査ログの principal が SA email に畳まり、GitHub の repository が見えなくなる
- `google-github-actions/auth` は `service_account` を省略すれば federated token をそのまま使う

CI 用の新しい SA も作らない。既存の `github-actions` SA は本 ADR の pipeline では使わない。削除は対象外である。

### Option D: 今回 apply の CI まで作る [却下]

build / push のあと、digest を `crawler_image` に渡して app-dev を apply する方式。010 の最終形である。

却下理由:

- CI identity が tfstate、Cloud Run、crawler SA の actAs まで持つ
- gitignore の `terraform.tfvars` を CI へ渡す設計が先に要る
- image push だけ先に通す方が、失敗したときの権限範囲が小さい

010 は維持する。実装は別 ADR に送る。

## Decision (決定事項)

GitHub Actions から crawler image を Artifact Registry へ push するときは、GitHub OIDC と ops の WIF pool `github` による federated principal への direct resource access を使う。初期 IAM は crawler リポジトリの writer だけである。terraform apply の CI は作らない。

### 採用方針

- WIF pool / provider は `haru256-devgist-ops` に置く。pool ID は `github`。provider ID は `oidc`
- issuer は `https://token.actions.githubusercontent.com`
- JWT の `aud` は WIF provider の既定 audience に固定する
- attribute mapping は少なくとも次を含める
  - `google.subject` = `assertion.sub`
  - `attribute.repository` = `assertion.repository`
  - `attribute.ref` = `assertion.ref`
- attribute condition は `assertion.repository == "haru-256/devgist"`
- IAM member は `principalSet://iam.googleapis.com/projects/<ops_number>/locations/global/workloadIdentityPools/github/attribute.repository/haru-256/devgist`
- repo 単位の principalSet なので、workflow ごとの `sub` allowlist は持たない
- `google-github-actions/auth` に `service_account` を渡さない。credential config に `service_account_impersonation_url` を入れない
- `google-github-actions/auth` に `project_id` として `haru256-devgist-ops` を渡す。WIF provider からは project number しか取れないため、gcloud の quota project に使う
- crawler Artifact Registry リポジトリへ `roles/artifactregistry.writer` を付ける。置き場は ops 同一 root（015）
- tfstate、datalake、app-dev、Cloud Run には付けない
- 既存の `github-actions` SA には `workload_identity_users` を足さない
- CI は image を build / push し、digest 参照を `image_ref:` として出す。Job の更新は手元で `crawler_image` に渡して apply する
- image tag は `workflows/crawler` を最後に変更した commit の短縮 SHA。同じ tag が Artifact Registry にあれば build しない
- `gcloud run jobs deploy` と `gcloud run jobs update` は使わない

### 初期構成

```
haru256-devgist-ops
├── WIF
│   ├── pool: github
│   └── provider: oidc
│       ├── issuer: https://token.actions.githubusercontent.com
│       └── condition: repository == haru-256/devgist
└── Artifact Registry repository crawler
    └── roles/artifactregistry.writer
        └── member: principalSet://.../workloadIdentityPools/github/attribute.repository/haru-256/devgist

GitHub Actions
├── smoke（workflow_dispatch）: token 交換と AR list
└── crawler image（main の workflows/crawler/**、workflow_dispatch）: build / push

手元
└── terraform apply（app-dev の crawler_image に digest を渡す）
```

GitHub の repository variable `GCP_GITHUB_WIF_PROVIDER` に、ops の terraform output `github_wif_provider_name` を入れる。workflow はこの値を `workload_identity_provider` に渡す。

### 再検討条件

- 使いたい Google Cloud API が federated identity に対応していない場合。その API だけ SA impersonation に寄せる
- GitHub Actions から terraform apply するとき。guest IAM は 015 の表に従い、別 ADR で書く
- prod を足すとき
- repository 単位の principalSet が広すぎ、`ref == refs/heads/main` や workflow 名で絞りたくなったとき

## Consequences (結果・影響)

### Positive (メリット)

- Cursor と同じ認証モデルになる。hop が無い
- JSON キーが GitHub に残らない
- Cursor 用 WIF と信頼条件が混ざらない
- CI の初期権限が crawler AR に閉じる
- 010 の apply を否定せず、後から principalSet へ IAM を足せる

### Negative (デメリット)

- digest を手元 apply し忘れると、Job は古い image のままである。010 が受け入れた中間状態が、この ADR の通常運用になる
- repository 単位の principalSet は、この repo のどの workflow からも crawler AR へ push できる
- WIF 自体の apply は手元に残る。CI が自分の identity を作れない
- 既存の `github-actions` SA が残る。本 pipeline は使わない

### Risks / Future Review (将来の課題)

- public repo なので、main に入った workflow を信頼する設計である。workflow file の変更は PR で見る
- Artifact Registry の retention は 010 のまま未決である
- apply の CI を足すときは、tfstate と Cloud Run の IAM がこの principalSet に乗る。そのときの blast radius を別 ADR で書く

## Next Steps

1. Terraform で ops の GitHub 用 WIF pool / provider と、crawler AR への writer を定義する
2. 手元で ops を apply する
3. GitHub の repository variable `GCP_GITHUB_WIF_PROVIDER` に `github_wif_provider_name` を入れる
4. smoke workflow で token 交換と AR list を確認する
5. crawler image の build / push workflow を足す
6. GitHub Actions から terraform apply するための IAM と workflow は、別 ADR で設計する

## Related Documents

- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [[INFRA-ADR-010] Cloud Run Job の管理責務を Terraform に集約する](./010-cloud-run-job-management.md)
- [[INFRA-ADR-011] Terraform monorepo における CI 対象検出と検証方針](./011-terraform-ci-for-monorepo.md)
- [[INFRA-ADR-014] Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする](./014-cursor-oidc-wif-direct-resource-access.md)
- [[INFRA-ADR-015] data は箱とし、guest IAM は依存の下流が書く](./015-guest-iam-downstream.md)
- [Infrastructure README](../../../infra/README.md)
- [issue #60](https://github.com/haru-256/devgist/issues/60)
