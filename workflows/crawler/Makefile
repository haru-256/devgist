include ../../make/help.mk
include ../../make/python.mk

.DEFAULT_GOAL := help

IMAGE_TAG ?= $(shell git rev-parse --short HEAD)
REPO_URL ?= us-central1-docker.pkg.dev/haru256-devgist-ops/crawler
IMAGE_NAME ?= crawler
IMAGE := $(REPO_URL)/$(IMAGE_NAME):$(IMAGE_TAG)

.PHONY: build-push-image
build-push-image: ## Build, push, and print the digest image reference
	docker build -t "$(IMAGE)" .
	docker push "$(IMAGE)"
	@digest=$$(docker inspect --format='{{index .RepoDigests 0}}' "$(IMAGE)" | cut -d'@' -f2); \
	if ! printf '%s\n' "$${digest}" | grep -Eq '^sha256:[a-f0-9]{64}$$'; then \
		printf 'Failed to resolve pushed image digest for %s\n' "$(IMAGE)" >&2; \
		exit 1; \
	fi; \
	image_ref="$(REPO_URL)/$(IMAGE_NAME)@$${digest}"; \
	printf 'image_ref: %s\n' "$${image_ref}"
