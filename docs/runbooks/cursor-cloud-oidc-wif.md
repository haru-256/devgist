# Cursor Cloud から GCP へ OIDC / WIF で接続する

Cloud Agent が Cursor の短命 OIDC JWT を GCP STS に渡し、federated token で data-dev datalake を読む手順。設計は [INFRA-ADR-014](../adr/infra/014-cursor-oidc-wif-direct-resource-access.md)。Terraform は #83。この文書は apply 後の Cursor 側配線である。

Cursor は IdP で、GCP が検証する。WIF pool / provider / issuer を Cursor のダッシュボードに登録しない。

## 置かないもの

- Service Account JSON キー
- 人間ユーザーの Application Default Credentials
- credential config の `service_account_impersonation_url`（`--service-account` 付きの `gcloud iam workload-identity-pools create-cred-config`）
- `cursor_oidc_subjects`（app-dev の gitignore 済み `terraform.tfvars`）

## Terraform から控える値

ops の `ops_project_number` を Cursor Secrets の `CURSOR_WIF_PROJECT_NUMBER` に入れる。秘密ではない。

app-dev の `cursor_oidc_subjects` に許可する Cursor `sub` を入れる。例: `["user:308716925"]`。空なら WIF は通っても GCS は拒否する。`sub` はメールではない。

## Audience

Google Auth は `GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE` に次を渡す。`cursor-gcp-oidc` はそれを mint `aud` にそのまま使う。

```text
//iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/cursor/providers/oidc
```

`allowed_audiences` が空のとき、GCP は canonical name を `https:` の有無どちらでも受理する。[仕様](https://cloud.google.com/iam/docs/reference/rest/v1/projects.locations.workloadIdentityPools.providers#Oidc)。カスタム値だけを `allowed_audiences` に入れるとその自動受理は効かない。このリポジトリでは空のままにする。

## Cursor Secrets

[Cloud Agents の Secrets](https://cursor.com/dashboard/cloud-agents) に次を入れる。

| 名前 | 値 |
|---|---|
| `CURSOR_WIF_PROJECT_NUMBER` | ops の `ops_project_number` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/home/ubuntu/.config/gcloud/cursor-wif.json`（`$HOME` が違うときは合わせる） |
| `GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES` | `1` |
| `DATA_LAKE_BUCKET_NAME` | crawler を動かすなら `haru256-devgist-data-dev-datalake` |

`GOOGLE_APPLICATION_CREDENTIALS` は鍵ではなく WIF credential config のパスである。

## Environment の `start`

既存の install / snapshot は残す。`.cursor/environment.json` はリポジトリに置かない。start に次を足す。

```bash
scripts/cursor-cloud/setup-adc.sh
```

これは `$HOME/.config/gcloud/cursor-wif.json` を書く。`command` は checkout した `scripts/cursor-cloud/cursor-gcp-oidc` の絶対パス。ADC の環境変数は Secrets が渡す。`install` で export しても Build 後に残らない。

egress を制限しているなら `sts.googleapis.com`、`iam.googleapis.com`、`storage.googleapis.com`、`www.googleapis.com`、`oauth2.googleapis.com` を許可する。mint は VM 内 socket である。

## 起動後に起きること

1. Google Auth が `cursor-wif.json` を読む
2. `cursor-gcp-oidc` が socket から JWT を mint する（寿命 5 分）
3. STS が `repo_url` と `agent_runtime == managed` を見る
4. GCS は `principal://.../workloadIdentityPools/cursor/subject/<sub>` の IAM だけで許す

token 交換を手順として繰り返さない。ADC が mint と STS を行う。

## 動作確認

WIF と allowlist の apply が済んでいる前提。

```bash
export GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE="//iam.googleapis.com/projects/${CURSOR_WIF_PROJECT_NUMBER}/locations/global/workloadIdentityPools/cursor/providers/oidc"
scripts/cursor-cloud/cursor-gcp-oidc | python3 -c 'import json,sys; print(json.load(sys.stdin)["success"])'

export GOOGLE_APPLICATION_CREDENTIALS="${HOME}/.config/gcloud/cursor-wif.json"
export GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES=1
gcloud auth application-default print-access-token >/dev/null
```

## 手元で credential JSON を書く場合

`--service-account` は付けない。

```bash
gcloud iam workload-identity-pools create-cred-config \
  "projects/${CURSOR_WIF_PROJECT_NUMBER}/locations/global/workloadIdentityPools/cursor/providers/oidc" \
  --subject-token-type=urn:ietf:params:oauth:token-type:id_token \
  --executable-command="$(pwd)/scripts/cursor-cloud/cursor-gcp-oidc" \
  --output-file="${HOME}/.config/gcloud/cursor-wif.json"
```

Cloud Agent では `setup-adc.sh` が同じ JSON を書く。

## スクリプト

| ファイル | 役割 |
|---|---|
| [`scripts/cursor-cloud/cursor-gcp-oidc`](../../scripts/cursor-cloud/cursor-gcp-oidc) | Google Auth が呼ぶ mint ヘルパー |
| [`scripts/cursor-cloud/setup-adc.sh`](../../scripts/cursor-cloud/setup-adc.sh) | `start` から呼び JSON を書く |

```bash
python3 scripts/cursor-cloud/tests/test_scripts.py
```

## うまくいかないとき

| 症状 | 見るところ |
|---|---|
| `executables need to be explicitly allowed` | `GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES` が `1` か |
| STS が audience 不一致 | JWT `aud` が canonical name か。`allowed_audiences` にカスタム値だけを入れてないか |
| mint は成功、GCS が 403 | `cursor_oidc_subjects` と JWT `sub` |
| `OIDC socket not found` | `/run/cursor/api.sock`。Cursor 管理 VM 以外では無い |
| credential JSON に `service_account_impersonation_url` がある | `--service-account` を付けて生成している |
