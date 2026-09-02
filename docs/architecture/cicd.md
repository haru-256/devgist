# CI/CD

認証モデルと WIF pool の構成は [iam.md](iam.md) を参照。ここでは workflow と権限の割り当てを扱う。

## workflow 一覧

| workflow | trigger | `ci_scope` | できること |
|---|---|---|---|
| `terraform-ci.yml` | PR / `main` への push | なし（GCP 認証を持たない） | fmt / validate / test / tflint / trivy |
| `terraform-plan.yml` | `pull_request` のみ | `terraform-plan-dev` | plan 対象 root と state の **read のみ** |
| `terraform-apply.yml` | `main` への push、`workflow_dispatch`（`target=dev`） | plan job は `terraform-plan-dev`、apply job は `terraform-apply-dev` | ops / data-dev / app-dev の apply |
| `crawler-deploy.yaml` | `main` への push（`workflow_dispatch` は下記の注意） | `crawler-push-dev` | crawler Artifact Registry への push のみ |
| `python-ci.yml` | PR / `main` への push / `workflow_dispatch` | なし | crawler の lint / test |

terraform 系と crawler-deploy は **path filter 付き**です。`infra/terraform/**` や `workflows/crawler/**` に変更が無ければ走りません。
crawler-deploy は `workflows/crawler/**/*.md` を除外するため、README だけの変更では image を作りません。

> **注意**: `crawler-deploy.yaml` の `workflow_dispatch` から GCP 認証は通りません。
> `crawler-push-dev` の成立条件が `event_name == "push"` を含むため、手動起動では `ci_scope=none` になり token 交換が拒否されます。
> 手元から image を作る場合は `make build-push-image` を使ってください。

根拠: [INFRA-ADR-011](../adr/infra/011-terraform-ci-for-monorepo.md)（静的 CI）、[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md)（plan / apply）、[INFRA-ADR-016](../adr/infra/016-github-actions-wif-and-crawler-image-push.md)（image push）

## `ci_scope` で認可を分ける

`attribute.ci_scope` は provider の attribute mapping が、GitHub が署名した `workflow_ref` / `event_name` / `ref` / `environment` から CEL で合成する。
**workflow の YAML が名乗る文字列ではない。** だから PR が apply 用の principal を選べない。

| `ci_scope` | 成立条件（概略） | 付いている IAM |
|---|---|---|
| `terraform-plan-dev` | `terraform-plan.yml@refs/pull/*` の `pull_request`、または `terraform-apply.yml@refs/heads/main` で environment 無し | tf / data-dev / ops / app-dev の `roles/viewer` + `roles/iam.securityReviewer` |
| `terraform-apply-dev` | `terraform-apply.yml@refs/heads/main` かつ `ref == refs/heads/main` かつ `push` または `workflow_dispatch` かつ `environment == "dev"` | 上記に加え、各 project の mutation ロールと deploy 対象 tfstate bucket の `roles/storage.objectUser` |
| `crawler-push-dev` | `crawler-deploy.yaml@refs/heads/main` かつ `push` かつ `ref == refs/heads/main` | crawler Artifact Registry の `roles/artifactregistry.writer` のみ |
| `terraform-{plan,apply}-prod` | `terraform-apply-prod.yml` 由来 | **未付与**。prod 環境の作成時に足す |
| `none` | 上記以外 | どの principalSet にも付かない。provider condition が token 交換を拒否する |

合成は apply → plan → crawler → `none` の順に評価する。部分一致（`contains(...)`）は使わない。

`plan` には `create` / `update` / `delete` と IAM 変更と WIF 変更を一切付けない。`roles/editor` も付けない。
resource 単位の custom role は作らない（predefined で足りるため。[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md) Option E）。

## write は protected `main` に閉じる

`main` は Ruleset 済み（PR 必須、required checks、up-to-date 必須、force push / delete 禁止）。
apply も crawler の image push も `main` の push だけで動く。feature branch では `ci_scope=none` になり token 交換に失敗する。

fork の `pull_request` は GitHub が OIDC token を発行しないため、workflow 側に追加の head repo ガードは置かない。

## CI が書き換えられないもの

次を含む差分の CI apply は**権限不足で失敗する**。手元（bootstrap）で apply する。

- WIF pool / provider / attribute mapping
- CI principal 自身の IAM（tfstate bucket や各 project の `setIamPolicy`）
- project 全体の IAM 管理ロール（`owner` / `iam.securityAdmin` / `resourcemanager.projectIamAdmin`）
- `environments/devgist-tf`（state 基盤）
- `environments/devgist-github`（GitHub Environment / repository variable / Ruleset）

## plan と apply の一致

- plan job: `terraform plan -no-color -input=false -lock=false -out=tfplan` → `terraform show` を Actions Summary に出す
- `tfplan` は artifact で apply job に渡す。`retention-days: 1`
- apply job: 同じ commit・同じ lock file で `terraform init` し、`terraform apply -input=false tfplan`
- **bare `terraform apply` は使わない**
- PR で作った plan artifact を merge 後の apply に流用しない
- root ごとに plan → apply を組にし、`data-dev` → `ops` → `app-dev` の順に `needs:` で直列化する
  （後段 root の plan が前段の新しい output を remote state 経由で読むため）
- concurrency は workflow 単位で `cancel-in-progress: false`

## GitHub 側の設定は Terraform が正本

**Terraform が正本の値を workflow YAML や GitHub UI に再掲しない。**

`environments/devgist-github` root が **ローカル apply** で書く（[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md)）。
値は `devgist-ops` の `terraform_remote_state` から読む。認証はローカルの `GITHUB_TOKEN`。GitHub App は使わない。

| repository variable | 中身 |
|---|---|
| `GCP_GITHUB_WIF_PROVIDER` | GitHub WIF provider の resource name |
| `CRAWLER_REPO_URL` | crawler Artifact Registry の Docker URL |
| `CRAWLER_IMAGE_NAME` | crawler Artifact Registry の repository id |

Environment 変数ではなく **repository variable** にするのは、Artifact Registry を prod / dev で 1 本にしており（[INFRA-ADR-007](../adr/infra/007-artifact-registry-and-sa-strategy.md)）、Environment 変数だとその Environment を使う job からしか読めないためです。

GitHub Environment `dev` も同じ root が作る。protection rule は付けない。
Environment は GitHub 側の履歴・承認のための器であって、**GCP IAM のキーではない**。

> [INFRA-ADR-017](../adr/infra/017-github-actions-terraform-managed-variables.md) はこれらを `devgist-ops` root に置いていました。置き場だけ 019 が `environments/devgist-github` に変えています。「Terraform が正本の値を GitHub にベタ書きしない」原則は 017 のまま有効です。

## Artifact Registry

- リポジトリは**アプリケーション単位で 1 本**。dev / prod で共用する（[INFRA-ADR-007](../adr/infra/007-artifact-registry-and-sa-strategy.md)）
- `latest` タグは使わない。Cloud Run Job は **digest 参照が必須**（[INFRA-ADR-010](../adr/infra/010-cloud-run-job-management.md)）
- image tag は `GITHUB_SHA`。可読性と追跡性のためだけに使う
- vulnerability scanning は **明示的に `DISABLED`**。`INHERITED` にしない（[INFRA-ADR-018](../adr/infra/018-artifact-registry-cost-controls.md)）
- cleanup policy: 直近 **5 世代を KEEP**、**30 日超を DELETE**（KEEP が勝つ）。`cleanup_policy_dry_run = false`
- 実装は `modules/artifact_registry`。このモジュール経由の全 Docker repository に適用される

30 日を超え、かつ直近 5 世代に入らない digest は消える。長期間 apply していない Cloud Run Job の旧 digest は pull できなくなる。

## crawler image の更新は 2 PR

```
① crawler-deploy.yaml (main への push)
   → build → Artifact Registry へ push
   → create-digest-pr job が GITHUB_TOKEN で digest 置換 PR を作る
② 人が Approve workflows → CI 通過 → merge
   → terraform-apply.yml が app-dev を apply → Cloud Run Job が新 image に切り替わる
```

- 置換対象: `infra/terraform/environments/devgist-app/dev/terraform.tfvars` の `crawler_image`
- ブランチは `ci/crawler-image-digest` 固定。毎回 `origin/main` から作り直す。auto-merge しない
- `create-digest-pr` job が持つのは `contents: write` と `pull-requests: write` だけ。`id-token` も `environment` も付けない
- 実作業は `.github/scripts/open-crawler-image-digest-pr.sh`
- digest PR の CI は `GITHUB_TOKEN` 起因のため、人が "Approve workflows to run" を押す必要がある

根拠: [INFRA-ADR-021](../adr/infra/021-crawler-image-digest-pr.md)

## secret の扱い

根拠: [INFRA-ADR-020](../adr/infra/020-terraform-cicd-secret-management.md)

### 前提

- 長寿命の credential（SA JSON キー、GitHub App の PEM、PAT）を GitHub Actions に置かない
- GitHub Repository Secret と `TF_VAR_*` は使わない
- trust boundary は protected `main` と、same-repo PR を作れる主体を本人に限ること
  - fork PR に secret は渡らないが、**same-repo PR は runner から権限を使える**
  - 「PR コードが使える最大権限 = plan WIF に与えた権限」。だから plan は read-only に保つ
- plan 結果は Actions の job log に出る。識別子は見えるが secret は含めない

### `sensitive = true` は解決策ではない

**`sensitive` は CLI / UI の表示抑制であって、state や plan からの排除ではありません。**

```
CLI                → redacted
terraform.tfstate  → 値が残る
saved tfplan       → 値が残る可能性がある
```

true secret に対して `sensitive` を第一選択にしないでください。

### true secret が必要になったときの優先順位

上から順に検討し、成立した時点で止める。

| 優先 | 手段 | Terraform が payload を知るか |
|---|---|---|
| 1 | **Resource 自身が Secret Manager を参照する**（Cloud Run の `secret_key_ref` など） | 知らない |
| 2 | **`ephemeral` + write-only argument（`*_wo`）** — Terraform 1.10+ / 1.11+ と provider の対応が要る | operation 中だけ通る。state / plan には残らない |
| 3 | **secret 操作だけ Terraform 管理外にする** — Terraform は resource 本体を管理し、値の投入は gcloud / script | 一度も扱わない |
| 4 | **`sensitive` + state / plan を secret 扱い**（最後の手段） | 知る。state と saved plan に残る |

4 を選ぶ場合は、private backend・strict IAM・暗号化・audit log・saved plan の短期 retention を適用し、
public repository の artifact や PR comment に raw な saved plan を出さないこと。

`ephemeral` は state / plan への永続化を防ぐ仕組みであって、**runner から secret を隠す仕組みではありません。**
原則として plan WIF に Secret Manager access を付けず、trusted な `main` に必要な分だけ付けます。

### 分類

| 区分 | 例 | 置き場 |
|---|---|---|
| 通常の設定値 | project ID、region、SA email、OIDC subject、resource 名、principal identifier | version 管理された `terraform.tfvars` |
| true secret | API key、password、OAuth client secret、private key、access token、refresh token | 上の decision tree を必ず通す |

`cursor_oidc_subjects` / `service_account_user_emails` は **principal identifier であって true secret ではありません**。
値を知っても OIDC token の偽造も IAM principal としての認証もできないため、通常の tfvars に置きます。

### 環境ごとの承認

| 環境 | apply |
|---|---|
| dev | protected `main` → final plan → 自動 apply。manual approval は要求しない |
| prod | 手動起動 → final plan 確認 → **GitHub Environment approval** → `terraform apply tfplan` |

## 再検討の条件

- prod を足すとき → `terraform-apply-prod.yml` を作り、`terraform-apply-prod` の principalSet に IAM を付ける。Environment `prod` は required reviewers 付きで `devgist-github` root に足す
- collaborator を増やすとき → same-repo PR から plan の read 権限が使えるため、plan workflow の権限を見直す
- workflow をリネームするとき → `ci_scope` の mapping は `workflow_ref` のパスに依存する。手元 apply が必要
- Terraform root が増えて直列 apply が重くなったとき
- true secret が必要になったとき → [INFRA-ADR-020](../adr/infra/020-terraform-cicd-secret-management.md) の decision tree を適用する
