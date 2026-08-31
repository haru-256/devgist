# 非 secret 値のみ（INFRA-ADR-019）
gcp_project_id     = "haru256-devgist-tf"
gcp_default_region = "us-central1"

# 対象ごとに tfstate bucket を作る。bucket 名は <id>-tfstate。実体は tf project に置く。
# haru256-devgist-github は GCP project ではなく github root 用の論理 id（INFRA-ADR-019）
tfstate_gcp_project_ids = [
  "haru256-devgist-tf",
  "haru256-devgist-ops",
  "haru256-devgist-data-dev",
  "haru256-devgist-app-dev",
  "haru256-devgist-github",
]
