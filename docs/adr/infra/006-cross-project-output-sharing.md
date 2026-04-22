# INFRA-ADR-006 Cross-project Terraform output 共有戦略

## Conclusion (結論)

- cross-project で共有する非 secret な値は、原則として `terraform_remote_state` で upstream project の `outputs` を参照する。
- `terraform_remote_state` の利用対象は非 secret 値に限定し、secret は Terraform outputs 経由で共有しない。
- secret は `GCP Secret Manager` で管理し、app project 側のアプリケーションランタイムが `Secret Manager` を参照して取得する。

## Status (ステータス)

Accepted

## Context (背景・課題)

### 背景

`INFRA-ADR-004` と `INFRA-ADR-005` により、DevGist の Terraform root module は `GCP project` ごとに分割し、service は `ops/app/data` に責務分解して扱う方針になった。

この構成では、別 project のリソース識別子を downstream 側で参照する場面が発生する。

例:

- `devgist-app` が `devgist-ops` の `Artifact Registry repository URL` を参照する
- `devgist-app` が `devgist-data` の `GCS bucket name` を参照する
- `devgist-app` が `devgist-data` の `Cloud SQL connection name` を参照する

ここで、どの方法で cross-project の値を共有するかを決める必要がある。

### 要件と制約

1. **silent success を避けたい**
   - 人手転記ミスや古い値の放置で、間違った既存リソースを参照したまま apply が成功する状態は避けたい
   - upstream の正しい値を downstream が直接参照できる形にしたい

2. **複雑な自動化を避けたい**
   - 初期フェーズで、CI/script による値同期や tfvars 生成の保守運用は避けたい
   - Terraform の仕組みの中で依存関係を閉じたい

3. **state 分離は維持したい**
   - root module と state は引き続き project ごとに分けたい
   - そのうえで、必要最小限の read 依存だけを許容したい

4. **secret を混ぜない**
   - secret を Terraform outputs や tfvars で project 間共有しない
   - secret は `Secret Manager` を正本としたい

5. **IAM を明示管理したい**
   - remote state の読み取り権限が必要になるため、IAM も Terraform で管理したい

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: `terraform_remote_state` | upstream を source of truth にして、自動追従したい場合 | 転記不要。upstream 変更に追従しやすい。Terraform 内で閉じる。 | state 間 read 依存が生じる。remote state 読み取り IAM が必要。 | 採用 |
| Option B: CI/script による自動同期 | 値配布を Terraform 外で自動化したい場合 | state を直接読ませずに済む。 | 自動化自体の保守が必要。初期フェーズには重い。 | 非採用 |
| Option C: variables + 手動更新 | 単純な構成で人手運用を許容する場合 | 実装が単純。state 間依存がない。 | 値の転記ミス・古い値の残留が起きやすい。silent success を防ぎにくい。 | 非採用 |

### 選定観点

- upstream の値を downstream が誤転記なしに使えるか
- 複雑な同期自動化なしで運用できるか
- state 分離を維持しながら依存を明示できるか
- secret を確実に分離できるか
- IAM を Terraform で追跡可能にできるか

## Considered Options

### Option A: `terraform_remote_state` を使う [採用]

upstream project の Terraform outputs を downstream project が `terraform_remote_state` で直接読む。

採用理由:

- **転記をなくせる**
  - `ops` や `data` の output を `app` がそのまま参照できる。
  - 人手で tfvars や変数にコピーする必要がなく、古い値が残る事故を減らせる。

- **source of truth が明確**
  - 値の正本は upstream project の Terraform output になる。
  - downstream 側は値を再定義せず、参照だけに徹することができる。

- **複雑な CI/script が不要**
  - 値の同期や配布を Terraform 外へ逃がさずに済む。
  - 個人開発の初期フェーズとして十分シンプルである。

- **state 分離と両立できる**
  - state 自体は project ごとに独立したまま保ち、必要最小限の read 依存だけを持てる。
  - `tf -> ops/data -> app` の apply 順序も明示しやすい。

### Option B: CI/script で値を自動同期する [却下]

upstream outputs を CI や wrapper script で収集し、downstream の tfvars などへ自動反映する。

却下理由:

- **自動化の保守コストが高い**
  - 値の配布ロジック自体を理解・保守する必要がある。
  - 初期フェーズとしては Terraform 本体より周辺運用が重くなりやすい。

- **source of truth が曖昧になる**
  - Terraform output ではなく CI/script 側に設計が逃げやすい。

### Option C: variables + 手動更新 [却下]

upstream の値を人手で tfvars や variables に転記し、downstream 側で受ける。

却下理由:

- **silent success のリスクがある**
  - typo や古い値のままでも、たまたま既存リソースを指していれば apply が通ってしまう可能性がある。

- **正本が分散しやすい**
  - upstream output と downstream variable のどちらが正か分かりにくくなる。

## Decision (決定事項)

DevGist の cross-project Terraform output 共有戦略として、`terraform_remote_state` を採用する。

### 採用方針

- `terraform_remote_state` の対象は非 secret な infrastructure identifiers に限定する
  - 例: `Artifact Registry repository URL`, `GCS bucket name`, `Cloud SQL connection name`

- downstream project は upstream project の `outputs` のみに依存する
  - upstream の内部 resource 名や state 内部構造に直接依存しない

- secret は Terraform outputs で共有しない
  - `GCP Secret Manager` を正本とする
  - app project 側のアプリケーションが runtime で `Secret Manager` を読む

- remote state を読むための IAM は Terraform 管理に含める
  - app の apply 実行主体が、必要な upstream state bucket を read できるようにする

- apply 順序は `tf -> ops/data -> app` を前提とする

### 値の種類ごとのルール

- **非 secret な共有値**
  - `terraform_remote_state` で upstream outputs を参照する

- **環境差分**
  - `gcp_project_id`, `region` など、state 共有と関係ない値は従来通り variables で受ける

- **安定した構成値**
  - `repository_id = "crawler"` など、project 内で完結する固定値は Terraform コードに明示してよい

- **secret**
  - `Secret Manager` で管理し、Terraform は secret 名や参照権限だけを扱う

### 参考実装

#### `ops` 側で output を公開する

```hcl
output "crawler_artifact_registry_repository_url" {
  value       = module.crawler_artifact_registry.repository_url
  description = "The Docker repository URL for crawler images"
}
```

#### `app` 側で `terraform_remote_state` を参照する

```hcl
data "terraform_remote_state" "ops" {
  backend = "gcs"
  config = {
    bucket = "haru256-devgist-ops-tfstate"
    prefix = "default"
  }
}

locals {
  crawler_repository_url = data.terraform_remote_state.ops.outputs.crawler_artifact_registry_repository_url
  crawler_image          = "${local.crawler_repository_url}/crawler:latest"
}
```

#### `data` 側の bucket 名を `app` が参照する

```hcl
data "terraform_remote_state" "data" {
  backend = "gcs"
  config = {
    bucket = "haru256-devgist-data-dev-tfstate"
    prefix = "default"
  }
}

locals {
  datalake_bucket_name = data.terraform_remote_state.data.outputs.datalake_bucket_name
}
```

#### secret は Terraform output で共有せず、アプリケーションが `Secret Manager` を参照する

```python
from google.cloud import secretmanager

def access_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
```

### 禁止事項

- secret を Terraform outputs や tfvars で共有すること
- downstream 側が upstream の内部 resource 名を直接決め打ちすること
- `terraform_remote_state` を無秩序に増やし、依存方向を曖昧にすること

### 再検討条件

- remote state 読み取り IAM や backend 依存の運用コストが高くなった場合
- 共有する値の数が増えすぎ、Terraform 間依存が複雑化した場合
- CI/CD を本格導入し、state 参照より pipeline orchestration の方が合理的になった場合

## Consequences (結果・影響)

### Positive (メリット)

- upstream の正しい値を downstream が直接参照できる
- 人手転記や tfvars 同期が不要になる
- 値の正本が Terraform outputs に一本化される
- 複雑な CI/script 自動化を初期フェーズで避けられる

### Negative (デメリット)

- remote state 読み取り用の cross-project IAM が必要になる
- backend bucket / prefix への依存が downstream 側に入る
- apply 順序を守る必要がある

### Risks / Future Review (将来の課題)

- backend 構成変更時に downstream の remote state 設定も追従が必要になる
- remote state 参照が増えすぎると、project 分離の見通しが悪くなる可能性がある
- outputs の設計が雑だと、upstream/downstream の境界が曖昧になる

## Next Steps

1. `ops`, `data`, `app` の各 root module で公開すべき非 secret outputs を整理する
2. `app` 側に `terraform_remote_state` の参照を追加する
3. remote state 読み取り IAM を Terraform 管理に含める
4. `infra/README.md` に apply 順序と remote state 参照関係を明記する
5. secret の runtime 参照方式を `Secret Manager` 前提で整備する

## Related Documents

- [INFRA-ADR-004] Terraform State Project と Ops Project を分離する
- [INFRA-ADR-005] Terraform environments は GCP project ごとに分割する
- [ADR運用ガイド](../../../docs/adr/README.md)
- [Infrastructure README](../../../infra/README.md)
