.PHONY: fmt
fmt: # format terraform
	terraform fmt -recursive

.PHONY: lint
lint: # lint terraform
	tflint --recursive --config ../../../.tflint.hcl
	trivy config --severity=HIGH,CRITICAL --tf-vars=terraform.tfvars ./
