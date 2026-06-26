include ../../make/help.mk
include ../../make/python.mk

.DEFAULT_GOAL := help

IMAGE_TAG ?= $(shell git rev-parse --short HEAD)
REPO_URL ?= us-central1-docker.pkg.dev/haru256-devgist-ops/crawler
IMAGE_NAME ?= crawler
PLATFORM ?= linux/amd64
IMAGE := $(REPO_URL)/$(IMAGE_NAME):$(IMAGE_TAG)

.PHONY: build-push-image
build-push-image: ## Build, push, and print the digest image reference
	@IMAGE_TAG="$(IMAGE_TAG)" \
		REPO_URL="$(REPO_URL)" \
		IMAGE_NAME="$(IMAGE_NAME)" \
		PLATFORM="$(PLATFORM)" \
		./scripts/build-push-image.sh
