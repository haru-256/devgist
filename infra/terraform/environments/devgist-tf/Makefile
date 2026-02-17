.DEFAULT_GOAL := help
TFLINT_CONFIG := ../../.tflint.hcl
include ../../scripts/common.mk

.PHONY: init
init: # initialize terraform
	terraform init -backend-config=config.gcs.tfbackend

.PHONY: plan
plan: # plan terraform
	terraform plan

.PHONY: apply
apply: # apply terraform
	terraform apply

.PHONY: help
help: # Show help for each of the Makefile recipes.
	@grep -h -E '^[a-zA-Z0-9 -]+:.*#' $(MAKEFILE_LIST) | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done
