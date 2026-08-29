# INFRA-ADR-017 GitHub Actions の Terraform 由来設定は ops が repository variable として書く

## Conclusion (結論)

- Artifact Registry の URL、image 名、WIF provider 名のように Terraform が正本の値は、workflow にベタ書きせず、ops の Terraform が GitHub の **repository variable** として書く。
- GitHub Environment `dev` も ops が作る。これは OIDC claim と IAM の `attribute.environment` の契約であり、image の行き先を環境ごとに分ける器ではない。
- crawler の `REPO_URL` / `IMAGE_NAME` は Environment 変数にしない。Artifact Registry は prod / dev で 1 本だからである。

## Status (ステータス)

Accepted (承認済み) - 2026-08-28

[INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md) の GitHub 側設定の書き手を決める。016 の認証モデルは維持する。

## Context (背景・課題)

### 背景

crawler image の push 先は ops の Artifact Registry である。URL は region、project、repository id から決まり、これらはすでに `devgist-ops` の Terraform が持っている（[INFRA-ADR-004](./004-separate-tf-and-ops-projects.md)、[INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md)、[INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md)）。

016 では WIF provider 名を terraform output にし、GitHub の repository variable `GCP_GITHUB_WIF_PROVIDER` へ人手でコピーする運用だった。workflow の `REPO_URL` は YAML にベタ書きされていた。どちらも Terraform が正本なのに、GitHub 側が別管理になる。

GitHub Environment `dev` は 016 の IAM（`attribute.environment/dev`）に必要である。protection rule は付けない。public repo では初回 run でも作れるが、名前の正本が Terraform に無い。

### 要件と制約

1. **正本は 1 つ**
   - region / project / AR repository / WIF provider を YAML と GitHub UI に再掲しない
2. **ops が GitHub 連携の書き手**
   - 004 の ops は CI/CD と Artifact Registry の置き場である
3. **値の軸と identity の軸を混ぜない**
   - GitHub Environment は OIDC / IAM 用である
   - AR は 007 のとおり prod / dev で共用する
4. **apply は手元のまま**
   - 016 と同様、terraform apply の CI は作らない
5. **長寿命の GitHub token を repo secret にしない**
   - GitHub provider の認証は apply する人の `GITHUB_TOKEN` とする。state にも tfvars にも書かない

### 比較した選択肢

#### 値の置き場

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: workflow YAML にベタ書き | 値がほぼ変わらず、Terraform と二重管理しても困らないとき | GitHub provider が不要 | region / project / repository が YAML と Terraform で乖離する | 非採用 |
| Option B: GitHub Environment 変数 | 環境ごとに行き先が違うとき | job の `environment:` と値が同じ器に載る | 007 の共用 AR では prod 用 Environment に同じ値を複製する。WIF provider 名も env に閉じると prod job から見えない | 非採用 |
| Option C: repository variable を ops Terraform が書く | Terraform が正本で、値が環境で変わらないとき | apply 1 回で AR / WIF / GitHub が揃う。人手コピーが消える | ops の plan に GitHub token が要る。GitHub API 障害が GCP apply を止める | 採用 |

#### GitHub リソースの置き場

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 別 root（例: `devgist-github`） | GitHub だけ独立して apply したいとき | GCP apply が GitHub token に依存しない | AR URL と WIF 名を remote state で引き、apply が 2 回になる。004 の ops 責務が割れる | 非採用 |
| Option B: `devgist-ops` に GitHub provider を足す | GitHub 連携の正本が ops のとき | 値が同じ state で閉じる | GitHub token が ops plan の前提になる | 採用 |

### 選定観点

- Terraform が正本の値を、GitHub へ人手で移さないこと
- Environment を identity 用の器として保ち、共用 AR の URL を env に閉じないこと
- 004 の ops に GitHub Actions 連携を置くこと
- apply の CI を増やさないこと

## Considered Options

### Option A: workflow に URL をベタ書きする [却下]

region と project と repository id を YAML に書く方式。

却下理由:

- 正本は Artifact Registry モジュールである
- `configure-docker` の host も同じ URL から取れるのに、もう 1 箇所ハードコードが増える

### Option B: GitHub Environment 変数にする [却下]

`github_actions_environment_variable` を Environment `dev` に付ける方式。job が `environment: dev` なので動く。

却下理由:

- 007 は crawler AR を prod / dev で 1 本にする
- 016 の WIF provider は prod / dev で共有する
- Environment 変数は「その Environment を使う job」にしか見えない。prod を足すと、同じ ops 由来の値を複製するか、参照できなくなる
- Environment `dev` の役割は OIDC claim であり、image の行き先ではない

### Option C: ops が repository variable と Environment 本体を書く [採用]

`devgist-ops` に `integrations/github` を足す。Environment `dev` は `github_repository_environment` で作る。値は `github_actions_variable` で repository に書く。

採用理由:

- AR URL、image 名、WIF provider 名が同じ apply で GitHub に載る
- repository variable は Environment を跨いで読める。prod job も同じ WIF provider 名を使える
- Environment `dev` の名前が IAM の `attribute.environment` と Terraform 上で同じ local になる
- GitHub 用の別 root を増やさない

## Decision (決定事項)

Terraform が正本の GitHub Actions 設定は、`devgist-ops` が GitHub provider 経由で書く。値は repository variable にする。GitHub Environment `dev` は identity 用に ops が管理し、protection rule は付けない。

### 採用方針

- GitHub provider は `devgist-ops` に置く。owner、repository 名、repository id、owner id はこの root の identity なので local に置く。Cursor OIDC の `repo_url` は owner と name から組み立てる。token は apply 時の環境変数 `GITHUB_TOKEN` とし、tfvars と state には書かない
- GitHub Environment 名は `dev` で固定する。IAM の `attribute.environment` も `dev`。reviewers と `deployment_branch_policy` は付けない。どの branch でも image を push するためである
- repository variable は次の 3 つにする
  - `GCP_GITHUB_WIF_PROVIDER` = GitHub WIF provider の resource name
  - `CRAWLER_REPO_URL` = crawler Artifact Registry の Docker URL
  - `CRAWLER_IMAGE_NAME` = crawler Artifact Registry の repository id。初期は image 名と repository id を一致させる
- workflow は `vars.CRAWLER_REPO_URL` と `vars.CRAWLER_IMAGE_NAME` を script の `REPO_URL` / `IMAGE_NAME` に渡す。`configure-docker` の host は `REPO_URL` の先頭から取る。`GCP_PROJECT_ID` はまだ workflow に残す
- 手元の `make build-push-image` は GitHub variable を読まない。Makefile の default は別経路として残す
- ops を apply する前は repository variable が空なので、crawler image job は skip する。README だけの変更では workflow を起動しない

### 初期構成

```
devgist-ops Terraform
├── Artifact Registry crawler
├── WIF pool github-devgist / provider oidc
├── github_repository_environment.dev
└── github_actions_variable
    ├── GCP_GITHUB_WIF_PROVIDER
    ├── CRAWLER_REPO_URL
    └── CRAWLER_IMAGE_NAME

GitHub Actions crawler-image.yml
├── environment: dev
├── vars.CRAWLER_REPO_URL → REPO_URL
├── vars.CRAWLER_IMAGE_NAME → IMAGE_NAME
└── vars.GCP_GITHUB_WIF_PROVIDER → workload_identity_provider
```

### 再検討条件

- Artifact Registry を環境で分割するとき。そのときは Environment 変数を再検討する
- 1 つの AR repository に複数 image を置くとき。`CRAWLER_IMAGE_NAME` を repository id から切り離す
- GitHub App で Terraform を動かすとき。PAT の `GITHUB_TOKEN` をやめる
- terraform apply の CI を足すとき。GitHub token の置き場を別 ADR で書く
- GitHub API 障害で GCP apply が止まるのが許容できないとき。GitHub 用 root を再検討する

## Consequences (結果・影響)

### Positive (メリット)

- AR / WIF / GitHub variable の正本が ops の 1 apply に揃う
- workflow から region と project と repository のベタ書きが消える
- Environment `dev` の名前が IAM と Terraform でずれない

### Negative (デメリット)

- ops の `terraform plan` / `apply` に GitHub token が要る
- GitHub 側の失敗が GCP リソースと同じ state に載る
- 既存の Environment `dev` は先に import する必要がある

### Risks / Future Review (将来の課題)

- token の権限は Environments と Variables の write で足りる。repo の administration 全体は渡さない
- public repo の Environment に protection を付けない方針は 016 のままである
- `GCP_PROJECT_ID` も Terraform 由来だが、今回は WIF と image の行き先だけを移す

## Next Steps

1. `devgist-ops` に GitHub provider、Environment `dev`、repository variable を定義する
2. 手元 apply の前に、既存の Environment `dev` を `terraform import github_repository_environment.dev devgist:dev` する
3. `GITHUB_TOKEN` を入れて ops を apply する
4. crawler image workflow が `vars.CRAWLER_REPO_URL` / `vars.CRAWLER_IMAGE_NAME` / `vars.GCP_GITHUB_WIF_PROVIDER` を読むことを確認する

## Related Documents

- [[INFRA-ADR-004] Terraform State Project と Ops Project を分離する](./004-separate-tf-and-ops-projects.md)
- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [[INFRA-ADR-016] GitHub Actions から crawler image を Artifact Registry へ push する](./016-github-actions-wif-and-crawler-image-push.md)
- [Infrastructure README](../../../infra/README.md)
- [issue #60](https://github.com/haru-256/devgist/issues/60)
