# INFRA-ADR-007 Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計

## Conclusion (結論)

- Artifact Registry のリポジトリはアプリケーション単位で 1 本とし、dev / prod で共用する。
- イメージの push は dev CI（GitHub Actions / WIF）のみが行い、prod は SHA 固定で同じリポジトリから参照する。
- ワークロード実行用 Service Account は **アプリケーション × 環境** の組み合わせ単位で作成する（例: `crawler-dev-sa`, `crawler-prod-sa`）。Artifact Registry の pull 権限は同じだが、各 SA が持つ周辺リソース（Cloud SQL・Secret Manager・GCS）の権限を最小化することで blast radius を抑える。この方針は Cloud Run に限らず、GKE・Cloud Batch・Cloud Functions など DevGist が採用するすべての compute platform に適用する。
- この方針は crawler に限らず、DevGist のすべてのアプリケーション（API、frontend 等）に適用する。

## Status (ステータス)

Accepted (2026-04-23)

## Context (背景・課題)

### 背景

`INFRA-ADR-004` で `devgist-ops` project を Artifact Registry などの共通運用基盤として定義した。
`INFRA-ADR-005` で Terraform environments は GCP project ごとに分割することが決まり、`devgist-ops` は dev / prod を問わない共通基盤として位置づけられた。

ここで、Artifact Registry のリポジトリを環境ごとに分割するかどうか、およびワークロード実行用 SA の設計方針が未決定だった。

### 要件と制約

1. **イメージの一貫性**
   - dev 環境でテストしたバイナリと同一のイメージを prod にデプロイしたい
   - 環境別にビルドし直すと、理論上異なるバイナリになり得る

2. **IAM による環境分離**
   - dev の CI / SA が prod のリソース（DB、Secret、GCS）にアクセスできないようにしたい

3. **運用シンプルさ**
   - 個人開発の初期フェーズとして、不要な複雑性を避けたい

4. **全アプリケーションへの一貫した適用**
   - crawler だけでなく、API・frontend 等すべての workload に同じ方針を適用したい

### 比較した選択肢

#### リポジトリ戦略

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 環境ごとにリポジトリを分割（`crawler-dev` / `crawler`） | コンプライアンス要件でリポジトリ単位の監査が必要な場合 | リポジトリ単位で push 権限を分離できる | イメージコピー（プロモーション）ステップが必要。SHA 固定で済む問題を過剰に複雑にする | 非採用 |
| Option B: アプリ単位で 1 本（`crawler`）、SHA 固定で dev / prod 共用 | ビルドを 1 回に統一し、同一バイナリを昇格させたい場合 | シンプル。「テストしたバイナリをそのままデプロイ」が自然に実現できる | リポジトリ単位の push 権限分離ができない（IAM で補う） | 採用 |

#### Service Account 戦略

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 環境単位で SA を作成（`app-dev-sa`, `app-prod-sa`） | 管理対象を最小にしたい場合 | SA 数が少ない | 同一環境内のアプリが侵害された場合、他アプリのリソースにもアクセスできてしまう | 非採用 |
| Option B: アプリケーション × 環境単位で SA を作成（`crawler-dev-sa` 等） | 最小権限の原則を徹底したい場合 | 侵害時の blast radius をアプリ単位に限定できる。Terraform で管理すれば SA 増加のコストは低い。compute platform が変わっても同じ原則を適用できる | SA 数が増える | 採用 |

### 選定観点

- 「テストしたイメージをそのまま prod に使う」という原則を守れるか
- SHA 固定が前提であれば、リポジトリ分割は不要な複雑性か
- SA 分離の本質的な目的が Artifact Registry ではなく周辺リソースの IAM 分離にあるか
- Terraform で管理する前提であれば、アプリケーション単位の SA 分離は運用コストとして許容できるか

## Considered Options

### Option A: リポジトリを環境ごとに分割する [却下]

`crawler-dev` と `crawler`（prod 用）のように環境別にリポジトリを作り、dev でビルドしたイメージを prod リポジトリにコピーしてから prod 環境が参照する。

却下理由:

- **プロモーションステップが不要な複雑性を生む**
  - SHA 固定で同一リポジトリを参照するだけで、「テストしたバイナリを prod にデプロイする」は達成できる。
  - イメージコピーのステップを追加しても、安全性は上がらない。

- **コンプライアンス要件がない**
  - 個人開発の初期フェーズでは「prod リポジトリには承認済みイメージのみ」という監査要件は存在しない。

- **ADR-004 の「共通配布基盤」という設計意図と合わない**
  - `devgist-ops` は workload・環境横断の共通基盤として設計されており、リポジトリを環境で分割するとその意図が崩れる。

### Option B: アプリ単位で 1 本、SHA 固定で dev / prod 共用する [採用]

`crawler`・`api`・`frontend` のようにアプリケーション単位でリポジトリを 1 本作り、dev / prod ともに SHA 固定で同じリポジトリを参照する。

採用理由:

- **「ビルドは 1 回」の原則を自然に実現できる**
  - dev CI がビルドして push した `crawler:sha-abc123` を、そのまま prod でも参照する。
  - dev で検証したバイナリと prod にデプロイするバイナリが同一であることが保証される。

- **SHA 固定により、prod への意図しない影響を防げる**
  - `latest` タグではなく commit SHA でイメージを固定することで、dev への新しい push が prod に自動で流れ込まない。
  - リポジトリ分割なしでも環境分離の実質的なリスクはない。
  - なお、Docker タグは技術的には可変（同名タグへの再 push が可能）であるため、厳密な不変性が必要な場合は `image@sha256:...` 形式の digest 参照を使用する。初期フェーズでは CI の push 権限を適切に絞ることで十分と判断する。

- **シンプルで拡張しやすい**
  - アプリが増えても同じルール（アプリ名でリポジトリ 1 本）を適用するだけ。

## Decision (決定事項)

Artifact Registry リポジトリはアプリケーション単位で 1 本とし、dev / prod 共用・SHA 固定を採用する。ワークロード実行用 SA は compute platform の種類によらず、アプリケーション × 環境の組み合わせ単位で作成する。

### 採用方針

**Artifact Registry リポジトリ**

- リポジトリはアプリケーション単位で 1 本作成する
  - 例: `crawler`, `api`, `frontend`
- dev / prod ともに同じリポジトリの同じ SHA を参照する
- `latest` タグは使用せず、常に commit SHA でイメージを固定する

**イメージの build / push**

- ビルドと push は dev CI（GitHub Actions / WIF）のみが行う
- prod 側から独自にビルドし直すことはしない
- push する SA は `devgist-ops` の GitHub Actions 用 SA に集約する

**Service Account**

- ワークロード実行用 SA はアプリケーション × 環境の組み合わせ単位で作成する
  - 例: `crawler-dev-sa`, `crawler-prod-sa`, `api-dev-sa`, `api-prod-sa`
- この方針は compute platform の種類（Cloud Run / Cloud Run Jobs / GKE / Cloud Batch / Cloud Functions 等）によらず統一して適用する
- Artifact Registry への read 権限（`roles/artifactregistry.reader`）は各 SA で共通
- SA を細分化する目的は最小権限の原則の徹底。あるアプリが侵害されても、他アプリの Cloud SQL・Secret Manager・GCS にアクセスできない
- Terraform で管理することで SA 増加のコストを抑える

### 初期構成

> 以下の名称は Terraform environment 名（`infra/terraform/environments/` 配下のディレクトリ名）を示す。
> GCP project ID は `haru256-` プレフィックスが付く（例: `haru256-devgist-ops`）。

```
devgist-ops（Artifact Registry）
├── crawler       ← dev / prod 共用、SHA 固定で参照
├── api           ← 同上（将来）
└── frontend      ← 同上（将来）

GitHub Actions SA（devgist-ops）
└── roles/artifactregistry.writer → 全リポジトリへの push 権限

crawler-dev-sa（devgist-app-dev）← Cloud Run Jobs / GKE / Cloud Batch 等共通
├── roles/artifactregistry.reader → crawler リポジトリの pull 権限
├── dev Cloud SQL（crawler 用）への接続権限
└── dev Secret Manager（crawler 用）への read 権限

crawler-prod-sa（devgist-app-prod）← 同上
├── roles/artifactregistry.reader → crawler リポジトリの pull 権限
├── prod Cloud SQL（crawler 用）への接続権限
└── prod Secret Manager（crawler 用）への read 権限

api-dev-sa（devgist-app-dev）← 将来
└── ...（api が必要なリソースのみ）

api-prod-sa（devgist-app-prod）← 将来
└── ...（api が必要なリソースのみ）
```

### 再検討条件

- コンプライアンス要件が発生し「prod リポジトリには承認済みイメージのみ」という監査が必要になった場合
- 組織的な billing 分離のために dev / prod で別 `devgist-ops` project が必要になった場合

## Consequences (結果・影響)

### Positive (メリット)

- 「テストしたバイナリをそのまま prod にデプロイ」が自然に実現できる
- イメージのプロモーション（コピー）ステップが不要でシンプル
- SA をアプリ × 環境単位に分離することで、侵害時の blast radius をアプリ単位に限定できる
- Terraform で管理するため SA 増加のコストは低い
- アプリが増えても同じルールで拡張できる

### Negative (デメリット)

- リポジトリ単位での push 権限分離ができない（「dev CI が誤って prod 向けタグを push できてしまう」は SHA 管理の規律で防ぐ）
- SA 数が増える（アプリ × 環境の組み合わせ分）

### Risks / Future Review (将来の課題)

- SHA 固定の徹底: `latest` タグが混入しないよう CI の設定と Terraform での image 参照を統一する
- GitHub Actions SA の権限範囲: push 権限を全リポジトリに一括付与するか、リポジトリ単位に絞るかは CI/CD 整備時に検討する

## Next Steps

1. `devgist-ops` の Terraform に Artifact Registry リポジトリ（`crawler` 等）を定義する
2. `devgist-app-dev` / `devgist-app-prod` の Terraform にアプリケーション × 環境単位の SA を定義し、IAM を設定する
3. GitHub Actions の WIF / SA に Artifact Registry への push 権限を付与する
4. CI/CD で commit SHA をイメージタグとして使う設定を実装する
5. `infra/README.md` の service-to-project 対応表に本 ADR の方針を反映する

## Related Documents

- [INFRA-ADR-004] Terraform State Project と Ops Project を分離する
- [INFRA-ADR-005] Terraform environments は GCP project ごとに分割する
- [INFRA-ADR-006] Cross-project Terraform output 共有戦略
- [ADR運用ガイド](../../../docs/adr/README.md)
- [Infrastructure README](../../../infra/README.md)
