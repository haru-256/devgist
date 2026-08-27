# INFRA-ADR-015 Cursor の datalake IAM は WIF を定義する ops に置く

## Conclusion (結論)

- data は箱である。bucket を作り、名前を output する。誰が触れるかは知らない。
- Cursor Cloud の federated principal へ datalake の `objectViewer` / `objectCreator` を付ける IAM は、WIF を定義する `devgist-ops` が書く。
- crawler SA の datalake IAM は `devgist-app/dev` のままとする。[INFRA-ADR-009](./009-cross-project-iam-ownership.md) の対象は env つき workload SA である。
- [INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) の認証（OIDC + WIF、direct resource access、SA impersonation なし）は維持する。014 が決めた IAM の置き場（app-dev、ops に集めない、ops は data を読まない）は捨てる。

## Status (ステータス)

Accepted (承認済み) - 2026-08-27

[INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) を supersede する。014 は削除しない。Accepted だった判断の履歴として残す。014 が差し替えたのは impersonation から direct access への権限の付け方である。本 ADR が差し替えるのは、その IAM binding をどの Terraform root に書くかである。認証モデル（direct resource access、鍵なし、GHA 用 WIF と混ぜない）を読むときは 014 の本文、置き場を読むときは本 ADR を使う。

## Context (背景・課題)

### 背景

014 は federated principal へ GCS IAM を直接付けるところまで決めた。実装は `devgist-app/dev` に置いた。app は crawler の datalake IAM を既に書いており、ops と data の remote state を両方読んでいた。014 はそれを「そのリソースを既に扱っている root」と呼び、ops にリソース IAM を集めないとした。

レビューで次が問題になった。Cursor の identity は app に無い。WIF pool は ops にある。bucket は data にある。app はどちらでもない join 点である。

009 の決定文は「workload 固有の cross-project IAM は identity を定義する側で書く」である。crawler なら SA は app、binding も app。同じ文面を Cursor に当てると binding は ops である。014 はそれを意図的に避け、app に逃した。

data に置く案も出た。lake の許可を env の state に閉じられる。ただし今の `devgist-data/dev` は IAM を一台も持たない箱である。Cursor の allowlist と ops の remote state を data に足すと、箱がゲスト一覧つき基盤に変わる。

### 要件と制約

1. **循環しない。** app は bucket 名を data から読む。data が crawler SA を app から読むと循環する。crawler の datalake IAM は app から動かせない。
2. **転記しない。** bucket 名も project number も tfvars にコピーしない。
3. **data の薄さを守る。** 今の消費者が crawler と Cursor だけなら、data にゲスト一覧を持たせない。
4. **014 の認証は崩さない。** 鍵を置かない。SA を impersonate しない。GHA 用 WIF と混ぜない。
5. **env 境界のコストは隠さない。** ops は env を表さない。lake IAM を ops に書くと、将来 data-prod を足したとき同じ state に dev/prod の ACL が並ぶ。それを承知で選ぶ。

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: app-dev（014 の現状） | ops と data を既に読んでいる join に寄せたい場合 | 新しい remote state 辺が無い | identity でも箱でもない。読む人が迷う | 非採用 |
| Option B: data-dev | lake の許可を env の state に閉じたい場合 | data-dev の apply だけでゲストが変わる。ops は WIF だけ | data が箱でなくなる。009 の文面と矛盾する。crawler は app、Cursor は data と割れる | 非採用 |
| Option C: ops | identity の家から箱へ手を伸ばす場合 | crawler と同じ形。data は箱のまま。009 の文面と一致する | ops が data を読む。箱が無いと ops の plan が止まる。prod を足すと ops に env つき ACL が並ぶ | 採用 |

### 選定観点

- data を箱のままにできるか
- crawler の grant と同じ探し方になるか
- 009 を Cursor 用に例外化せずに済むか
- 循環と転記を増やさないか

## Considered Options

### Option A: app-dev に書く [却下]

014 の初期実装。crawler の `google_storage_bucket_iam_member.crawler` の隣に Cursor を置いた。

却下理由:

- Cursor の SA も bucket も app に無い。都合のよい join 点でしかない
- allowlist を変えるたびに app-dev を apply する。Cloud Run Job と同じ state である
- 「identity 側に書け」とも「resource 側に書け」とも言えない

### Option B: data-dev に書く [却下]

bucket 所有者に member を置く。ops の project number と pool id を data が remote state で読む。

却下理由:

- 今の data は箱である。IAM も Cursor `sub` も無い。ここに allowlist を置くと、箱ではなくゲスト一覧つき基盤になる
- 消費者がまだ二人しかいない。その時点で data にゲストを持たせる必然が無い
- crawler の grant は循環のため app に残る。lake IAM が app と data に割れる
- 009 の「identity 側」と正面から矛盾する。例外を 009 に足すことになる

data が箱でなくなる条件（ゲストが増える、prefix ごとに principal が違う、resource owner の承認が要る、新しい data env に初期ゲストを載せたい）が来たら、この案を再検討する。

### Option C: ops に書く [採用]

WIF を定義した root が、箱への grant を書く。app が crawler SA でやっていることと同じである。

014 がこれを止めた理由は、循環でも GCP の制約でもない。共用 root に env つき ACL を置きたくない、ops の plan が lake 待ちになる、という blast radius と apply の先後である。data は薄いので先に apply できる。今は data-dev しか無い。そのコストを受ける。

採用理由:

- data は箱のまま
- 「identity の家が、他人の箱への grant を書く」が crawler と Cursor で揃う
- 009 を Cursor 用に曲げない。009 が想定したのは env つき SA が downstream にある場合であり、Cursor の identity は ops にある。identity 側 = ops で、文面どおりである
- bucket 名は data の output を読む。転記しない

## Decision (決定事項)

Cursor Cloud の datalake IAM binding は `devgist-ops` で管理する。data は箱のまま残す。014 の direct resource access は変えない。

### 採用方針

- data は bucket（および将来の stateful リソース）を作り、識別子を output する。consumer の identity を state に持たない
- env つき workload SA の外部 access は、SA を発行した root が書く。今は crawler の datalake IAM が app。009 のままである
- 共用基盤の identity（Cursor WIF、将来 ops に置く platform identity）が env の箱へ手を伸ばす grant は、その identity を定義した root が書く。今は ops
- ops は data の `datalake_bucket_name` を `terraform_remote_state` で読む。principal 文字列は ops 自身の project number と pool id から組む
- `cursor_oidc_subjects` は ops の gitignore 済み `terraform.tfvars` に置く。空なら IAM member が無い
- 実効 ACL の一覧は Terraform ではなく `gcloud storage buckets get-iam-policy` で見る。lake の member は crawler（app）と Cursor（ops）で割れる。意図の種類でファイルが分かれている

### 初期構成

```
devgist-data/dev
└── GCS datalake（箱。IAM なし）

devgist-ops
├── WIF pool cursor / provider oidc
└── GCS IAM（data-dev datalake へ federated principal を付与）
    ├── roles/storage.objectViewer
    └── roles/storage.objectCreator
        └── member: principal://.../workloadIdentityPools/cursor/subject/<allowlisted sub>

devgist-app/dev
├── Service Account: crawler
└── GCS IAM（同じ箱へ crawler SA を付与）
```

### apply 順

crawler だけならグラフはひし形のままである。`tf → (ops ∥ data) → app`。README の `ops → data → app` は、そのひし形を一列に歩いたものだった。

Cursor の lake IAM を ops に置くと、ops が data を読む。その辺があるあいだの順は次である。

```
tf → data → ops → app
```

WIF と Artifact Registry だけ先に欲しいときは、data がまだ無いと ops の plan が落ちる。箱を先に作る。

### 権限を広げるとき

同じ Cursor `sub` を、触らせる箱の IAM として ops に足す。新しい data env（prod）を足すなら、ops がその env の remote state を追加で読む。それは共用 state に env つき ACL が並ぶ、と最初から受け入れたコストである。prod を足す判断自体は別途明示する。

data が箱でなくなったら、本 ADR の Option B を再検討する。そのときは Cursor の grant を data へ移し、crawler は循環のため app に残る非対称を文書化する。

### 再検討条件

- data の消費者が増え、ゲスト一覧を data の PR で見たくなった場合
- prefix / dataset / Secret 単位で principal が分かれ、consumer 側から書けなくなった場合
- data-prod の lake ACL を ops と同じ PR で触るのが危険になった場合
- federated identity 非対応 API が出て SA impersonation に戻す場合（014 の再検討条件。置き場の話ではない）

## Consequences (結果・影響)

### Positive (メリット)

- data の Terraform が薄い
- Cursor の grant を探す場所が WIF と同じ ops になる
- 009 を Cursor 用に例外化しない
- app-dev から Cursor allowlist が消える。Job 定義と関係ない

### Negative (デメリット)

- ops の apply が data に依存する
- 将来 data-prod の grant も ops に並ぶ
- lake の member は app と ops に割れる。一覧は GCP 側で見る

### Risks / Future Review (将来の課題)

- ops の PR に AR、WIF、data-dev ACL、data-prod ACL が混ざり始める兆候を見る
- data に Cloud SQL / BigQuery を足すとき、まだ箱か、ゲストを持ち始めたかを見直す

## Next Steps

1. `google_storage_bucket_iam_member.cursor_oidc` と `cursor_oidc_subjects` を `devgist-ops` に置く。app-dev から外す
2. ローカルで `data → ops → app` の順に apply する。app の state に旧 Cursor IAM が残っているなら、ops で先に作ってから app 側を外す。app が先に destroy すると GCS member が消える
3. GitHub Actions 用 WIF は、014 と同様に別 ADR または別 PR で設計する

## Related Documents

- [[INFRA-ADR-014] Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする](./014-cursor-oidc-wif-direct-resource-access.md)（superseded。認証モデルは本 ADR が維持する）
- [[INFRA-ADR-013] Cursor Cloud から GCP への認証に Cursor OIDC と WIF を採用する](./013-cursor-oidc-workload-identity-federation.md)（superseded）
- [[INFRA-ADR-009] Cross-project IAM binding の ownership](./009-cross-project-iam-ownership.md)
- [[INFRA-ADR-006] Cross-project Terraform output 共有戦略](./006-cross-project-output-sharing.md)
- [[INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略](./001-gcp-project-structure.md)
- [docs/runbooks/cursor-cloud-oidc-wif.md](../../runbooks/cursor-cloud-oidc-wif.md)
