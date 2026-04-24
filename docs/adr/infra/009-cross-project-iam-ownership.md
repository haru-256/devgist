# INFRA-ADR-009 Cross-project IAM binding の ownership

## Conclusion (結論)

- workload-specific な cross-project IAM binding は、原則として **workload identity を定義する downstream 側 Terraform state** で管理する。
- upstream resource の識別子は `terraform_remote_state` で参照し、手動転記は避ける。
- resource 側からの監査は、Terraform の配置場所ではなく、GCP の IAM policy / Policy Analyzer で確認する。

## Status (ステータス)

Accepted (2026-04-25)

## Context (背景・課題)

### 背景

`INFRA-ADR-005` では Terraform root module を GCP project ごとに分割する方針を採用した。
`INFRA-ADR-006` では cross-project の非 secret な値を `terraform_remote_state` で共有し、手動転記を避ける方針を採用した。
`INFRA-ADR-007` では Artifact Registry は `devgist-ops`、crawler runtime は `devgist-app-dev` のように、1 つの workload を複数 project に責務分解する方針を採用した。

この構成では、`devgist-app-dev` の runtime Service Account に、`devgist-ops` の Artifact Registry repository read 権限を付与するような cross-project IAM binding が発生する。
この IAM binding を resource 所有側（`ops`）で管理するか、workload identity 所有側（`app`）で管理するかを決める必要がある。

### 要件と制約

1. **workload の blast radius を把握したい**
   - `crawler` SA がどの external resource にアクセスできるかを、workload 側で追えるようにしたい

2. **resource 側の監査可能性を保ちたい**
   - Artifact Registry repository など、resource 側から「誰に access を許可しているか」を確認できること

3. **手動転記を避けたい**
   - Service Account email や repository ID を tfvars に手動転記して silent success を起こしたくない

4. **state 依存の循環を避けたい**
   - `ops -> app` と `app -> ops` のような remote state 循環を避けたい
   - 既存の apply 順序 `tf -> ops/data -> app` を維持したい

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: resource 所有側 state で管理 | resource owner が access policy を厳格に統制する場合 | resource 側 Terraform で許可先を一覧しやすい | downstream SA email の手動転記、または remote state 逆依存が必要になる | 非採用 |
| Option B: workload identity 所有側 state で管理 | workload の blast radius を把握したい場合 | SA が持つ外部 access を workload 側で追える。upstream outputs を remote state で読める | resource 側 Terraform だけでは許可先一覧が完結しない | 採用 |
| Option C: CI/script で binding を集約生成 | IAM 一覧を別レイヤで集約したい場合 | resource 視点・workload 視点の両方を生成できる可能性がある | 初期フェーズには自動化が重い。source of truth が Terraform から分散しやすい | 非採用 |

### 選定観点

- workload 単位の最小権限レビューがしやすいか
- resource 側の実効 access を監査できるか
- `terraform_remote_state` の依存方向が循環しないか
- 手動転記を避けられるか
- 初期フェーズの運用負荷が低いか

## Considered Options

### Option A: resource 所有側 state で管理する [却下]

`devgist-ops` 側で Artifact Registry repository IAM を管理し、`crawler` SA に `roles/artifactregistry.reader` を付与する。

却下理由:

- `crawler` SA は `devgist-app-dev` 側で作成されるため、`ops` 側がその SA email を知る必要がある。
- `ops` 側で `devgist-app-dev` の remote state を読むと、既存の apply 順序 `ops -> app` と逆向きの依存が発生する。
- tfvars で SA email を受けると、`INFRA-ADR-006` が避けたかった手動転記の問題が再発する。
- workload の blast radius を確認したいときに、`app` 側だけでは外部 access が見えにくくなる。

### Option B: workload identity 所有側 state で管理する [採用]

`devgist-app-dev` 側で `crawler` SA を作成し、`devgist-ops` の Artifact Registry repository ID を remote state で参照して、repository IAM binding を追加する。

採用理由:

- `crawler` SA が何にアクセスできるかを `app` 側 Terraform で追いやすい。
- upstream resource ID は `terraform_remote_state` で参照できるため、手動転記が不要になる。
- apply 順序は `ops -> app` のまま維持でき、remote state の循環を避けられる。
- 実際の IAM binding は Artifact Registry repository の IAM policy に反映されるため、resource 側からの監査は `gcloud artifacts repositories get-iam-policy` や Policy Analyzer で可能である。

### Option C: CI/script で binding を集約生成する [却下]

各 project の outputs を CI/script で収集し、resource 側または専用 state に IAM binding を生成する。

却下理由:

- 初期フェーズでは、Terraform 以外の生成・同期ロジックの保守コストが高い。
- source of truth が Terraform root module から外へ分散しやすい。
- 現時点では、`terraform_remote_state` と project ごとの root module で十分に扱える。

## Decision (決定事項)

Cross-project IAM binding のうち、特定 workload identity の外部 access を表すものは、workload identity を定義する downstream 側 Terraform state で管理する。

### 採用方針

- workload-specific な access edge は SA 定義側 state で管理する
  - 例: `crawler` SA に `devgist-ops` の Artifact Registry `crawler` repository read を付与する
  - 例: `backend` SA に `devgist-data-dev` の Secret Manager secret accessor を付与する
- upstream resource の識別子は `terraform_remote_state` で参照する
- secret 値は Terraform outputs / remote state で共有しない
- IAM binding は repository / bucket / secret など、可能な限り resource 単位に絞る
- resource 側の実効 access は GCP の IAM policy / Policy Analyzer で監査する

### resource 所有側 state で管理するもの

- resource と identity が同じ project/state にある IAM binding
- shared resource 全体の共通 policy
- organization / folder / project level の governance policy
- workload-specific ではない CI/CD や platform 管理者向けの broad access
- authoritative policy 管理が必要な場合

### 初期構成

```
devgist-ops
└── Artifact Registry repository: crawler

devgist-app-dev
├── Service Account: crawler
└── Artifact Registry repository IAM member
    ├── resource: devgist-ops/crawler
    ├── role: roles/artifactregistry.reader
    └── member: serviceAccount:crawler@haru256-devgist-app-dev.iam.gserviceaccount.com
```

### 具体例: crawler が Artifact Registry repository を pull する

`crawler` runtime SA は `devgist-app-dev` 側で作成する。
Artifact Registry repository は `devgist-ops` 側で作成する。
`crawler` SA が image を pull するための repository IAM binding は、workload-specific な access edge なので `devgist-app-dev` 側で管理する。

`devgist-ops` 側では repository ID / location / project ID を output する。

```hcl
output "ops_project_id" {
  value       = data.google_project.project.project_id
  description = "The GCP project ID managed by the ops environment"
}

output "crawler_artifact_registry_repository_id" {
  value       = module.artifact_registries["crawler"].repository_id
  description = "The Artifact Registry repository ID for crawler images"
}

output "crawler_artifact_registry_repository_location" {
  value       = module.artifact_registries["crawler"].location
  description = "The Artifact Registry repository location for crawler images"
}
```

`devgist-app-dev` 側では `devgist-ops` の remote state を読み、`crawler` SA に repository 単位の reader を付与する。

```hcl
data "terraform_remote_state" "ops" {
  backend = "gcs"

  config = {
    bucket = "haru256-devgist-ops-tfstate"
    prefix = "default"
  }
}

module "service_accounts" {
  source = "../../../modules/service_accounts"

  project_id = data.google_project.project.project_id

  service_accounts = {
    crawler = {
      description = "Service account used by the crawler workload in dev"
    }
  }
}

resource "google_artifact_registry_repository_iam_member" "crawler_reader" {
  project    = data.terraform_remote_state.ops.outputs.ops_project_id
  location   = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_location
  repository = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_id
  role       = "roles/artifactregistry.reader"
  member     = module.service_accounts.members["crawler"]
}
```

この配置により、`devgist-app-dev` 側では `crawler` SA が持つ外部 access を追いやすくなる。
一方で、実際の binding は Artifact Registry repository の IAM policy に反映されるため、`devgist-ops` 側からも `gcloud artifacts repositories get-iam-policy` で監査できる。

### 監査方法

Artifact Registry repository に直接付いた IAM policy は以下で確認する。

```bash
gcloud artifacts repositories get-iam-policy crawler \
  --project=haru256-devgist-ops \
  --location=us-central1
```

実効 access は inherited IAM も含めて Policy Analyzer で確認する。

```bash
gcloud asset analyze-iam-policy \
  --project=haru256-devgist-ops \
  --full-resource-name="//artifactregistry.googleapis.com/projects/haru256-devgist-ops/locations/us-central1/repositories/crawler" \
  --permissions="artifactregistry.repositories.downloadArtifacts"
```

### 再検討条件

- resource owner 側で access policy を Terraform 上も一元管理する必要が出た場合
- CI/CD orchestration が整い、state 間依存や generated IAM policy を安全に扱えるようになった場合
- organization / folder level の IAM governance が導入され、project 単位の判断では不十分になった場合

## Consequences (結果・影響)

### Positive (メリット)

- workload SA の blast radius を SA 定義側 Terraform で追いやすい
- 手動転記を避け、ADR-006 の `terraform_remote_state` 方針と整合する
- `ops -> app` の apply 順序を維持できる
- resource 側の監査は GCP の IAM policy / Policy Analyzer で補える

### Negative (デメリット)

- resource 所有側 Terraform だけを見ても、すべての許可先一覧は完結しない
- access review では Terraform state と GCP IAM policy / Policy Analyzer の役割を使い分ける必要がある
- downstream state が upstream resource IAM を変更するため、設計意図を ADR と README で明示しないと ownership が誤解されやすい

### Risks / Future Review (将来の課題)

- cross-project IAM binding が増えすぎると、workload 側 Terraform の見通しが悪くなる可能性がある
- resource 側監査の運用が定着しないと、resource owner 視点の access review が弱くなる
- IAM Deny や organization policy など allow policy 以外の制約が増えた場合、Policy Analyzer だけでは判断できない場合がある

## Next Steps

1. `devgist-app-dev` 側で `crawler` SA の Artifact Registry reader binding を管理する
2. `infra/README.md` に cross-project IAM binding の ownership と監査方法を追記する
3. 将来 GCS / Secret Manager / Cloud SQL の cross-project IAM を追加するときも、本 ADR の判断基準に従う

## Related Documents

- [[INFRA-ADR-005] Terraform environments は GCP project ごとに分割する](./005-terraform-environment-slicing.md)
- [[INFRA-ADR-006] Cross-project Terraform output 共有戦略](./006-cross-project-output-sharing.md)
- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [[INFRA-ADR-008] Service Account 命名規則](./008-service-account-naming.md)
- [Artifact Registry repository IAM policy command](https://cloud.google.com/sdk/gcloud/reference/artifacts/repositories/get-iam-policy)
- [Policy Analyzer for allow policies](https://cloud.google.com/policy-intelligence/docs/analyze-iam-policies)
