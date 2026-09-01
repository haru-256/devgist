# 非 secret の設定値のみ。service_account_user_emails も true secret ではないので
# ここに書く（INFRA-ADR-020）
gcp_project_id     = "haru256-devgist-app-dev"
gcp_default_region = "us-central1"

# managed SA を attach / actAs できるユーザー
service_account_user_emails = ["yohei.okabayashi@haru256.dev", "admin@haru256.dev"]

# crawler image の digest。crawler-deploy が main で push した image に合わせ、
# digest を書き換える infra PR で更新する（INFRA-ADR-019）
crawler_image = "us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@sha256:c85e37e684a28dafb5ac45c9329951584cd268eb07b9e6795b17bf453efc2590"
