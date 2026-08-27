# INFRA-ADR-015 data は箱とし、guest IAM は identity 定義側に書く

## Conclusion (結論)

- data は箱である。リソースを作り、識別子を output する。consumer の principal は持たない。
- ある identity（Service Account でも federated principal でも）が他人の箱へ持つ guest IAM は、その identity を定義した Terraform root が書く。[INFRA-ADR-009](./009-cross-project-iam-ownership.md) の核であり、identity が app 以外にあっても同じである。
- 009 は supersede しない。crawler → Artifact Registry の置き場は変えない。009 の「downstream」は、当時 identity が app にしか無かったことによる。本 ADR はその語を identity 定義側と読み替える。
- [INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) の認証（OIDC + WIF、direct resource access、SA impersonation なし）は維持する。014 が決めた IAM の置き場（app に寄せる、ops に集めない）は捨てる。

## Status (ステータス)

Accepted (承認済み) - 2026-08-27

[INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) を supersede する。014 は削除しない。Accepted だった判断の履歴として残す。014 が差し替えたのは impersonation から direct access への権限の付け方である。本 ADR が差し替えるのは、guest IAM をどの Terraform root に書くかである。認証モデルを読むときは 014 の本文、置き場を読むときは本 ADR を使う。

009 は履歴ごと残す。本 ADR は 009 の例外ではなく、009 が crawler で言ったことを identity の置き場に依存しない文にしたものである。

## Context (背景・課題)

### 背景

009 は crawler SA（app）が Artifact Registry（ops）を読む IAM を、resource 側ではなく identity 側に置いた。理由は循環と転記を避けること、workload の blast radius を SA の家で見ることである。当時 identity は app にしか無く、本文は「downstream 側」と書いた。

014 は Cursor の federated principal へ GCS IAM を直接付けるところまで決めた。実装は app-dev に置いた。app は crawler の datalake IAM を既に書いており、ops と data の remote state を両方読んでいた。014 はそれを「そのリソースを既に扱っている root」と呼び、ops にリソース IAM を集めないとした。

レビューで次が問題になった。Cursor の identity は app に無い。WIF pool は ops にある。bucket は data にある。app はどちらでもない join 点である。

009 の核を Cursor に当てると binding は ops である。014 は「downstream = app」と読んで app に逃した。箱に置く案も出た。どちらも、guest IAM を identity の家以外に置く判断である。

この ADR の対象は Cursor の lake だけではない。次の platform identity、次の箱でも同じ問いになる。ここで一般化する。

### 要件と制約

1. **循環しない。** remote state の向きを逆転させて閉じたグラフにしない。app は既に ops と data を読む。data が app の SA を読むと循環する。
2. **転記しない。** bucket 名も project number も SA email も tfvars にコピーしない。
3. **箱はゲストを知らない。** data は consumer の principal を state に持たない。今の消費者が crawler と Cursor だけなら、ゲスト一覧つき基盤にしない。
4. **009 の crawler 配置を崩さない。** crawler → AR と crawler → datalake は app のままである。
5. **この規則は guest access に限る。** 同一 root 内の IAM、箱の共通 policy（UBLA など）、org / folder の governance、platform 管理者の broad access は 009 が resource 側に残したもので、本 ADR は触らない。
6. **env 境界のコストは隠さない。** env を表さない root に置いた identity が env つきの箱へ grant すると、その root に env つき ACL が並ぶ。それを承知で identity 側を選ぶ。

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 両方を既に読んでいる join に書く | identity 側が箱を読むと循環する場合 | 新しい remote state 辺が無い | identity でも箱でもない。読む人が迷う | 原則非採用。循環するときだけ残る逃げ道 |
| Option B: 箱がゲスト一覧を持つ | resource owner が許可を env の PR で見たい場合 | 箱の apply だけでゲストが変わる | 箱が箱でなくなる。009 の核と矛盾する。循環する consumer は箱に寄せられない | 非採用 |
| Option C: identity を定義した root が書く | identity の blast radius をその家で見たい場合 | crawler と同じ探し方。箱はゲストを知らない | identity の root が箱を読む。共用 root なら env つき ACL が並ぶ | 採用 |

### 選定観点

- 箱をゲスト一覧なしに保てるか
- crawler と platform identity で同じ探し方になるか
- 009 を「app 専用」にせずに済むか
- 循環と転記を増やさないか

## Considered Options

### Option A: join 点に書く [原則却下]

両方の remote state を既に読んでいる root に寄せる。014 の初期実装は app-dev だった。crawler の `google_storage_bucket_iam_member.crawler` の隣に Cursor を置いた。

却下理由:

- その root に identity も箱も無い。都合のよい合流点でしかない
- 「identity 側に書け」とも「箱側に書け」とも言えない
- 次の identity でも同じ迷いが再発する

残す条件: identity 定義側が箱を読むと、既存の辺と循環する場合。そのときは graph を逆転させず、両方を既に見ている root が、identity 側の output から principal を組んで書く。014 が Cursor → datalake でこれを選んだのは誤りである。data は ops を読んでいない。循環は無かった。

### Option B: 箱がゲスト一覧を持つ [却下]

bucket 所有者に member を置く。identity 側の project number や SA email を箱が remote state で読む。

却下理由:

- 箱が consumer の principal を持ち始める。data はゲスト一覧つき基盤になる
- 009 の核（identity 側）と正面から矛盾する
- crawler の grant は循環のため app に残る。同じ箱の guest IAM が identity 側と箱側に割れる

箱が箱でなくなる条件（ゲストが増えて resource owner の承認が要る、prefix / dataset ごとに principal が違う、新しい data env に初期ゲストを載せたい）が来たら、この案を再検討する。そのときは 009 の「shared resource の共通 policy」側へ寄せる判断になる。

### Option C: identity 定義側に書く [採用]

principal を定義した root が、箱への grant を書く。app が crawler SA でやっていることと同じである。identity が ops の WIF なら ops が書く。identity が app の SA なら app が書く。

014 が ops を止めた理由は、循環でも GCP の制約でもない。共用 root に env つき ACL を置きたくない、ops の plan が箱待ちになる、という blast radius と apply の先後である。箱は薄いので先に apply できる。そのコストを受ける。

採用理由:

- 箱はゲストを知らない
- 「identity の家が、他人の箱への grant を書く」が crawler と Cursor で揃う
- 009 を app 専用にしない。identity 側 = その principal を定義した root である
- 箱の識別子は remote state で読む。転記しない

## Decision (決定事項)

guest IAM は identity 定義側に書く。data は箱のまま残す。014 の direct resource access は変えない。

### 採用方針

- 箱（今は `devgist-data/*`）は stateful リソースを作り、識別子を output する。consumer の identity を state に持たない。箱の共通 policy（公開禁止、UBLA、暗号化）は箱側でよい
- ある identity の、箱や他 project リソースへの guest access は、その identity を定義した root が書く
  - app の workload SA → 箱 / Artifact Registry: app（009 のまま）
  - ops の platform identity（Cursor WIF、将来 ops に置くもの）→ 箱: ops
- principal 文字列は identity 側の state で完結させる。箱の識別子だけ remote state で借りる
- identity 定義側が箱を読む辺を足してよいのは、その箱が identity 側をまだ読んでいないときに限る。読んでいれば循環するので Option A に戻る。graph を逆転させない
- 実効 ACL の一覧は Terraform ではなく GCP の IAM policy / Policy Analyzer で見る。同じ箱の member は、identity の家の数だけ Terraform 上は割れる。意図の種類でファイルが分かれている

### 初期構成

最初の適用は Cursor WIF と crawler SA である。規則自体はどちらにも同じである。

```
devgist-data/dev
└── GCS datalake（箱。guest IAM なし）

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

`cursor_oidc_subjects` は ops の gitignore 済み `terraform.tfvars` に置く。空なら IAM member が無い。これは ops が定義した identity の allowlist であり、箱のゲスト一覧ではない。

### apply 順

identity が箱を読まないあいだ、グラフはひし形のままである。`tf → (ops ∥ data) → app`。README の `ops → data → app` は、そのひし形を一列に歩いたものだった。

ops の identity が data の箱へ grant する辺があるあいだの順は次である。

```
tf → data → ops → app
```

箱が無いと identity 側の plan が落ちる。箱を先に作る。

### 権限を広げるとき

同じ identity を、触らせる箱の IAM として identity 定義側に足す。新しい data env を足すなら、その identity の root が env の remote state を追加で読む。共用 root なら env つき ACL が並ぶ。最初から受け入れたコストである。prod を足す判断自体は別途明示する。

その identity が app の compute へ grant したくなると、ops が app を読むことになる。app は既に ops を読んでいるので循環する。その access は本 ADR の原則では ops に書けない。identity を app に置くか、Option A の逃げ道を明示するか、別判断である。

箱が箱でなくなったら Option B を再検討する。そのときは 009 の「resource 所有側の共通 policy」へ寄せ、循環する consumer は identity 側に残る非対称を文書化する。

### 再検討条件

- 箱の消費者が増え、ゲスト一覧を箱の PR で見たくなった場合
- prefix / dataset / Secret 単位で principal が分かれ、identity 側から書けなくなった場合
- 共用 identity root に複数 env の ACL を同じ PR で触るのが危険になった場合
- identity 定義側が箱を読むと循環し、Option A を本則にせざるを得なくなった場合
- federated identity 非対応 API が出て SA impersonation に戻す場合（014 の再検討条件。置き場の話ではない）

## Consequences (結果・影響)

### Positive (メリット)

- 箱の Terraform が薄い。ゲスト追加が箱の PR を叩かない
- ある identity の外部 access を、その identity の家で追える
- 009 を app 専用の例外にしない
- Cursor の allowlist が app-dev の Job 定義から消える

### Negative (デメリット)

- identity が箱を読む辺の数だけ apply 順が伸びる
- 共用 identity root に env つき grant が並ぶ
- 同じ箱の member は Terraform 上 identity の家ごとに割れる。一覧は GCP 側で見る
- identity が自分より downstream のリソースへ grant すると循環する。そのケースは本則では解けない

### Risks / Future Review (将来の課題)

- ops の PR に AR、WIF、data-dev ACL、data-prod ACL が混ざり始める兆候を見る
- data に Cloud SQL / BigQuery を足すとき、まだ箱か、ゲストを持ち始めたかを見直す
- Cursor が app の Job を起動したくなったとき、循環を理由に join へ戻さない。先に identity の置き場を疑う

## Next Steps

1. Cursor の `google_storage_bucket_iam_member.cursor_oidc` と `cursor_oidc_subjects` を identity 定義側（ops）に置く。app-dev から外す
2. ローカルで `data → ops → app` の順に apply する。app の state に旧 Cursor IAM が残っているなら、ops で先に作ってから app 側を外す。app が先に destroy すると GCS member が消える
3. GitHub Actions 用 WIF は、014 と同様に別 ADR または別 PR で設計する。置く root が決まったら、その identity の guest IAM も本 ADR に従う

## Related Documents

- [[INFRA-ADR-009] Cross-project IAM binding の ownership](./009-cross-project-iam-ownership.md)（核は本 ADR と同じ。crawler → AR の配置は変えない）
- [[INFRA-ADR-014] Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする](./014-cursor-oidc-wif-direct-resource-access.md)（superseded。認証モデルは本 ADR が維持する）
- [[INFRA-ADR-013] Cursor Cloud から GCP への認証に Cursor OIDC と WIF を採用する](./013-cursor-oidc-workload-identity-federation.md)（superseded）
- [[INFRA-ADR-006] Cross-project Terraform output 共有戦略](./006-cross-project-output-sharing.md)
- [[INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略](./001-gcp-project-structure.md)
- [docs/runbooks/cursor-cloud-oidc-wif.md](../../runbooks/cursor-cloud-oidc-wif.md)
