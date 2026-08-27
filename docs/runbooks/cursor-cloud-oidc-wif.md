# Cursor Cloud から GCP へ OIDC / WIF で接続する

## 概要

Cloud Agent が Cursor の短命 OIDC JWT を GCP STS に渡し、federated token で data-dev datalake を読む。設計は [INFRA-ADR-014](../adr/infra/014-cursor-oidc-wif-direct-resource-access.md)。WIF pool は #83。この文書は apply 後の Cursor 側配線である。

Cursor は IdP、GCP が検証する。ダッシュボードに WIF や issuer は登録しない。token 交換を毎回指示する必要はない。ADC が mint と STS を行う。mint の `aud` は `GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE` のまま使う。`allowed_audiences` が空なら GCP は canonical name を `https:` の有無どちらでも受理する（[仕様](https://cloud.google.com/iam/docs/reference/rest/v1/projects.locations.workloadIdentityPools.providers#Oidc)）。

ヘルパーは [`scripts/cursor-cloud/setup-adc.sh`](../../scripts/cursor-cloud/setup-adc.sh)（`start` から credential JSON を書く）と [`scripts/cursor-cloud/cursor-gcp-oidc`](../../scripts/cursor-cloud/cursor-gcp-oidc)（Google Auth が呼ぶ mint。`jq` と `curl` が要る）。

## Cursor に設定するもの

入れる場所は [Cloud Agents](https://cursor.com/dashboard/cloud-agents) の Secrets と Environment。`CURSOR_WIF_PROJECT_NUMBER` は ops の terraform output `ops_project_number` である。秘密ではない。

### Secrets

| 名前 | 値 |
|---|---|
| `CURSOR_WIF_PROJECT_NUMBER` | ops の `ops_project_number` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/home/ubuntu/.config/gcloud/cursor-wif.json`（`$HOME` が違うときは `echo $HOME` で合わせる） |
| `GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES` | `1` |
| `DATA_LAKE_BUCKET_NAME` | crawler を動かすなら `haru256-devgist-data-dev-datalake` |

`GOOGLE_APPLICATION_CREDENTIALS` は鍵ではなく、`start` が書く WIF credential config のパスである。

### Environment

| 項目 | 値 |
|---|---|
| `start` | `scripts/cursor-cloud/setup-adc.sh` |
| Network allowlist（egress を制限しているときだけ） | `sts.googleapis.com`、`iam.googleapis.com`、`storage.googleapis.com`、`www.googleapis.com`、`oauth2.googleapis.com` |

既存の install / snapshot は残す。リポジトリに `.cursor/environment.json` は置かない。`install` で export した変数は Build 後に残らない。mint 自体は VM 内の Unix socket で、allowlist は不要である。

### 置かないもの

- Service Account JSON キー、人間ユーザーの ADC
- WIF pool / provider / issuer（Cursor 側に登録する欄は無い）
- `service_account_impersonation_url`（`gcloud ... create-cred-config` に `--service-account` を付けない）
- `cursor_oidc_subjects`（Cursor ではなく app-dev の gitignore 済み `terraform.tfvars`）

## 手順

1. ops を apply し、`ops_project_number` を控える。
2. app-dev の `cursor_oidc_subjects` に、許可する Cursor `sub` を入れる。例: `["user:308716925"]`。`sub` はメールではない。空なら WIF は通っても GCS は拒否する。
3. 上の「Cursor に設定するもの」を Secrets と Environment に入れる。
4. 新しい Cloud Agent を起動する。`start` が `$HOME/.config/gcloud/cursor-wif.json` を書く。`command` は checkout した `cursor-gcp-oidc` の絶対パスである。

起動後は Google Auth が JSON を読み、ヘルパーが JWT を mint し（寿命 5 分）、STS が `repo_url` と `agent_runtime == managed` を見る。GCS は `principal://.../workloadIdentityPools/cursor/subject/<sub>` の IAM だけで許す。

## 動作確認

WIF と allowlist の apply、Cursor の設定、`start` 済みが前提。本線は ADC が token を取れることである。Secrets が入っていれば export は不要。

```bash
gcloud auth application-default print-access-token >/dev/null
```

mint ヘルパーだけを試すときは audience を渡す。値は付け替えない。

```bash
export GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE="//iam.googleapis.com/projects/${CURSOR_WIF_PROJECT_NUMBER}/locations/global/workloadIdentityPools/cursor/providers/oidc"
scripts/cursor-cloud/cursor-gcp-oidc | jq -r '.success'
```

ヘルパーのテストは `python3 scripts/cursor-cloud/tests/test_scripts.py`。

## うまくいかないとき

| 症状 | 見るところ |
|---|---|
| `jq is required` | Cloud Agent の PATH に `jq` が無いか |
| `executables need to be explicitly allowed` | Secrets の `GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES` が `1` か |
| credential ファイルが無い | `start` に `setup-adc.sh` があるか。`CURSOR_WIF_PROJECT_NUMBER` が入っているか |
| STS が audience 不一致 | JWT `aud` が canonical name か。`allowed_audiences` にカスタム値だけを入れてないか |
| mint は成功、GCS が 403 | `cursor_oidc_subjects` と JWT `sub` |
| `OIDC socket not found` | `/run/cursor/api.sock`。Cursor 管理 VM 以外では無い |
| credential JSON に `service_account_impersonation_url` がある | `--service-account` を付けて生成している。Cloud Agent では `setup-adc.sh` を使う |

JSON を手元で書くときも `--service-account` は付けない。

```bash
gcloud iam workload-identity-pools create-cred-config \
  "projects/${CURSOR_WIF_PROJECT_NUMBER}/locations/global/workloadIdentityPools/cursor/providers/oidc" \
  --subject-token-type=urn:ietf:params:oauth:token-type:id_token \
  --executable-command="$(pwd)/scripts/cursor-cloud/cursor-gcp-oidc" \
  --output-file="${HOME}/.config/gcloud/cursor-wif.json"
```
