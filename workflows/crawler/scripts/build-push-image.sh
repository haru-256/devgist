#!/usr/bin/env bash
set -euo pipefail

# Build and push the crawler image, then print the immutable digest reference.
#
# Required env: IMAGE_TAG, REPO_URL, IMAGE_NAME, PLATFORM
# Caller must already be authenticated to push to REPO_URL.
# PLATFORM must be a single value; --load cannot load a multi-platform manifest.
#
# stdout: image_ref: <repo>/<name>@sha256:<digest>
# stderr: docker build/push progress

IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"
REPO_URL="${REPO_URL:?REPO_URL is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
PLATFORM="${PLATFORM:?PLATFORM is required}"

CRAWLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_REF="${REPO_URL}/${IMAGE_NAME}"
TAGGED_IMAGE="${IMAGE_REF}:${IMAGE_TAG}"

if [[ "${PLATFORM}" == *,* ]]; then
  printf 'Error: PLATFORM must be a single platform for --load (got: %s)\n' "${PLATFORM}" >&2
  exit 1
fi

docker buildx build --platform "${PLATFORM}" -t "${TAGGED_IMAGE}" --load "${CRAWLER_DIR}" >&2
docker push "${TAGGED_IMAGE}" >&2

repo_digest="$(docker image inspect -f '{{index .RepoDigests 0}}' "${TAGGED_IMAGE}")"
digest="${repo_digest#*@}"
if ! [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  printf 'Failed to resolve image digest for %s (got: %s)\n' "${TAGGED_IMAGE}" "${digest}" >&2
  exit 1
fi
printf 'image_ref: %s@%s\n' "${IMAGE_REF}" "${digest}"
