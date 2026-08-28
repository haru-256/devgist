#!/usr/bin/env bash
set -euo pipefail

# Build and push the crawler image, then print the immutable digest reference.
#
# This script is used from the Makefile and from GitHub Actions. Authentication
# is expected to be prepared by the caller, for example with gcloud/docker
# login before invoking this script.

IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"
REPO_URL="${REPO_URL:?REPO_URL is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
PLATFORM="${PLATFORM:?PLATFORM is required}"

# Resolve the crawler directory relative to this script so the build context is
# independent of the caller's current working directory. This lets the script be
# reused from the Makefile, from repo root, or from GitHub Actions without
# accidentally building the wrong context.
CRAWLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The tag is convenient for building and pushing, but it is mutable. Terraform
# should receive the digest-based reference printed at the end of this script.
IMAGE="${REPO_URL}/${IMAGE_NAME}:${IMAGE_TAG}"

print_image_ref() {
  local digest="$1"
  if [[ -z "${digest}" ]]; then
    printf 'Failed to resolve image digest for %s\n' "${IMAGE}" >&2
    exit 1
  fi
  if ! [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    printf 'Invalid digest format: %s\n' "${digest}" >&2
    exit 1
  fi
  printf 'image_ref: %s@%s\n' "${REPO_URL}/${IMAGE_NAME}" "${digest}"
}

is_image_not_found() {
  grep -qiE 'NOT_FOUND|not found|failed to find image' <<<"$1"
}

# stdout: digest when found. exit 0 found, 2 missing, 1 error.
lookup_existing_digest() {
  local err_file out status digest
  if ! command -v gcloud >/dev/null 2>&1; then
    printf 'gcloud is required to look up %s\n' "${IMAGE}" >&2
    return 1
  fi
  err_file="$(mktemp)"
  set +e
  out="$(gcloud artifacts docker images describe "${IMAGE}" --format='value(image_summary.digest)' 2>"${err_file}")"
  status=$?
  set -e
  if [[ "${status}" -eq 0 ]]; then
    digest="$(tr -d '[:space:]' <<<"${out}")"
    rm -f "${err_file}"
    if ! [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
      printf 'Invalid digest from Artifact Registry for %s: %s\n' "${IMAGE}" "${digest}" >&2
      return 1
    fi
    printf '%s\n' "${digest}"
    return 0
  fi
  if is_image_not_found "$(cat "${err_file}")"; then
    rm -f "${err_file}"
    return 2
  fi
  printf 'gcloud artifacts docker images describe failed for %s\n' "${IMAGE}" >&2
  cat "${err_file}" >&2
  rm -f "${err_file}"
  return 1
}

# Skip rebuild when this tag already exists in Artifact Registry. The tag is
# still mutable; Terraform consumes the digest printed below. If gcloud is
# missing, fall through to docker so a local daemon-only build can still run.
if command -v gcloud >/dev/null 2>&1; then
  existing_digest=""
  lookup_status=0
  set +e
  existing_digest="$(lookup_existing_digest)"
  lookup_status=$?
  set -e
  if [[ "${lookup_status}" -eq 0 ]]; then
    printf 'Reusing existing tag %s\n' "${IMAGE}" >&2
    print_image_ref "${existing_digest}"
    exit 0
  fi
  if [[ "${lookup_status}" -ne 2 ]]; then
    exit "${lookup_status}"
  fi
fi

# docker buildx --load can only load a single-platform image into the local
# Docker daemon. Reject comma-separated platform lists before build starts.
if [[ "${PLATFORM}" == *,* ]]; then
  printf 'Error: PLATFORM must be a single platform for --load (got: %s)\n' "${PLATFORM}" >&2
  exit 1
fi

# Build the image for the requested platform and load it into the local Docker
# daemon so it can be pushed and inspected by the following steps.
docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --load "${CRAWLER_DIR}"

# Push the mutable tag to Artifact Registry. The registry records the immutable
# content digest, which we resolve from Docker metadata below.
docker push "${IMAGE}"

# Resolve the pushed digest from RepoDigests and strip the repository prefix so
# only the sha256 digest remains, matching Terraform's expected image format.
digest="$(docker inspect --format='{{join .RepoDigests "\n"}}' "${IMAGE}" | head -n 1 | sed 's/.*@//')"
print_image_ref "${digest}"
