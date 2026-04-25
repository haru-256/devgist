output "emails" {
  description = "Service account emails by logical name."
  value = {
    for name, sa in module.service_accounts.service_accounts_map :
    name => sa.email
  }
}



output "members" {
  description = "Service account IAM member strings by logical name."
  value = {
    for name, sa in module.service_accounts.service_accounts_map :
    name => "serviceAccount:${sa.email}"
  }
}

output "names" {
  description = "Service account resource names by logical name."
  value = {
    for name, sa in module.service_accounts.service_accounts_map :
    name => sa.name
  }
}
