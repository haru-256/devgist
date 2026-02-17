.PHONY: fmt
fmt: # format terraform
	terraform fmt -recursive

.PHONY: lint
lint: # lint terraform
	tflint --recursive --config $(TFLINT_CONFIG)
	trivy config --severity=HIGH,CRITICAL --tf-vars=terraform.tfvars ./
