#!/usr/bin/env bash
set -euo pipefail

# Build and push the crawler image, then print the immutable digest reference.
# Authentication is the caller's responsibility.

IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"
REPO_URL="${REPO_URL:?REPO_URL is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
PLATFORM="${PLATFORM:?PLATFORM is required}"

CRAWLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${REPO_URL}/${IMAGE_NAME}:${IMAGE_TAG}"

if [[ "${PLATFORM}" == *,* ]]; then
  printf 'Error: PLATFORM must be a single platform for --load (got: %s)\n' "${PLATFORM}" >&2
  exit 1
fi

docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --load "${CRAWLER_DIR}"
docker push "${IMAGE}"

digest="$(docker inspect --format='{{join .RepoDigests "\n"}}' "${IMAGE}" | head -n 1 | sed 's/.*@//')"
if [[ -z "${digest}" ]]; then
  printf 'Failed to resolve image digest for %s\n' "${IMAGE}" >&2
  exit 1
fi
if ! [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  printf 'Invalid digest format: %s\n' "${digest}" >&2
  exit 1
fi
printf 'image_ref: %s@%s\n' "${REPO_URL}/${IMAGE_NAME}" "${digest}"
