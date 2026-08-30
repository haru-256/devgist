# 非 secret 値のみ。secret 値（cursor_oidc_subjects、service_account_user_emails）は
# secrets.auto.tfvars（local、gitignore 済み）か TF_VAR_*（CI）で渡す（INFRA-ADR-019）
gcp_project_id     = "haru256-devgist-ops"
gcp_default_region = "us-central1"
