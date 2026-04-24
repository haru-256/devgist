# INFRA-ADR-008 Service Account 命名規則

## Conclusion (結論)

- Service Account ID は `<workload-or-actor>[-<purpose>]` 形式とする。
- 環境名（`dev` / `prod`）と `sa` suffix は Service Account ID に含めない。
- 環境は project ID、principal 種別は `iam.gserviceaccount.com` の email domain で表現されるため、Service Account ID では責務を短く明確に表す。

## Status (ステータス)

Accepted (2026-04-25)

## Context (背景・課題)

### 背景

`INFRA-ADR-007` では、ワークロード実行用 Service Account をアプリケーション × 環境の組み合わせ単位で作成する方針を採用した。
その中では `crawler-dev-sa` / `crawler-prod-sa` のような例を使っていたが、実際の Service Account email は `<service-account-id>@<project-id>.iam.gserviceaccount.com` 形式になる。

DevGist の project ID は `haru256-devgist-app-dev` や `haru256-devgist-app-prod` のように環境名を含むため、Service Account ID 側にも `dev` / `prod` を含めると情報が重複する。
また、`iam.gserviceaccount.com` により principal が Service Account であることは明らかなので、`-sa` suffix も型情報として冗長である。

### 要件と制約

1. **責務の明確さ**
   - Service Account ID だけで、どの workload / actor / purpose のための identity か分かること

2. **冗長性の回避**
   - project ID や email domain で既に表現される情報を Service Account ID に重複して持たないこと

3. **GCP 制約への適合**
   - Service Account ID は 6〜30 文字で、lowercase 英数字と hyphen を使う必要がある
   - 将来 frontend / backend / deployer / CI 用の SA が増えても 30 文字制限に収まりやすいこと

4. **既存 ADR との整合**
   - `INFRA-ADR-007` の「アプリケーション × 環境単位で SA を分離する」方針は維持する
   - 環境の識別は Service Account ID ではなく project ID で行う

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `<workload>-<env>-sa` | 単一 project 内に複数環境の SA を同居させる場合 | 名前だけで環境と principal 種別が分かる | DevGist では project ID と email domain と重複する。長くなりやすい | 非採用 |
| Option B: `<workload>` | runtime SA のように workload ごとに 1 つの責務を持つ場合 | 短く、project ID と合わせると意味が明確 | deployer / scheduler など目的違いの SA が増えた時に区別が必要 | 採用 |
| Option C: `<workload-or-actor>-<purpose>` | 1 workload に複数 purpose の SA がある場合 | 目的を表現でき、30 文字制限にも比較的収まりやすい | purpose の語彙を揃えないと揺れる | 採用 |

### 選定観点

- email 全体で見たときに意味が明確か
- GCP の 30 文字制限に余裕を持てるか
- frontend / backend / crawler / GitHub Actions などが増えても一貫して適用できるか
- 既存の project 分離方針と矛盾しないか

## Considered Options

### Option A: `<workload>-<env>-sa` [却下]

`crawler-dev-sa` や `backend-prod-sa` のように、workload、環境、principal 種別をすべて Service Account ID に含める。

却下理由:

- DevGist では project ID が環境を表しているため、`dev` / `prod` が重複する。
- Service Account email domain によって principal 種別は分かるため、`sa` suffix は型情報として冗長である。
- `backend-prod-deployer-sa` のように purpose が増えると 30 文字制限に近づきやすい。

### Option B: `<workload>` [採用]

`crawler`、`frontend`、`backend` のように、runtime identity は workload 名だけで表す。

採用理由:

- `crawler@haru256-devgist-app-dev.iam.gserviceaccount.com` のように、email 全体で見れば workload と環境が自然に分かる。
- runtime SA は workload と 1:1 で対応することが多く、短く読みやすい。
- `INFRA-ADR-007` の SA 分離方針を維持したまま、命名だけを簡潔にできる。

### Option C: `<workload-or-actor>-<purpose>` [採用]

`github-actions`、`backend-deployer`、`crawler-scheduler` のように、workload または actor に purpose を付ける。

採用理由:

- CI/CD、deployer、scheduler など runtime 以外の identity でも責務を表現しやすい。
- 1 workload に複数 SA が必要になった場合でも、短い purpose を付けて区別できる。
- `<workload>` だけで不足する場合の自然な拡張形になる。

## Decision (決定事項)

DevGist の Service Account ID は `<workload-or-actor>[-<purpose>]` 形式とし、環境名と `sa` suffix は含めない。

### 採用方針

- runtime SA は原則として `<workload>` を使う
  - 例: `crawler`, `frontend`, `backend`
- runtime 以外、または 1 workload に複数 SA がある場合は `<workload-or-actor>-<purpose>` を使う
  - 例: `github-actions`, `backend-deployer`, `crawler-scheduler`
- 環境名は Service Account ID ではなく project ID で表現する
  - 例: `crawler@haru256-devgist-app-dev.iam.gserviceaccount.com`
  - 例: `crawler@haru256-devgist-app-prod.iam.gserviceaccount.com`
- `-sa` suffix は付けない
- purpose は短く、具体的な責務を表す語にする

### 初期構成

```
haru256-devgist-ops
└── github-actions@haru256-devgist-ops.iam.gserviceaccount.com
    └── Artifact Registry push 用

haru256-devgist-app-dev
└── crawler@haru256-devgist-app-dev.iam.gserviceaccount.com
    └── crawler runtime 用

haru256-devgist-app-prod（将来）
└── crawler@haru256-devgist-app-prod.iam.gserviceaccount.com
    └── crawler runtime 用
```

### 再検討条件

- 単一 project 内に複数環境の SA を同居させる方針へ変更する場合
- Service Account ID だけを project context なしで扱う運用が増え、環境名なしでは混乱が大きくなる場合
- 組織全体の命名規則が別途定義され、DevGist 固有規則を合わせる必要が出た場合

## Consequences (結果・影響)

### Positive (メリット)

- Service Account ID が短くなり、GCP の 30 文字制限に余裕が出る
- project ID と Service Account ID の責務分担が明確になる
- frontend / backend / crawler などの runtime SA を横並びで扱いやすい
- `-sa` suffix のような型情報を名前に持たずに済む

### Negative (デメリット)

- Service Account ID 単体では環境が分からない
- `INFRA-ADR-007` の例示名（`crawler-dev-sa` 等）とは異なる命名になる
- project context なしでログや一覧を見た場合は、email 全体または resource name を確認する必要がある

### Risks / Future Review (将来の課題)

- purpose の語彙が増えすぎると命名揺れが起きるため、必要に応じて `deployer` / `scheduler` / `ci` などの語彙を整理する
- 既に作成済みの SA を改名することはできないため、適用済み環境で命名変更する場合は新 SA 作成と IAM 移行が必要になる

## Next Steps

1. Terraform の Service Account ID を本 ADR の規則へ合わせる
2. `INFRA-ADR-007` の例示名は、本 ADR により命名規則としては supersede されることを参照で明確にする
3. 今後 frontend / backend 用 SA を追加するときは、本 ADR の命名規則に従う

## Related Documents

- [[INFRA-ADR-001] GCPプロジェクト構成と環境分離戦略](./001-gcp-project-structure.md)
- [[INFRA-ADR-004] Terraform State Project と Ops Project を分離する](./004-separate-tf-and-ops-projects.md)
- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [Google Cloud: Create service accounts](https://cloud.google.com/iam/docs/service-accounts-create)
