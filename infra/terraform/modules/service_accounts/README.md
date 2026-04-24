# service_accounts

Google Cloud service accounts を作成し、Service Account 自身の権限と、Service Account を利用できる principal をまとめて管理する wrapper module です。

内部では公式 module [`terraform-google-modules/service-accounts/google`](https://registry.terraform.io/modules/terraform-google-modules/service-accounts/google/latest) を利用します。DevGist 側では、SA ごとに異なる project role と `roles/iam.serviceAccountUser` / `roles/iam.serviceAccountTokenCreator` を同じ入力で扱えるように薄く包んでいます。

## 役割

- Service Account を複数作成する
- SA ごとに project role を付与する
- SA ごとに `roles/iam.serviceAccountUser` を付与する
- SA ごとに `roles/iam.serviceAccountTokenCreator` を付与する
- Service Account key は作成しない

## 入力例

```hcl
module "service_accounts" {
  source = "../../modules/service_accounts"

  project_id = "haru256-devgist-ops"

  service_accounts = {
    github-actions = {
      description = "Service account used by GitHub Actions for DevGist CI/CD"

      project_roles = [
        {
          project = "haru256-devgist-ops"
          role    = "roles/artifactregistry.writer"
        }
      ]

      service_account_users = [
        "user:admin@example.com",
      ]
    }
  }
}
```

## IAM の考え方

`project_roles` は **Service Account が何をできるか** を定義します。たとえば Artifact Registry へ push する SA には `roles/artifactregistry.writer` を付与します。

`service_account_users` と `token_creators` は **誰がその Service Account を使えるか** を定義します。Cloud Run Jobs などに SA を attach / actAs できればよい場合は `service_account_users` を使います。短命 token を発行して impersonation する必要がある場合だけ `token_creators` を使います。

## 注意点

- `service_account_users` と `token_creators` は `user:...`, `group:...`, `serviceAccount:...` のような IAM member 形式で渡します。
- 人間ユーザーのメールアドレスなど repository 管理外にしたい値は、root module 側の untracked `terraform.tfvars` から渡してください。
- この module は Service Account key を作成しません。CI/CD やローカル実行では WIF または impersonation を使う前提です。

## Outputs

| Name | Description |
|---|---|
| `emails` | Service Account email by logical name |
| `iam_emails` | `serviceAccount:<email>` member string by logical name |
| `members` | `iam_emails` と同じ形式の互換 output |
| `names` | Full Service Account resource name by logical name |
