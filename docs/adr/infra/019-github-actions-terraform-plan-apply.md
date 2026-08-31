# INFRA-ADR-019 GitHub Actions から terraform plan / apply する

## Conclusion (結論)

- GitHub Actions から terraform plan / apply する。WIF は既存の pool `github-devgist` / provider `oidc` を維持する。用途の分離は provider を増やさず、custom attribute `ci_scope`（operation × environment）と IAM の `principalSet` で行う。`attribute.environment` は IAM の主キーから外す。
- plan は same-repo PR で read-only の speculative plan を実行し、結果を PR コメントに出す。apply は protected `main` への push で dev を自動適用する。final plan は `terraform plan -out=tfplan` で保存し、`terraform apply tfplan` で確認した plan と同じ内容を適用する。
- CI apply の対象 root は `devgist-ops` / `devgist-data/dev` / `devgist-app/dev`。`devgist-tf` と、GitHub リソースを管理する新 root `environments/devgist-github` はローカル apply に限定する。GitHub App は導入しない（作成・設定した App と `TF_GITHUB_APP_*` は削除する）。
- apply principal は WIF pool / provider / attribute mapping、CI principal 自身の IAM、tfstate 基盤（`devgist-tf`）、GitHub リソースを変更できない。これらの差分を含む CI apply は権限不足で失敗し、手元 apply（bootstrap）となる。
- prod は環境が未作成のため器だけ用意する。`ci_scope` の mapping には prod 条件を先に入れるが、IAM binding と workflow ファイルは prod 環境作成時に足す。

## Status (ステータス)

Accepted (承認済み) - 2026-08-30

[INFRA-ADR-011](./011-terraform-ci-for-monorepo.md) が後続に送った plan / apply の設計である。[INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md) の認証モデル（GitHub 専用 pool、direct resource access、SA impersonation なし、condition は repository id）は維持する。016 の「IAM は `attribute.environment/dev`」「crawler image は branch を問わず」は本 ADR が置き換える。[INFRA-ADR-017](./017-github-actions-terraform-managed-variables.md) の「GitHub リソースは ops が書く」は、置き場を `environments/devgist-github` root に変える。「Terraform が正本の値は GitHub にベタ書きせず Terraform から書く」原則は維持する。016 / 017 本文は履歴として残す。

## Context (背景・課題)

### 背景

Terraform CI は fmt / validate / test / tflint / trivy までである。`terraform init -backend=false` で、GCP 認証も plan も apply も無い（[INFRA-ADR-011](./011-terraform-ci-for-monorepo.md)）。

GitHub Actions 用 WIF は ops の pool `github-devgist` / provider `oidc` にある。IAM は `principalSet://.../attribute.environment/dev` に crawler Artifact Registry の writer だけが付いている（[INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md)）。GitHub Environment `dev` は OIDC claim 用で、protection は付けない（[INFRA-ADR-017](./017-github-actions-terraform-managed-variables.md)）。

このまま apply 用 write IAM を `attribute.environment/dev` に足すと、同じ Environment を使う全 workflow が write を共有する。`on: pull_request` の YAML は PR head から実行されるので、plan 用 job に `environment: dev` を書けば、緩い provider condition（repository id のみ）を通って write principal を満たせる。

要件は次である。

- PR と `main` の push で plan したい
- apply は protected `main` への push だけ
- plan と apply で principal の権限を分ける
- 既存 WIF を増やすのではなく、principal で切る

Google は GitHub のような multi-tenant IdP では attribute condition で tenant / repository を制限すること、**1 pool につき 1 provider**、**同じ IdP を重複 federation しない**ことを推奨している。用途の分岐は mapping の CEL と IAM で行う。

### GitHub リソースの扱い

ops root の GitHub provider リソース（Environment、repository variable）は、Actions の `GITHUB_TOKEN` では write できない（Environments の作成・更新には GitHub App / PAT の `Administration: write` が要る）。GitHub App を作って CI に載せる案を検討し、App と `TF_GITHUB_APP_*` の secret / variable まで作成したが、次の理由で却下した。

- PR の YAML は PR head から実行される。repo secret の PEM は same-repo PR の workflow から参照可能で、protection なしに credential を CI に置くことになる
- GitHub リソースの変更頻度は低く、自動化のメリットが小さい
- 一方で再現性は欲しいので、Terraform 管理自体は続ける

一般原則として、**CI にするとセキュリティ対処コストが高く、自動化のメリットが低いものはローカルで管理する**。GitHub リソースは新 root `environments/devgist-github` に分離し、plan / apply をローカルに限定する。これにより CI の workflow は GCP 認証だけを持ち、GitHub 側の credential を CI に置く問題自体が消える。

### 要件と制約

1. **長寿命の秘密を GitHub に置かない**
   - JSON キーを repo secret にしない。credential config に SA impersonation を入れない。GitHub App の PEM も置かない
2. **plan と apply の blast radius を分ける**
   - plan principal は read-only。PR の YAML 改ざんが write に届かない
3. **write は protected `main` に限定する**
   - `main` は Ruleset 済み（PR 必須、required checks、up-to-date 必須、force push / delete 禁止）
   - crawler の AR writer も同じ理由で `main` に閉じる
4. **既存の GitHub WIF 入口を維持する**
   - pool / provider / issuer は 016 のまま。Cursor 用 pool には触れない
5. **CI apply の対象は ops / data / app。tf と github は載せない**
   - state bucket を持つ `devgist-tf` と、GitHub リソースを持つ `environments/devgist-github` はローカル apply
6. **CI apply が自分の trust boundary を書き換えられない**
   - WIF pool / provider / attribute mapping、CI principal 自身の IAM、GitHub Ruleset の更新権限を apply principal に付けない
7. **guest IAM の置き場は 015 の表**
8. **静的 CI は GCP 認証なしのまま**
   - 011 の `terraform-ci.yml` は維持する。plan / apply は別 workflow
9. **確認した plan と apply 内容を一致させる**
   - `terraform plan -out=tfplan` → `terraform apply tfplan`。bare `terraform apply` は使わない
10. **PR plan と apply は時間的に一致しない**
    - PR plan は speculative。apply 直前に `main` 上で final plan を再生成する

### 比較した選択肢

#### WIF の分割単位

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: plan / apply で pool または provider を増やす | 認証境界そのものを用途で物理分割したい場合 | 緩い provider が apply 用 Environment を発行できない | 同じ GitHub IdP の dual federation。Google が避ける subject collision / 同一 IdP の重複 | 非採用 |
| Option B: GitHub Environment 名を IAM の主キーにする（現状の延長） | job の `environment:` と IAM を 1:1 にしたい場合 | 016 からの差分が小さい | PR の YAML が Environment 名を選べる。crawler と apply が `dev` を共有し得る | 非採用 |
| Option C: 1 pool / 1 provider のまま `ci_scope` を CEL で合成する | 同じ GitHub IdP を複数 CI 用途に使う場合 | 入口は 1 つ。principal は用途ごと。claim は GitHub 署名で、YAML が `ci_scope` を名乗れない | mapping が CEL としてやや長い。`workflow_ref` は repository 名を含む | 採用 |

#### write を `main` に閉じる場所

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: provider condition に `ref == refs/heads/main` を入れる | その provider 全体を main 専用にしたい場合 | token 交換時点で PR を拒否できる | PR plan が同じ provider を使えない | 非採用 |
| Option B: `ci_scope` の合成条件に workflow / event / ref / environment を入れる | 入口は広く、用途ごとに閉じたい場合 | plan は PR を通せる。apply / crawler は main だけ write | mapping が security-critical。変更は bootstrap | 採用 |

#### CI apply の対象 root

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: data / app のみ。ops は手元 | WIF と CI identity を CI から完全に隔離したい場合 | 自己権限昇格の面が狭い | ops の AR や guest IAM も毎回手元 | 非採用 |
| Option B: ops / data / app を CI。tf は手元 | state 基盤だけ極小に残したい場合 | 日常の apply 対象が揃う。tfstate project は不変に近い | ops 同一 root に WIF がある。apply IAM で mapping 更新を禁止する必要がある | 採用 |
| Option C: 全 root を CI | 手元 apply を無くしたい場合 | 導線が 1 つ | tfstate を CI が作り変えられる。004 の tf 保護と食い違う | 非採用 |

#### ops の GitHub リソース

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: workflow の `GITHUB_TOKEN` で CI apply する | 追加 credential なしで済ませたい場合 | 秘密が増えない | `GITHUB_TOKEN` は Environments を write できない（GitHub App / PAT の `Administration: write` が必要）。必ず失敗する | 非採用 |
| Option B: GitHub App を作り CI apply する | ops を丸ごと CI に載せたい場合 | GitHub リソースも自動化できる | PEM という長寿命の秘密を repo secret に置く。PR YAML から参照できる。GitHub リソースの変更頻度は低く自動化メリットが小さい | 非採用 |
| Option C: `environments/devgist-github` root に分離しローカル apply に限定する | 再現性は Terraform で確保しつつ CI には載せない場合 | CI は GCP 認証だけを持つ。credential を CI に置く問題が消える | GitHub リソースの変更は手元 apply。state 移行（state rm + import）が要る | 採用 |

### 選定観点

- Google の 1 pool / 1 provider と、同一 GitHub IdP を増やさないこと
- PR が apply / crawler の write principal を選べないこと
- plan は PR と `main` の両方で動くこと
- write 系は protected `main` に閉じること
- CI が WIF mapping、CI principal 自身の IAM、tfstate 基盤、GitHub リソースを更新できないこと
- CI 化のセキュリティコストが自動化メリットを上回るものはローカルで管理すること

## Considered Options

### Option A: plan / apply で WIF を増やす [却下]

pool または provider を plan 用と apply 用に分ける方式。

却下理由:

- 同じ issuer `https://token.actions.githubusercontent.com` を二重に federation する
- Google は 1 pool 1 provider、同じ IdP の重複を避ける
- 016 の「この repo の GitHub Actions 入口は 1 pool」を崩す
- 分離は IAM で足りる。足りないのは Environment 名を主キーにしたことである

### Option B: GitHub Environment を GCP principal の主キーにする [却下]

`dev-plan` / `dev-apply` を作り、`attribute.environment` に IAM を付ける方式。

却下理由:

- `environment` claim の値は job の `environment:` そのもので、`pull_request` の YAML が選べる
- 既存 provider の condition は repository id だけなので、PR でも token 交換に成功する
- crawler-deploy が `environment: dev` のままだと、apply を同じ principal に足した瞬間に image push job が tfstate / Cloud Run まで持つ

GitHub Environment 自体は残してよい。使うのは protection / 履歴と、apply 系 `ci_scope` の合成条件の一部であり、GCP IAM のキーではない。

### Option C: `ci_scope` を CEL で合成し、IAM は principalSet で分ける [採用]

provider の attribute mapping で、GitHub が署名した `workflow_ref` / `event_name` / `ref` / `environment` から `attribute.ci_scope` を作る。IAM は `principalSet://.../attribute.ci_scope/<value>` に付ける。

採用理由:

- `ci_scope` は YAML の文字列ではなく、実行コンテキストから導出される
- PR の `workflow_ref` は `.../terraform-plan.yml@refs/pull/N/merge` であり、apply 条件の `@refs/heads/main` かつ `event_name == push` を満たさない
- apply の条件に `environment == "dev"` を含める。prod では `environment: prod` に required reviewers を付けることで、**approval 通過後にしか `environment=prod` の JWT が発行されず**、GitHub の承認ゲートと GCP identity が結合する
- crawler の writer も `crawler-deploy.yaml@refs/heads/main` に閉じる。feature branch の push では `ci_scope=none` になり、condition で token 交換に失敗する
- 既存の `google-github-actions/auth` は provider 名を変えない。workflow は `ci_scope` を渡さない

### Option D: GitHub App で ops の GitHub リソースまで CI apply する [却下]

GitHub App を作成し、`TF_GITHUB_APP_ID` / `TF_GITHUB_APP_INSTALLATION_ID` / `TF_GITHUB_APP_PEM_FILE` を repository secret / variable に設定して、CI から GitHub provider を App 認証で動かす方式。

却下理由:

- PEM は長寿命の秘密であり、「長寿命の秘密を GitHub に置かない」の要件と緊張する
- repo secret は same-repo PR の workflow YAML から参照できる。plan を PR に載せる以上、Credential の露出面が増える
- GitHub リソース（Environment、repository variable）は変更頻度が低く、自動化のメリットが小さい
- セキュリティ対処コストが自動化メリットを上回るものはローカル管理にする一般原則に従う

作成済みの GitHub App と `TF_GITHUB_APP_*` は削除する。GitHub リソースは `environments/devgist-github` root に移し、ローカルから個人の `GITHUB_TOKEN` で apply する（017 の手元運用を維持）。

## Decision (決定事項)

GitHub Actions の terraform plan / apply と crawler image push は、既存の GitHub WIF 1 組を入口にし、`attribute.ci_scope` ごとの principalSet で認可する。

### 採用方針

#### WIF

- pool `github-devgist` / provider `oidc` / issuer `https://token.actions.githubusercontent.com` は維持する
- `attribute.environment = assertion.environment` は外す。GitHub Environment の無い job でも、`ci_scope` が付くなら federate できる。job に Environment を付けて protection や履歴に使うのは自由だが、GCP は Environment 単体では認可しない
- `google.subject` は `assertion.sub` のまま（監査の一意性）
- `repository_id` / `repository_owner_id` の mapping は維持する。`workflow_ref` / `ref` / `event_name` / `environment` は合成の材料であり、IAM のキーにはしない
- `attribute.ci_scope` は CEL の三項演算子で決める。値は URL に載るので `terraform-plan-dev` のような短い token にする。`workflow_ref` 全体を値にしない
- `environment` は optional claim なので、CEL では `has(assertion.environment)` で guard する

#### Provider condition

認証境界は repository の immutable id と、既知の用途だけ通すことの AND である。

```hcl
attribute_condition = <<-EOT
  assertion.repository_id == "1106323394" &&
  assertion.repository_owner_id == "31652298" &&
  attribute.ci_scope != "none"
EOT
```

`ref` や workflow を共通 condition に入れない。入れると PR plan が死ぬ。

#### `ci_scope` の合成

`workflow_ref` は `OWNER/REPO/.github/workflows/FILE@REF` であり repository **名** を含む。condition が `repository_id` で repo を固定しているので、パス側は JWT の `assertion.repository` を結合し、repo 名を Terraform にベタ書きしない。rename すると `repository` と `workflow_ref` が同じ JWT で一緒に変わる。id は condition のまま。

初期の対応は次である。ファイル名は workflow のパスそのものである。

| `ci_scope` | 条件（概念） | IAM |
|---|---|---|
| `terraform-apply-dev` | `workflow_ref == assertion.repository + "/.github/workflows/terraform-apply.yml@refs/heads/main"` かつ `ref == "refs/heads/main"` かつ (`event_name == "push"` または `workflow_dispatch`) かつ `environment == "dev"` | ops / data-dev / app-dev の必要な write、対象 tfstate の read/write |
| `terraform-plan-dev` | 同上の workflow / ref / event で environment 無し。または `event_name == "pull_request"` かつ `workflow_ref` が `assertion.repository + "/.github/workflows/terraform-plan.yml@refs/pull/"` で始まる | deploy 対象 root と tf 自身の tfstate の read、ops / data-dev / app-dev / tf の get/list と IAM policy の read。create / update / delete と IAM 変更と WIF 変更は付けない |
| `terraform-apply-prod` | `terraform-apply-prod.yml` かつ `event_name == "workflow_dispatch"` かつ `ref == "refs/heads/main"` かつ `environment == "prod"` | prod 環境作成時に付ける。今は付けない |
| `terraform-plan-prod` | `terraform-apply-prod.yml` かつ `workflow_dispatch` かつ `main` で environment 無し | 同上 |
| `crawler-push-dev` | `event_name == "push"` かつ `ref == "refs/heads/main"` かつ `workflow_ref == assertion.repository + "/.github/workflows/crawler-deploy.yaml@refs/heads/main"` | crawler Artifact Registry の `roles/artifactregistry.writer` のみ |
| `none` | 上記以外 | どの principalSet にも付けない。condition が token 交換を拒否する |

合成は apply → plan → crawler → `none` の順で評価する。`contains("terraform-apply.yml")` のような部分一致は使わない。

prod の plan / apply を別 workflow ファイル（`terraform-apply-prod.yml`）にするのは、`workflow_dispatch` の input は JWT claim に載らず、同じファイルでは prod 用 plan job（environment 無し）と dev 用 plan job を `ci_scope` で区別できないからである。prod の Environment 承認は apply job にだけ付け、plan job は承認なしで先に走らせて plan を確認できるようにする。

fork の `pull_request` は GitHub が OIDC token を発行しない（fork では `id-token: write` が効かず `ACTIONS_ID_TOKEN_REQUEST_URL` が出ない）。DevGist は same-repo PR author を owner に限定する（[INFRA-ADR-020](./020-terraform-cicd-secret-management.md)）ため、workflow に追加の head repo ガードは置かない。

#### `attribute.environment` を外すこと

懸念は次に限る。いずれも `ci_scope` 側で吸収する。

- 移行中に mapping だけ先に変えると、旧 `attribute.environment/dev` に誰も当たらず crawler が落ちる。新 IAM の追加と mapping 切替と旧 binding 削除は **同一の手元 ops apply** にする
- GCP は GitHub Environment の使用を強制しなくなる。protection が要るなら GitHub 側に付ける。write の可否は `ci_scope` が決める
- job が `environment:` を付け続けるなら JWT の `sub` は従来どおり `environment:` を含む。mapping から外すだけで、claim 自体は消えない

#### Workflow

静的検証は `.github/workflows/terraform-ci.yml` のまま。GCP 認証を足さない。

- `.github/workflows/terraform-plan.yml` — `pull_request` のみ。`ci_scope=terraform-plan-dev`。`terraform plan -lock=false`（state に lock 用 write を持たせない）。結果は PR コメントに upsert する。`devgist-tf` と `environments/devgist-github` は対象外
- `.github/workflows/terraform-apply.yml` — `push` の `main` と `workflow_dispatch`（input `target` は `dev` のみ。prod は環境作成時に専用 workflow `terraform-apply-prod.yml` を足す）。root ごとに plan job（environment 無し → `terraform-plan-dev`）→ apply job（`environment: dev` → `terraform-apply-dev`）を組みにし、`data-dev` → `ops` → `app-dev` の順に `needs:` で直列にする
- apply の「CI が pass したら」は Ruleset の required checks で担保する。merge できない commit は `main` に乗らず、apply も走らない。up-to-date 必須も設定済みなので、main に乗る内容は必ず CI 通過済みの組み合わせである
- crawler-deploy の trigger を `main` に合わせる。feature branch では job を走らせない（走っても `ci_scope=none` で失敗する）

apply 順は 015 の DAG に合わせる。plan → apply を root ごとに interleave するのは、後段 root の plan が前段 root の新しい output を remote state 経由で読むためである。先に全 root を plan してから apply すると、後段の saved plan が stale になる。

#### final plan と apply の一致

- plan job は `terraform plan -no-color -input=false -lock=false -out=tfplan` を実行し、`terraform show -no-color tfplan` を Actions Summary に出す
- `tfplan` は artifact として plan job から apply job へ受け渡す。`retention-days: 1`。public repo でも artifact の download は GitHub login 必須だが、planned values / variables を含み得るので sensitive artifact として扱う
- apply job は同じ commit を checkout し、同じ Terraform / provider version（lock file）で `terraform init` した上で `terraform apply -input=false tfplan` を実行する。bare `terraform apply` は使わない
- PR で生成した plan artifact を merge 後の apply に流用しない
- saved plan の apply 中に state が変わっていれば Terraform が "Saved plan is stale" で失敗する。concurrency は workflow 単位で `cancel-in-progress: false` とし、apply の並行実行と中断を防ぐ

#### CI apply の対象と、CI が書き換えられないもの

| root | plan | apply |
|---|---|---|
| `devgist-data/dev` | CI | CI |
| `devgist-ops` | CI | CI（下記の例外あり） |
| `devgist-app/dev` | CI | CI |
| `devgist-tf` | しない | ローカル |
| `environments/devgist-github` | しない | ローカル |

ops は CI に載せる。ただし **apply principal に次を付けない**。

- WIF pool / provider の更新（`iam.workloadIdentityPools.update` 相当。`workloadIdentityPoolViewer` 相当の read は付ける）
- project 全体の IAM 管理（`roles/owner`、`roles/iam.securityAdmin`、`roles/resourcemanager.projectIamAdmin`）
- CI principal 自身の IAM 変更（tfstate bucket の `setIamPolicy`、data-dev / ops / app-dev project の `setIamPolicy` は付けない）
- GitHub Ruleset / Environment / repository variable の変更（CI は GitHub 向け credential を持たない）

これらが差分に含まれる CI apply は権限不足で失敗する。その変更は手元（bootstrap）である。mapping が security-critical であるという Google の推奨に合わせる。CI apply の権限で完結する差分だけが CI で通る、という境界にする。

#### `environments/devgist-github` root

- GitHub provider のリソース（`github_repository_environment`、`github_actions_variable`）をこの root が書く。値は ops の `terraform_remote_state` から読む（006）
- state bucket は `haru256-devgist-github-tfstate`。`devgist-tf` の `tfstate_gcp_project_ids` に `haru256-devgist-github` を足して tf を apply してから使う
- 認証はローカルの `GITHUB_TOKEN`（017 の手元運用）。GitHub App は使わない
- 移行は ops で `terraform state rm` してから `devgist-github` root で `terraform import` する
- この root は `providers.tf` を持つため静的 CI（fmt / validate / tflint / test）の対象にはなるが、plan / apply の対象からは除外する

#### IAM の置き場（015）

| identity | resource | 書く root |
|---|---|---|
| GitHub `ci_scope`（ops の WIF） | tfstate buckets（tf project） | ops |
| 同上 | tf project の project ロール | ops |
| 同上 | data-dev のリソース・project ロール | ops |
| 同上 | ops 同一 root の AR など | ops |
| 同上 | app-dev の project ロール・crawler SA の actAs | app-dev |

ロールは resource-level を優先し、だめなら project の predefined、その次に custom role である。`roles/editor` は付けない。

resource の IAM policy の read（`getIamPolicy`）は、predefined の read-only role では bucket / AR repository 分を賄えない（`roles/viewer` は project の `getIamPolicy` 系を含むが、`storage.buckets.getIamPolicy` や `artifactregistry.repositories.getIamPolicy` は含まない）。plan が `_*_iam_member` を refresh するにはこれらが要るので、次の custom role を各 resource 側の root で定義する。

| custom role | 定義する root | permissions | 付与先 |
|---|---|---|---|
| `tfstateReader` | `devgist-tf` | `storage.buckets.get` / `storage.buckets.getIamPolicy` / `storage.objects.get` / `storage.objects.list` | deploy 対象 root と tf 自身の tfstate bucket × plan-dev / apply-dev（`devgist-github` の state は secret の plaintext を含むので CI から読ませない） |
| `datalakeIamReader` | `devgist-data/dev` | `storage.buckets.get` / `storage.buckets.getIamPolicy` | datalake bucket × plan-dev |
| `arRepoIamReader` | `devgist-ops` | `artifactregistry.repositories.get` / `artifactregistry.repositories.getIamPolicy` | crawler AR repository × plan-dev |

custom role の定義変更は CI apply では通らない（apply principal に `iam.roles.update` を付けない）。定義の作成・変更は bootstrap である。

plan は上記 read に加えて各 project の `roles/viewer` と `roles/iam.securityReviewer`（project の `getIamPolicy` と SA / custom role / WIF pool の read）。apply は対象 deploy bucket の `roles/storage.objectUser` と、app-dev / data-dev / ops の必要な mutation（`run.admin`、`storage.admin`、`artifactregistry.admin`、`iam.serviceAccountAdmin`、`serviceusage.serviceUsageAdmin` など）に、crawler SA への `roles/iam.serviceAccountUser` を足す。crawler-push は AR writer だけである。

#### tfvars

gitignore の `*.tfvars` のままだと CI は plan も apply もできない。空の値で ops を apply すると `cursor_oidc_subjects` が空になり、Cursor の GCS IAM が消える。

- 非 secret（`gcp_project_id`、region、`crawler_image` digest、conference 名など）は `environments/**/terraform.tfvars` に限り version 管理する。gitignore にそのパスの例外を置く。それ以外の `*.tfvars` は引き続き ignore する
- 人が特定される値（`cursor_oidc_subjects`、`service_account_user_emails`）は true secret ではなく principal identifier である。値を知っても OIDC token の偽造や IAM principal としての認証はできない。通常の設定値として `environments/**/terraform.tfvars` に version 管理する（[INFRA-ADR-020](./020-terraform-cicd-secret-management.md)）。GitHub Repository Secret や `TF_VAR_*` は使わない
- これらの variable は `default = []` を持つ。空なら grant が付かないだけで、plan / apply は失敗しない
- `crawler_image` は variable を維持し、値は committed tfvars に置く。image の更新は「build（crawler-deploy が main で push）→ digest を tfvars に書き換える infra PR → merge で apply」の 2 PR 運用とする。digest を書き換える PR の自動作成 CI は別タスク（issue #60 の後続）とする

### 初期構成

```
GitHub OIDC
    │
    ▼
github-devgist / oidc
    │  condition: repository_id + owner_id + ci_scope != "none"
    │  mapping: ci_scope を workflow_ref + event_name + ref + environment から合成
    │           attribute.environment は置かない
    │
    ├─ terraform-plan.yml
    │    PR (same-repo)
    │    → terraform-plan-dev → state/GCP READ → PR コメント
    │
    ├─ terraform-apply.yml
    │    push main / workflow_dispatch(target=dev)
    │    → plan job (terraform-plan-dev) → artifact → apply job (environment: dev, terraform-apply-dev)
    │    → data-dev → ops → app-dev の直列
    │
    └─ crawler-deploy.yaml
         push main のみ
         → crawler-push-dev → AR writer

ローカル / bootstrap
├─ devgist-tf（tfstate bucket、tfstateReader custom role）
├─ environments/devgist-github（GitHub Environment / repository variable）
├─ WIF mapping と pool/provider の変更
└─ CI principal の IAM grant の作成・変更
```

### 再検討条件

- federated identity 非対応 API が出て、その API だけ SA impersonation に寄せる場合
- prod を足すとき。`terraform-apply-prod.yml` を作り、prod の principalSet に IAM を付ける。GitHub Environment `prod`（required reviewers 付き）は `environments/devgist-github` root に足す。個人開発なので deployment 開始者本人が承認する前提で `Prevent self-review` は付けない
- リポジトリ rename。`repository_id` は不変。`workflow_ref` は `assertion.repository` 結合なので通常は追従する。claim の形が変わったときだけ mapping を直す
- collaborator を増やすとき。same-repo PR から repository variable と plan の read 権限が参照できるため、plan workflow の権限を見直す
- Terraform root 数が増え、全 root の直列 apply が重い場合
- tfvars に secret 値が入る見込みが出た場合。tfplan artifact の中身も見直す

## Consequences (結果・影響)

### Positive (メリット)

- WIF 入口は 1 つのまま、plan / apply / crawler の IAM が分かれる
- PR が Environment 名を書いても apply principal を満たせない
- write は protected `main` に閉じる。crawler の AR writer も同じ
- 011 の静的 CI は GCP なしのまま
- tfstate project と GitHub リソースを CI の日常変更から外せる
- CI は GCP 向け credential だけを持ち、GitHub 向けの長寿命の秘密を CI に置かない
- 確認した saved plan と apply 内容が一致する

### Negative (デメリット)

- same-repo PR の `.tf` は plan principal の read で実行される。state や resource 識別子の読み出し、`local-exec` は残る
- `terraform-apply.yml` が `main` に入ったあとの中身は、WIF から見ると正当な apply である。中身のレビューは Ruleset 頼み
- mapping 変更、CI principal の IAM 変更、GitHub リソース、`devgist-tf` は手元が残る
- crawler は feature branch から image を push できない（016 からの行動変）
- `workflow_ref` はファイルパスに結合する。workflow のリネームは mapping の更新（手元 apply）が要る
- GitHub リソースの root 分離で state 移行（state rm + import）が一度だけ要る

### Risks / Future Review (将来の課題)

- apply principal が project IAM admin を後から付与されると、自分で WIF を緩められる。ロール追加の PR を見る
- plan 結果を public の PR コメントに出す。識別子は公開されるが secret は含めない。Actions log も login 済みユーザーには見えるので、秘匿性はコメントでも log でも変わらない
- tfplan artifact は login 必須だが sensitive 扱いとし、`retention-days: 1` にする。tfvars に secret が入る見込みが出たら再検討する
- 直列 apply の途中失敗で data だけ新しい、があり得る。再実行で揃える
- IAM ロールの初期セットは実際の CI plan / apply で不足が出たら権限エラーのメッセージに従って足す。初回の CI 実行で調整する
- GitHub App を再導入したくなった場合は、本 ADR の Option D の却下理由を再評価する

## Next Steps

1. `devgist-tf` の `tfstate_gcp_project_ids` に `haru256-devgist-github` を足し、`tfstateReader` custom role と `tf_project_id` output を追加して、ローカルで tf を apply する
2. `environments/devgist-github` root を作り、ops から GitHub リソースを移す（ops で `terraform state rm` → `devgist-github` root で `terraform import`）。ローカルで `devgist-github` root を apply する
3. ops の GitHub WIF mapping に `ci_scope` を足し、condition に `ci_scope != "none"` を足し、`attribute.environment` を外す。新 principalSet の IAM を足してから、同一の手元 apply で旧 `attribute.environment/dev` を外す
4. plan / apply principal の guest IAM を 015 の表どおり ops と app-dev に書く。tfstate bucket の IAM も含める。data-dev に `datalakeIamReader`、ops に `arRepoIamReader` を定義する。ローカルで data → ops → app の順に apply する
5. 非 secret tfvars の commit 例外を入れる。作成済みの GitHub App と `TF_GITHUB_APP_*` を削除する
6. `terraform-plan.yml` と `terraform-apply.yml` を追加する。crawler-deploy の trigger を `main` にする
7. ops の tftest を `ci_scope` に更新する。plan / apply 対象 root の検出には 011 の root 検出に除外フィルタを足したものを使う
8. merge 後、初回の CI plan / apply が通ることを確認し、権限不足があればロールを足す（手元 apply を挟む）

## Related Documents

- [[INFRA-ADR-004] Terraform State Project と Ops Project を分離する](./004-separate-tf-and-ops-projects.md)
- [[INFRA-ADR-006] Cross-project Terraform output 共有戦略](./006-cross-project-output-sharing.md)
- [[INFRA-ADR-010] Cloud Run Job の管理責務を Terraform に集約する](./010-cloud-run-job-management.md)
- [[INFRA-ADR-011] Terraform monorepo における CI 対象検出と検証方針](./011-terraform-ci-for-monorepo.md)
- [[INFRA-ADR-015] data は箱とし、guest IAM は依存の下流が書く](./015-guest-iam-downstream.md)
- [[INFRA-ADR-016] GitHub Actions から crawler image を Artifact Registry へ push する](./016-github-actions-wif-and-crawler-image-push.md)
- [[INFRA-ADR-017] GitHub Actions の Terraform 由来設定は ops が repository variable として書く](./017-github-actions-terraform-managed-variables.md)（置き場は本 ADR が `environments/devgist-github` に変える）
- [[INFRA-ADR-020] Terraform CI/CD と Secret Management 方針](./020-terraform-cicd-secret-management.md)
- [Terraform CI](../../../.github/workflows/terraform-ci.yml)
- [Crawler Deploy workflow](../../../.github/workflows/crawler-deploy.yaml)
- [Infrastructure README](../../../infra/README.md)
- [issue #60](https://github.com/haru-256/devgist/issues/60)
- [Best practices for using Workload Identity Federation](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation)
- [Workload Identity Federation（attribute mapping / principalSet）](https://docs.cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc)
- [Permissions in a forked repository](https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs#changing-the-permissions-in-a-forked-repository)
