# INFRA-ADR-020 Terraform CI/CD と Secret Management 方針

## Conclusion (結論)

- GCP infrastructure は GitHub Actions から terraform plan / apply する。PR は read-only WIF、protected `main` は write WIF。dev は自動 apply、prod は final plan 確認後に manual approval を挟む。
- Provider credential は長寿命 secret として GitHub Actions に置かない。GCP は OIDC + WIF。WIF が難しく変更頻度も低い control-plane（GitHub リソース）は Terraform 管理を維持しつつローカル apply にする。
- true secret（API key、password、private key など）は Terraform に payload を渡さない設計を優先する。`sensitive` は表示抑制であり、state / plan からの排除ではない。
- `cursor_oidc_subjects` / `service_account_user_emails` は true secret ではなく principal identifier なので、通常の `terraform.tfvars` に version 管理する。

## Status (ステータス)

Accepted (承認済み) - 2026-08-31

[INFRA-ADR-019](./019-github-actions-terraform-plan-apply.md) が terraform plan / apply の CI 化を決めた。本 ADR はその前提となる trust boundary と、Terraform が扱う値の secret 管理方針を定める。019 の実装詳細（`ci_scope` の CEL、workflow 構成、IAM の置き場）は 019 を参照する。

## Context (背景・課題)

### 背景

DevGist の Terraform 運用では、次を同時に実現する。

- 通常の GCP infrastructure は GitHub Actions から Terraform を実行する
- CI credential を長寿命 secret として GitHub Actions に保存しない
- true secret が将来必要になっても、PR comment / Actions log / step summary / state / saved plan に不用意に残さない

### DevGist の threat model

DevGist は個人開発であり、same-repository branch から PR を作成できる主体を本人に限定する。`main` は protected branch である。

そのため threat model は「任意の第三者 collaborator による malicious same-repo PR」を通常運用では想定しない。この前提では、

```text
PR → read-only WIF
protected main → write WIF
```

という構成は合理的である。ただし「PR code が利用可能な最大権限 = terraform-plan WIF に与えた権限」であることは変わらない。plan identity は引き続き read-only / least privilege とする。

### Fork PR と same-repo PR は性質が異なる

GitHub は fork repository からの `pull_request` には原則 repository secrets を渡さない。一方、same-repository branch からの PR は、workflow に secret や権限が与えられていれば runner から利用できる。

一般論としては untrusted code と privileged credential を同じ runner に置くべきではない。DevGist では same-repo PR author を本人に限定することでこのリスクを明示的に受容する。ただし true secret を PR に渡す必要がないのであれば、依然として渡さないことを基本とする。

### WIF と Secret Management は別問題

WIF は「誰が何の権限を取得できるか」を安全に管理する仕組みである。一方、Terraform の secret 問題は「Terraform が扱った値がどこに永続化・表示されるか」という別問題である。

WIF で安全に GCP credential を取得できても、`variable "password" { sensitive = true }` として password を通常の resource argument に渡せば、その password は state や saved plan に残る可能性がある。したがって、

```text
Authentication / Authorization → WIF
Secret persistence             → Terraform secret management
```

として別々に設計する。

### `sensitive` は暗号化・非保存ではない

Terraform の `sensitive = true` は主に CLI / UI での表示を抑制する機能である。通常の sensitive value は、

```text
CLI          → redacted
terraform.tfstate → 値が残る
saved tfplan      → 値が残る可能性がある
```

ため、true secret を state / plan から排除したい場合の根本解決にはならない。Terraform 1.10+ の `ephemeral`、Terraform 1.11+ の write-only argument を利用できるかを判断する。

### 現在の principal 情報は true secret ではない

現在 DevGist で利用している `cursor_oidc_subjects` / `service_account_user_emails` は認証 credential ではなく principal identifier / authorization metadata である。値を知っただけで OIDC token を偽造したり IAM principal として認証したりすることはできない。

public repository に置いて問題ない情報であれば、Repository Secret にする必要はなく、通常の version-controlled `terraform.tfvars` として管理する。これにより GitHub Repository Secret、`TF_VAR_*`、structured secret masking という不要な複雑性を削除する。

### 要件と制約

1. **長寿命の秘密を GitHub Actions に置かない**
   - GCP は OIDC + WIF。Service Account JSON キーは作らない
2. **plan と apply の blast radius を分ける**
   - plan principal は read-only。PR の YAML 改ざんが write に届かない
3. **write は protected `main` に限定する**
4. **true secret は Terraform に payload を渡さない設計を優先する**
5. **WIF が難しく変更頻度も低い control-plane はローカル apply**
   - GitHub リソースは Terraform 管理を維持しつつ `devgist-github` でローカル apply
6. **principal identifier は secret にしない**
   - `cursor_oidc_subjects` / `service_account_user_emails` は `terraform.tfvars` に version 管理する

### 比較した選択肢

#### true secret の渡し方

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Resource が Secret Manager を参照する | Cloud Run などが secret name / version だけを知る場合 | Terraform が payload を知らない。state / plan に残らない | resource が対応している必要がある | 最優先 |
| ephemeral + write-only argument | Provider が `*_wo` を提供する場合 | state / plan に残らない | Terraform 1.10+ / 1.11+ と provider の対応が要る | 次点 |
| secret 操作だけ Terraform 外 | 低頻度の control-plane 操作 | Terraform が payloadを一度も扱わない | 手動または別スクリプトが要る | 次点 |
| sensitive + protected state / plan | どうしても Terraform 管理する場合 | Terraform で完結する | state / plan に残る。artifact を secret 扱いする運用が要る | 最後の手段 |

#### principal identifier の置き場

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Repository Secret + `TF_VAR_*` | 値を隠したい場合 | GitHub UI で値が見えない | structured secret の masking が弱い。CI に secret を渡す複雑さが残る | 非採用 |
| gitignore 済み `secrets.auto.tfvars` | ローカルだけ値を持つ場合 | commit されない | CI に値を渡す経路が別途要る | 非採用 |
| 通常の `terraform.tfvars` | 値が public で問題ない場合 | CI / ローカルで同じファイルを読む。余計な経路が無い | 値が repository に残る | 採用 |

### 選定観点

- Terraform が secret payload を知る必要があるかを最初に判断する
- `sensitive` を第一選択にしない
- principal identifier と true secret を分ける
- CI 化のセキュリティコストが自動化メリットを上回るものはローカルで管理する

## Considered Options

### Option A: すべての Terraform を CI に載せる [却下]

GitHub リソースも含めて全 root を CI apply する方式。

却下理由:

- GitHub Provider の write には GitHub App / PAT の長寿命 credential が要る
- GitHub リソースの変更頻度は低く、自動化のメリットが小さい
- セキュリティ対処コストが自動化メリットを上回る

### Option B: true secret を GitHub Repository Secret に入れて `TF_VAR_*` で渡す [却下]

API key などを repository secret に入れ、CI の `TF_VAR_*` 経由で Terraform に渡す方式。

却下理由:

- Terraform が payload を知る以上、state / saved plan に残る可能性がある
- structured secret（JSON list など）は GitHub の masking が完全一致ベースで弱い
- 「Terraform が secret payload を知る必要があるか」を先に問うべきで、secret を渡すのは最後の手段

### Option C: Resource が Secret Manager を参照し、Terraform は secret name / version だけを知る [採用]

Cloud Run などが Secret Manager の secret を直接参照する方式。

採用理由:

- Terraform は secret payload を知らない
- PR plan / main plan / apply のいずれも secret を必要としない
- state / saved plan に payload が残らない

### Option D: ephemeral + write-only argument [採用]

Provider が `*_wo` を提供する場合に、ephemeral resource から secret を読み、write-only argument に渡す方式。

採用理由:

- secret は Terraform の memory を operation 中だけ通り、state / plan に残らない
- `*_wo_version` のような非 secret version number で rotation を Terraform に認識させられる

## Decision (決定事項)

### Terraform CI/CD の基本構成

- **Pull Request**: same-repo PR check → read-only terraform-plan WIF → `terraform plan` → PR review。plan WIF には tfstate read、GCP resource get/list、IAM policy read のみを与える。create / update / delete は持たせない
- **dev**: protected `main` → final `terraform plan -out=tfplan` → plan 確認 → `terraform apply tfplan`。manual approval は要求しない
- **prod**: manual deployment 開始 → final plan → plan 確認 → GitHub Environment approval → `terraform apply tfplan`

### Provider authentication

- **GCP**: GitHub Actions → OIDC → GCP WIF → Google Provider。長寿命 Service Account key は作らない
- **GitHub**: 変更頻度が低いため `devgist-github` で local plan / apply。Terraform 管理は維持するため再現性・変更履歴・drift 検知は失わない。「Terraform 管理すること」と「CI で自動 apply すること」は別と考える

### true secret が必要になった場合の判断フロー

```text
true secret が必要
        │
        ▼
1. Resource 自身が Secret Manager を参照できるか？
        │
   ┌────┴────┐
  YES        NO
   │          │
   ▼          ▼
Secret      2. Provider/resource に
Manager        write-only argument (*_wo)
reference      があるか？
   │             │
   │        ┌────┴────┐
   │       YES        NO
   │        │          │
   ▼        ▼          ▼
Terraform  Secret   3. Terraform 管理が
はsecret   Manager     本当に必要か？
を知らない   ↓          │
          ephemeral  ┌─┴───────┐
             ↓       NO        YES
            *_wo      │          │
                      ▼          ▼
                  Terraform 外   sensitive +
                  で secret 操作   state/tfplan を secret 扱い
```

優先順位は、

```text
Secret Manager reference
        ↓
ephemeral + write-only
        ↓
Terraform 管理外
        ↓
protected state / plan
```

とする。

#### Pattern 1: Resource 自身が Secret Manager を参照できる

最も望ましい。Terraform は secret name / version だけを知り、payload は Terraform を通らない。secret payload は手動または別の安全な経路で Secret Manager に投入する。

```hcl
resource "google_secret_manager_secret" "external_api_key" {
  secret_id = "external-api-key"
  replication { auto {} }
}

resource "google_cloud_run_v2_job" "crawler" {
  template {
    template {
      containers {
        image = var.crawler_image
        env {
          name = "EXTERNAL_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.external_api_key.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}
```

#### Pattern 2: Secret 参照不可だが write-only argument がある

Provider が `*_wo` を提供する場合。ephemeral resource から読み、write-only argument に渡す。secret は state / saved plan に保存されない。

```hcl
ephemeral "google_secret_manager_secret_version" "db_password" {
  project = var.gcp_project_id
  secret  = "app-db-password"
  version = tostring(var.db_password_version)
}

resource "google_sql_user" "app" {
  project  = var.gcp_project_id
  instance = google_sql_database_instance.main.name
  name     = "app"

  password_wo         = ephemeral.google_secret_manager_secret_version.db_password.secret_data
  password_wo_version = var.db_password_version
}
```

`ephemeral` は state / plan への永続化を防ぐ仕組みであり、runner から secret を隠す仕組みではない。原則として PR plan WIF には Secret Manager access を付けず、trusted main に必要な secret だけ access を付ける。DevGist は PR author を本人に限定しているため必要性があればリスクを受容する余地はあるが、不要な secret access は付与しない。

#### Pattern 3: Secret 参照不可 + write-only argument なし

- **Option A: secret 操作だけ Terraform 管理外にする**（第一候補）。Terraform は network / IAM / resource 本体を管理し、secret value の設定は gcloud / REST API / dedicated script で行う。Terraform が payload を一度も扱わない
- **Option B: どうしても Terraform 管理する**（最後の手段）。`sensitive = true` を付けるが、state / saved plan に残る。private GCS backend、strict IAM、encryption、audit logs、private saved-plan storage、short retention を適用し、public repository の artifact や PR comment へ raw saved plan を公開しない

### Secret の分類ルール

- **通常の設定値**: Project ID、Region、Service Account email、OIDC subject、resource name、principal identifier。public にして問題なければ通常の `terraform.tfvars` として version control する
- **true secret**: API key、password、OAuth client secret、private key、access token、refresh token。`sensitive` だけ付けるを第一選択にせず、必ず上記の decision tree を適用する

### 再検討条件

- same-repo PR author を本人以外に広げるとき。plan workflow の権限と PR に渡す値を見直す
- true secret が必要になったとき。本 ADR の decision tree を適用する
- Terraform / provider の `ephemeral` / write-only argument の対応が広がったとき。Pattern 2 を優先する

## Consequences (結果・影響)

### Positive (メリット)

- GCP の CI credential は WIF の短期 identity で、長寿命 secret を GitHub Actions に置かない
- true secret は Terraform が payload を知らない設計を優先し、state / plan / log / comment への露出を減らす
- principal identifier を secret にしないことで、repository secret / `TF_VAR_*` / structured masking の複雑さを削除する
- GitHub リソースは Terraform 管理を維持しつつ、CI に GitHub credential を置かない

### Negative (デメリット)

- GitHub リソースの変更はローカル apply が要る
- true secret が必要になった場合、resource / provider の対応によっては Terraform 管理外の操作が残る
- `terraform.tfvars` に principal identifier が残る（public で問題ないという判断）

### Risks / Future Review (将来の課題)

- same-repo PR author を本人以外に広げる場合、plan principal の read 権限と PR に渡す値を再評価する
- `sensitive` を付けた値が state / plan に残ることを見落とすリスク。true secret は decision tree を必ず通す
- Secret Manager を読む WIF identity を PR に与える場合、PR runner が secret を取得できることを認識する

## Next Steps

1. `cursor_oidc_subjects` / `service_account_user_emails` を `terraform.tfvars` に version 管理する（本 PR で実施済み）
2. true secret が必要になったら、本 ADR の decision tree に従って実装する
3. GitHub リソースの変更は `devgist-github` でローカル apply する

## Related Documents

- [[INFRA-ADR-019] GitHub Actions から terraform plan / apply する](./019-github-actions-terraform-plan-apply.md)
- [[INFRA-ADR-016] GitHub Actions から crawler image を Artifact Registry へ push する](./016-github-actions-wif-and-crawler-image-push.md)
- [[INFRA-ADR-017] GitHub Actions の Terraform 由来設定は ops が repository variable として書く](./017-github-actions-terraform-managed-variables.md)
- [Terraform ephemeral values](https://developer.hashicorp.com/terraform/language/values/variables#sensitive-values-in-variables)
- [GitHub Actions secret hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
