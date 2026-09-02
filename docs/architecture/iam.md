# IAM と認証

## 鍵を作らない

- Service Account の JSON キーを作らない。`service_accounts` module は `generate_keys = false`
- 人間ユーザーの Application Default Credentials を CI や Cloud Agent 環境に置かない
- 外部実行基盤（Cursor Cloud、GitHub Actions）からの認証は **Workload Identity Federation** を使う

根拠: [INFRA-ADR-013](../adr/infra/013-cursor-oidc-workload-identity-federation.md)（初出。以降すべての ADR が維持）

## WIF は federated principal への direct resource access

**Service Account を impersonate しない。CI / agent 用の SA を作らない。**
STS が出した federated token をそのままリソースへ使い、IAM は federated principal に直接付ける。

GCP 公式が direct access を既定として推奨し、impersonation は API 制限がある場合の代替と位置づけているため。
federated identity 非対応の API が必要になったときだけ、その API に限って impersonation を再検討する。

根拠: [INFRA-ADR-014](../adr/infra/014-cursor-oidc-wif-direct-resource-access.md)（認証モデル。[INFRA-ADR-015](../adr/infra/015-guest-iam-downstream.md) が維持）、
[INFRA-ADR-016](../adr/infra/016-github-actions-wif-and-crawler-image-push.md)（GitHub Actions へ適用）

## WIF pool は IdP × リポジトリごとに分ける

いずれも `haru256-devgist-ops` に置く。1 pool につき 1 provider。同じ IdP を二重に federation しない。

| pool | provider | issuer | 用途 | IAM の主キー |
|---|---|---|---|---|
| `cursor` | `oidc` | `https://api.cursor.com` | Cursor Cloud Agent | `principal://.../subject/<cursor sub>` |
| `github-devgist` | `oidc` | `https://token.actions.githubusercontent.com` | GitHub `haru-256/devgist` 専用 | `principalSet://.../attribute.ci_scope/<scope>` |

- 別の GitHub リポジトリを足すときは別 pool にする
- `ops` は dev / prod を兼ねるので、環境で pool を分けない。環境の分離は IAM で行う
- GitHub の IAM 主キーは `attribute.ci_scope`。**`attribute.environment` は使わない**
  （PR の YAML が `environment:` を自由に名乗れるため。[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md) が [INFRA-ADR-016](../adr/infra/016-github-actions-wif-and-crawler-image-push.md) の判断を置き換えた）

`ci_scope` の合成規則と各 scope の権限は [cicd.md](cicd.md) を参照。

### provider の attribute condition

| pool | condition |
|---|---|
| `cursor` | `repo_url == "github.com/haru-256/devgist"` かつ `agent_runtime == "managed"` |
| `github-devgist` | `repository_id` と `repository_owner_id` の固定、かつ `attribute.ci_scope != "none"` |

リポジトリの固定には rename で変わらない **id** を使う。名前や owner login は使わない。
`ref` や workflow を共通 condition に入れない（入れると PR の plan が通らなくなる）。
Cursor の `environment_id` は信頼条件に入れない（環境の作り直しで Terraform 変更が必要になるため）。

## Service Account

### 命名

`<workload-or-actor>[-<purpose>]`。**環境名と `-sa` suffix は付けない**（[INFRA-ADR-008](../adr/infra/008-service-account-naming.md)）。

- runtime は workload 名だけ: `crawler`
- runtime 以外、または 1 workload に複数必要なとき: `github-actions`、`backend-deployer`
- 環境は project ID が表す: `crawler@haru256-devgist-app-dev.iam.gserviceaccount.com`

> [INFRA-ADR-007](../adr/infra/007-artifact-registry-and-sa-strategy.md) 本文の `crawler-dev-sa` という例示名は 008 で置き換わっています。ADR-007 の SA 分離方針そのものは有効です。

### 粒度

workload 実行用 SA は **アプリケーション × 環境**で作る。compute platform（Cloud Run / GKE / Cloud Batch 等）が変わっても同じ原則を適用する。
目的は Artifact Registry ではなく、周辺リソース（Cloud SQL / Secret Manager / GCS）の blast radius をアプリ単位に限ることにある（[INFRA-ADR-007](../adr/infra/007-artifact-registry-and-sa-strategy.md)）。

Artifact Registry の read は project 全体ではなく **リポジトリ単位**で付ける。

### 現存する SA

| SA | project | 用途 |
|---|---|---|
| `crawler` | `haru256-devgist-app-dev` | Cloud Run Job の runtime |
| `github-actions` | `haru256-devgist-ops` | **未使用**。現行の CI パイプラインは使わない。削除は未実施（[INFRA-ADR-016](../adr/infra/016-github-actions-wif-and-crawler-image-push.md)） |

## guest IAM の置き場

別 root の principal に IAM を付ける binding（guest IAM）の置き場は、次で一意に決まる。

**書いてよいのは、その binding がつなぐ identity の root か resource の root だけ。そのうち依存の下流が書く。**

| identity の root ＼ resource の root | data（箱） | ops | app |
|---|---|---|---|
| **ops** | ops が書く | 同一 root | app が書く |
| **app** | app が書く | app が書く | 同一 root |

書いてはいけない場所:

- **箱（`data`）のゲスト一覧**。data はリソースを作って識別子を output するだけで、consumer の principal を持たない
- **identity も resource も持たない第三の root**。両方の remote state を読めるからといって書かない

根拠: [INFRA-ADR-015](../adr/infra/015-guest-iam-downstream.md)。
[INFRA-ADR-009](../adr/infra/009-cross-project-iam-ownership.md) は supersede されていません。009 の「downstream が書く」を、identity が上流にある場合まで含めて一意にしたのが 015 です。

> [INFRA-ADR-014](../adr/infra/014-cursor-oidc-wif-direct-resource-access.md) が Cursor → datalake の IAM を `app-dev` に置いた判断は捨てられています。`app` は identity でも箱でもない第三の root でした。現在は `ops` が書きます。

### 現在の配置

| identity | resource | 付ける role | 書く root |
|---|---|---|---|
| Cursor federated principal | `data-dev` の datalake | `storage.objectViewer` / `storage.objectCreator` | `ops` |
| Cloud Run Service Agent（app-dev） | `ops` の Artifact Registry | `artifactregistry.reader` | `app-dev` |
| `crawler` SA | `data-dev` の datalake | `storage.objectViewer` / `storage.objectCreator` | `app-dev` |
| GitHub `ci_scope` | tfstate bucket と `tf` project のロール | 下記 [cicd.md](cicd.md) 参照 | `ops` |
| GitHub `ci_scope` | `data-dev` のリソースと project ロール | 同上 | `ops` |
| GitHub `ci_scope` | `ops` 同一 root の Artifact Registry など | 同上 | `ops` |
| GitHub `ci_scope` | `app-dev` の project ロール、`crawler` SA の actAs | 同上 | `app-dev` |

> **image を pull するのは `crawler` SA ではありません。**
> クロスプロジェクトの Artifact Registry から image をダウンロードするのは
> Cloud Run Service Agent（`service-<project-number>@serverless-robot-prod.iam.gserviceaccount.com`）です。
> `crawler` SA が使われるのは、コンテナ起動後のアプリケーションからの GCS アクセスなどです。
>
> [INFRA-ADR-007](../adr/infra/007-artifact-registry-and-sa-strategy.md) / [INFRA-ADR-009](../adr/infra/009-cross-project-iam-ownership.md) の本文は
> 「crawler SA に Artifact Registry の reader を付ける」と書いていますが、実装は上記の通りです。
> 「リポジトリ単位で reader を付ける」「binding は app-dev が書く」という方針自体は変わりません。

この規則は **guest access に限る**。同一 root 内の IAM、箱の共通 policy（公開禁止、UBLA、暗号化）、org / folder の governance は対象外で、resource 側に置く。

## 監査

Terraform の配置場所からは許可先の一覧が完結しない（同じリソースの member が、書く root の数だけ Terraform 上は割れる）。
実効 ACL は **GCP 側で見る**。

```bash
# リソースに直接付いた IAM policy
gcloud artifacts repositories get-iam-policy crawler \
  --project=haru256-devgist-ops --location=us-central1

# 継承も含めた実効 access
gcloud asset analyze-iam-policy \
  --project=haru256-devgist-ops \
  --full-resource-name="//artifactregistry.googleapis.com/projects/haru256-devgist-ops/locations/us-central1/repositories/crawler" \
  --permissions="artifactregistry.repositories.downloadArtifacts"
```

## 再検討の条件

- 使いたい GCP API が federated identity 非対応だった場合 → その API だけ SA impersonation に寄せる
- 箱の消費者が増え、ゲスト一覧を箱の PR で見たくなった場合 → [INFRA-ADR-015](../adr/infra/015-guest-iam-downstream.md) の Option B を再検討
- `ops` の identity が `app` のほぼ全部を所有し始めた場合 → identity の置き場を `app` へ移すか再検討
- `ops` の PR に AR / WIF / data-dev ACL / data-prod ACL が混ざり始めたら、分割の兆候
