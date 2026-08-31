# 非 secret の設定値のみ。principal identifier（cursor_oidc_subjects、
# service_account_user_emails）も true secret ではないのでここに書く（INFRA-ADR-020）
gcp_project_id     = "haru256-devgist-ops"
gcp_default_region = "us-central1"

# Cursor Cloud の user id（sub）。空なら datalake IAM member が付かない
cursor_oidc_subjects = ["user:308716925"]

# managed SA を attach / actAs できるユーザー
service_account_user_emails = ["yohei.okabayashi@haru256.dev", "admin@haru256.dev"]
