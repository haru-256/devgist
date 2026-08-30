# 非 secret 値のみ。service_account_user_emails は
# secrets.auto.tfvars（local、gitignore 済み）か TF_VAR_*（CI）で渡す（INFRA-ADR-019）
gcp_project_id     = "haru256-devgist-app-dev"
gcp_default_region = "us-central1"

# crawler image の digest。crawler-deploy が main で push した image に合わせ、
# digest を書き換える infra PR で更新する（INFRA-ADR-019）
crawler_image = "us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@sha256:bdb4626f3a6352d93b33ee39846610151e8060165b99921a1d0877f57ae314b4"
