# 非 secret 値のみ。secret 値（cursor_oidc_subjects、service_account_user_emails）は
# secrets.tfvars（local、gitignore 済み）か TF_VAR_*（CI。repository secret は
# devgist-github root が書く）で渡す（INFRA-ADR-019）
gcp_project_id     = "haru256-devgist-ops"
gcp_default_region = "us-central1"
