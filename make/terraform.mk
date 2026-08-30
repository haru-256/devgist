# Resolve paths from this included file so calls from any environment directory behave the same.
MAKE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
TERRAFORM_ROOT := $(abspath $(MAKE_DIR)/../infra/terraform)
TFLINT_CONFIG ?= $(TERRAFORM_ROOT)/.tflint.hcl
BACKEND_CONFIG ?= config.gcs.tfbackend
TRIVY_SEVERITY ?= HIGH,CRITICAL
# secrets.tfvars は *.auto.tfvars と違い自動では読まれない。あれば -var-file で渡す（INFRA-ADR-019）
SECRETS_TFVARS := $(wildcard secrets.tfvars)
SECRETS_VAR_FILE := $(if $(SECRETS_TFVARS),-var-file=$(SECRETS_TFVARS))

.PHONY: fmt
fmt: ## Format terraform recursively
	terraform fmt -recursive

.PHONY: lint
lint: ## Lint terraform and scan config
	tflint --recursive --config $(TFLINT_CONFIG)
	trivy config --severity=$(TRIVY_SEVERITY) $(if $(wildcard terraform.tfvars),--tf-vars=terraform.tfvars) ./

.PHONY: init
init: ## Initialize terraform
	terraform init -backend-config=$(BACKEND_CONFIG)

.PHONY: plan
plan: ## Run terraform plan
	terraform plan $(SECRETS_VAR_FILE)

.PHONY: apply
apply: ## Run terraform apply
	terraform apply $(SECRETS_VAR_FILE)
