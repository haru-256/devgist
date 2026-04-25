locals {
  service_account_names = keys(var.service_accounts)

  # upstream module は description を names と同じ順序の list として受け取るため、
  # service_account_names から作った順序を保って対応関係が崩れないようにする。
  service_account_descriptions = [
    for name in local.service_account_names :
    var.service_accounts[name].description == null ? "" : var.service_accounts[name].description
  ]

  # project_roles は「各 SA が何をできるか」を表す。
  # upstream module の project_roles は全 SA 共通なので、SA ごとの差分はこの module で扱う。
  project_role_bindings = {
    for binding in flatten([
      for sa_name, sa in var.service_accounts : [
        for role_binding in sa.project_roles : {
          sa_name = sa_name
          project = role_binding.project
          role    = role_binding.role
        }
      ]
    ]) :
    "${binding.sa_name}|${binding.project}|${binding.role}" => binding
  }

  # Service Account IAM は「誰がその SA を使えるか」を表す。
  # member は user:name@example.com のような IAM member 形式で渡す。
  token_creator_bindings = flatten([
    for sa_name, sa in var.service_accounts : [
      for member in sa.token_creators : {
        sa_name = sa_name
        role    = "roles/iam.serviceAccountTokenCreator"
        member  = member
      }
    ]
  ])

  service_account_user_bindings = flatten([
    for sa_name, sa in var.service_accounts : [
      for member in sa.service_account_users : {
        sa_name = sa_name
        role    = "roles/iam.serviceAccountUser"
        member  = member
      }
    ]
  ])

  service_account_iam_bindings = {
    for binding in concat(
      local.token_creator_bindings,
      local.service_account_user_bindings,
    ) :
    "${binding.sa_name}|${binding.role}|${binding.member}" => binding
  }
}

module "service_accounts" {
  source  = "terraform-google-modules/service-accounts/google"
  version = "~> 4.7.0"

  project_id   = var.project_id
  prefix       = var.prefix
  names        = local.service_account_names
  descriptions = local.service_account_descriptions

  # SAごとに role を変えたいので、この module の project_roles は使わない。
  project_roles = []

  # 秘密鍵は原則作らない。WIF / impersonation を使う。
  generate_keys = false
}

# SA 自身に権限を付与する。例: Artifact Registry writer/reader や
# deploy 対象 project への権限。
resource "google_project_iam_member" "project_roles" {
  for_each = local.project_role_bindings

  project = each.value.project
  role    = each.value.role
  member  = "serviceAccount:${module.service_accounts.service_accounts_map[each.value.sa_name].email}"
}

# principal に SA を使う権限を付与する。上の project_roles とは別物で、
# こちらは SA に対する actAs / impersonation を制御する。
resource "google_service_account_iam_member" "service_account_iam" {
  for_each = local.service_account_iam_bindings

  service_account_id = module.service_accounts.service_accounts_map[each.value.sa_name].name
  role               = each.value.role
  member             = each.value.member
}
