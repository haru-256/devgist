#!/usr/bin/env bash
set -euo pipefail

# Build and push the crawler image, then print the immutable digest reference.
#
# This script is intentionally usable from both the Makefile and future
# GitHub Actions workflows. Authentication is expected to be prepared by the
# caller, for example with gcloud/docker login before invoking this script.

IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"
REPO_URL="${REPO_URL:?REPO_URL is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
PLATFORM="${PLATFORM:?PLATFORM is required}"

# The tag is convenient for building and pushing, but it is mutable. Terraform
# should receive the digest-based reference printed at the end of this script.
IMAGE="${REPO_URL}/${IMAGE_NAME}:${IMAGE_TAG}"

# docker buildx --load can only load a single-platform image into the local
# Docker daemon. Reject comma-separated platform lists before build starts.
if [[ "${PLATFORM}" == *,* ]]; then
  printf 'Error: PLATFORM must be a single platform for --load (got: %s)\n' "${PLATFORM}" >&2
  exit 1
fi

# Build the image for the requested platform and load it into the local Docker
# daemon so it can be pushed and inspected by the following steps.
docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --load .

# Push the mutable tag to Artifact Registry. The registry records the immutable
# content digest, which we resolve from Docker metadata below.
docker push "${IMAGE}"

# Resolve the pushed digest from RepoDigests and strip the repository prefix so
# only the sha256 digest remains, matching Terraform's expected image format.
digest="$(docker inspect --format='{{join .RepoDigests "\n"}}' "${IMAGE}" | head -n 1 | sed 's/.*@//')"

if [[ -z "${digest}" ]]; then
  printf 'Failed to resolve pushed image digest for %s\n' "${IMAGE}" >&2
  exit 1
fi

# Keep this validation aligned with Terraform's crawler_image validation, which
# expects the final image reference to end with @sha256:<64 lowercase hex chars>.
if ! [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  printf 'Invalid digest format: %s\n' "${digest}" >&2
  exit 1
fi

image_ref="${REPO_URL}/${IMAGE_NAME}@${digest}"
printf 'image_ref: %s\n' "${image_ref}"
