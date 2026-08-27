# INFRA-ADR-015 data は箱とし、guest IAM は依存の下流が書く

## Conclusion (結論)

- data は箱である。リソースを作り、識別子を output する。consumer の principal は持たない。
- guest IAM を書いてよいのは、その binding がつなぐ **identity の root** か **resource の root** だけである。どちらでもない第三の root には書かない。
- その二 root のうち、**既に下流の側**が書く。下流は片方を自分で持ち、もう片方を `terraform_remote_state` で読む。辺を逆向きに足して循環させない。
- 二 root が並列なら、箱を上流にする（箱 → identity）。箱が consumer を読まない。identity が既に上流なら、resource 側が書く。resource 側が箱なら、ゲスト一覧は持たせない。
- [INFRA-ADR-009](./009-cross-project-iam-ownership.md) は supersede しない。crawler → Artifact Registry は、app が下流なので app が書く。009 が却下したのは上流の resource 側（ops が crawler SA を読む）である。
- [INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) の認証は維持する。014 が Cursor → datalake を app に置いた判断は捨てる。app は identity でも箱でもない。

## Status (ステータス)

Accepted (承認済み) - 2026-08-27

[INFRA-ADR-014](./014-cursor-oidc-wif-direct-resource-access.md) を supersede する。014 は削除しない。014 が差し替えたのは impersonation から direct access への権限の付け方である。本 ADR が差し替えるのは guest IAM の置き場である。

009 は残す。009 の「downstream」は crawler では identity 側と一致した。本 ADR は、identity が上流にあるときも同じ「下流が書く」を使う。常に identity 側、ではない。

## Context (背景・課題)

### 背景

009 は crawler SA（app）→ Artifact Registry（ops）を identity 側に置いた。ops が app を読むと循環する。当時 identity は app にしか無く、本文は「downstream 側」と書いた。crawler では identity 側 = 下流だった。

014 は Cursor の federated principal へ GCS IAM を直接付け、実装を app-dev に置いた。app は ops と data を両方読む。014 はそれを「そのリソースを既に扱っている root」と呼んだ。実際の identity は ops、箱は data である。app は第三の root だった。

Cursor → datalake を identity 側（ops）に直すと、data は ops を読んでいないので循環しない。箱 → ops の辺を足せる。これは 009 の crawler → data と同じ形である。

同じ文を「常に identity 側」まで伸ばすと、Cursor → Cloud Run で詰まる。app は ops を既に読む。ops が app を読むと循環する。ここを例外や別判断にすると、本則が穴になる。

問いをやり直す。書いてよい root はどこか。辺はどちら向きか。

### 要件と制約

1. **循環しない。** 既存の remote state 辺を逆転させない。app は ops と data を読む。data は consumer を読まない。
2. **転記しない。** 識別子は remote state で借りる。
3. **箱はゲストを知らない。** data は consumer の principal を持たない。
4. **第三の root に逃さない。** identity も resource も持たない root は、両方読めるからといって書かない。
5. **009 の crawler 配置を崩さない。** crawler → AR と crawler → datalake は app のまま。
6. **この規則は guest access に限る。** 同一 root 内の IAM、箱の共通 policy、org / folder の governance は 009 が resource 側に残したもので、触らない。

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 第三の root（join） | 両方を既に読んでいる root へ寄せたい場合 | 新しい辺が無い | 所有していない IAM が溜まる。014 の失敗 | 非採用 |
| Option B: 箱がゲスト一覧を持つ | resource owner が許可を env の PR で見たい場合 | 箱の apply だけでゲストが変わる | 箱が箱でなくなる。crawler は循環で箱に寄せられない | 非採用 |
| Option C: 常に identity 定義側 | blast radius を identity の家だけに集めたい場合 | 探し方が一箇所 | identity が上流だと循環する。例外が本則を食う | 非採用 |
| Option D: platform identity を app へ移す | 循環を identity の置き場で消したい場合 | Cursor の IAM が app に揃う | WIF が env 倍。ops の platform 責務と矛盾する | 非採用 |
| Option E: 所有する二 root の下流が書く。箱は書かない | DAG を保ったまま置き場を一意にしたい場合 | 循環が穴にならない。第三の root が無い | Cursor の blast radius が ops と app に割れる | 採用 |

### 選定観点

- 箱をゲスト一覧なしに保てるか
- 循環を例外にせず本則で解けるか
- 014 の第三 root に戻らないか
- 009 の crawler → AR を壊さないか

## Considered Options

### Option A: 第三の root に書く [却下]

両方の remote state を既に読んでいる root に寄せる。014 は app-dev に Cursor → datalake を置いた。

却下理由:

- その root は identity も箱も持たない
- 次の identity でも同じ迷いが再発する
- Cursor → Cloud Run では app が resource の所有者なので、app に書くのはこの案ではない。所有していないものへ逃げるのがこの案である

### Option B: 箱がゲスト一覧を持つ [却下]

箱が identity 側の output を読み、member を置く。

却下理由:

- 箱が consumer の principal を持ち始める
- crawler の grant は循環のため app に残る。同じ箱の guest IAM が割れる

箱が箱でなくなる条件が来たら、009 の「shared resource の共通 policy」へ寄せて再検討する。

### Option C: 常に identity 定義側に書く [却下]

principal を定義した root が、触るリソースの IAM を全部書く。

却下理由:

- identity が resource より上流だと、identity 側が resource を読むことになり循環する
- そのときだけ join に逃げる、とすると本則に穴が開く。前回の文面がそれだった

Cursor → datalake だけ見るとこの案で足りる。Cursor → Cloud Run まで含めると足りない。

### Option D: Cursor の identity を app に置く [却下]

循環しないよう、触る compute と同じ root に WIF を移す。

却下理由:

- WIF pool は env を表さない platform である。ops に置いた判断（013 / 014）を、IAM の循環だけでひっくり返さない
- app-dev と app-prod で pool が倍になる。Cursor の `sub` allowlist も倍になる
- lake だけ触る今の権限（014）に対して、identity の家を compute に移す必然が無い

identity の置き場を疑うのは、ops に置いた identity が app のほぼ全部を所有し始めたときである。今ではない。

### Option E: 所有する二 root の下流が書く [採用]

binding は identity の root か resource の root にだけ置く。二 root のうち、依存の下流が書く。

- identity が下流（crawler → data、crawler → AR、Cursor → data）: identity の家が書く。009 と同じ
- identity が上流（Cursor → Cloud Run）: resource の家が書く。app は Job の所有者である。第三の root ではない
- 並列（当初の ops と data）: 箱を上流にする。箱はゲストを書かない

009 が却下した Option A は、**上流の** resource 側（ops が crawler SA を読む）である。本 ADR が許す resource 側は、**下流の** resource 側（app が ops の principal を読む）だけである。

採用理由:

- 循環が本則の外に出ない
- 箱はゲストを知らない
- 第三の root が無い。014 の失敗を繰り返さない
- crawler → AR は app が下流のまま。009 を壊さない

## Decision (決定事項)

guest IAM は、identity と resource を所有する二 root のうち依存の下流が書く。data は箱のまま残す。014 の direct resource access は変えない。

### 採用方針

- 箱（今は `devgist-data/*`）は stateful リソースを作り、識別子を output する。consumer の identity を state に持たない。箱の共通 policy（公開禁止、UBLA、暗号化）は箱側でよい
- guest IAM の置き場は次で一意に決まる

| identity の root \ resource の root | data（箱） | ops | app |
|---|---|---|---|
| ops | ops が書く。必要なら data → ops を足す | 同一 root | app が書く。ops → app を逆転しない |
| app | app が書く | app が書く（009） | 同一 root |

- 書いてはいけない場所: 箱のゲスト一覧。identity も resource も持たない第三の root
- 実効 ACL の一覧は Terraform ではなく GCP の IAM policy / Policy Analyzer で見る。同じリソースの member は、書く root の数だけ Terraform 上は割れる

### 初期構成

最初の適用は Cursor WIF と crawler SA である。どちらも表の該当マスに従う。

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

`cursor_oidc_subjects` は ops の gitignore 済み `terraform.tfvars` に置く。空なら IAM member が無い。ops が定義した identity の allowlist であり、箱のゲスト一覧ではない。

Cloud Run Job 起動はこの identity に含めない（014）。含めるときは表どおり app が書く。ops の principal は app が既に読む remote state から組む。ops は app を読まない。

### apply 順

identity が箱を読まないあいだ、グラフはひし形のままである。`tf → (ops ∥ data) → app`。

ops の identity が data の箱へ grant する辺があるあいだの順は次である。

```
tf → data → ops → app
```

app は sink である。app のリソースへの guest IAM を足しても、この順は変わらない。

### 権限を広げるとき

- 箱を足す: identity の root が箱の remote state を読む。共用 root なら env つき ACL が並ぶ。承知のコストである
- app の compute を足す: app が ops の principal を member にする。identity を app に移さない。第三の root にも置かない
- 箱が箱でなくなったら Option B を再検討する

### 再検討条件

- 箱の消費者が増え、ゲスト一覧を箱の PR で見たくなった場合
- prefix / dataset / Secret 単位で principal が分かれ、下流側から書けなくなった場合
- 共用 identity root に複数 env の ACL を同じ PR で触るのが危険になった場合
- ops の identity が app のほぼ全部を所有し、identity の家を app へ移す方が小さくなった場合（Option D の再訪）
- federated identity 非対応 API が出て SA impersonation に戻す場合（014 の再検討条件。置き場の話ではない）

## Consequences (結果・影響)

### Positive (メリット)

- 箱の Terraform が薄い
- 循環を例外にしない。置き場が表で決まる
- 第三の root に IAM が溜まらない
- 009 の crawler → AR をそのまま読める

### Negative (デメリット)

- 一つの identity の guest IAM が、触る resource の上流・下流で root をまたぐ。Cursor なら lake は ops、Job 起動は app
- 共用 identity root に env つき grant が並ぶ
- 同じ箱の member は Terraform 上 identity の家ごとに割れる。一覧は GCP 側で見る

### Risks / Future Review (将来の課題)

- ops の PR に AR、WIF、data-dev ACL、data-prod ACL が混ざり始める兆候を見る
- data に Cloud SQL / BigQuery を足すとき、まだ箱かを見直す
- Cursor の Job 起動を足すとき、app が書くことを「014 の join に戻った」と誤読しない。app は Job の所有者である

## Next Steps

1. Cursor の `google_storage_bucket_iam_member.cursor_oidc` と `cursor_oidc_subjects` を ops に置く。app-dev から外す。これは表の ops × data である
2. ローカルで `data → ops → app` の順に apply する。app の state に旧 Cursor IAM が残っているなら、ops で先に作ってから app 側を外す
3. GitHub Actions 用 WIF は別 ADR または別 PR で設計する。置く root が決まったら、その identity の guest IAM も本 ADR の表に従う

## Related Documents

- [[INFRA-ADR-009] Cross-project IAM binding の ownership](./009-cross-project-iam-ownership.md)（crawler → AR は、app が下流なので app。本 ADR は 009 が却下した上流 resource 側を復活させない）
- [[INFRA-ADR-014] Cursor Cloud の GCP 権限は WIF federated principal への direct resource access とする](./014-cursor-oidc-wif-direct-resource-access.md)（superseded。認証モデルは本 ADR が維持する）
- [[INFRA-ADR-013] Cursor Cloud から GCP への認証に Cursor OIDC と WIF を採用する](./013-cursor-oidc-workload-identity-federation.md)（superseded）
- [[INFRA-ADR-006] Cross-project Terraform output 共有戦略](./006-cross-project-output-sharing.md)
- [[INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略](./001-gcp-project-structure.md)
- [docs/runbooks/cursor-cloud-oidc-wif.md](../../runbooks/cursor-cloud-oidc-wif.md)
