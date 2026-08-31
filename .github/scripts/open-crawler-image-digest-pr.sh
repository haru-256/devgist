#!/usr/bin/env bash
set -euo pipefail

# Update crawler_image in app-dev tfvars and open or update a digest PR.
#
# Required env: IMAGE_REF, GH_TOKEN
# Optional env: SOURCE_SHA, RUN_URL
# Caller must be able to push to origin and call the GitHub API.
#
# Branch is always reset from origin/main (ci/crawler-image-digest).
# No-op when tfvars already has IMAGE_REF.

IMAGE_REF="${IMAGE_REF:?IMAGE_REF is required}"
GH_TOKEN="${GH_TOKEN:?GH_TOKEN is required}"
SOURCE_SHA="${SOURCE_SHA:-}"
RUN_URL="${RUN_URL:-}"

BRANCH="ci/crawler-image-digest"
TFVARS_REL="infra/terraform/environments/devgist-app/dev/terraform.tfvars"
COMMIT_MSG="chore(infra): bump crawler Cloud Run image digest"
if [[ -n "${SOURCE_SHA}" ]]; then
  COMMIT_MSG="${COMMIT_MSG} (${SOURCE_SHA})"
fi
PR_TITLE="${COMMIT_MSG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BODY_TEMPLATE="${SCRIPT_DIR}/crawler-image-digest-pr.md"
TFVARS="${REPO_ROOT}/${TFVARS_REL}"

if ! [[ "${IMAGE_REF}" =~ @sha256:[a-f0-9]{64}$ ]]; then
  printf 'invalid IMAGE_REF: %s\n' "${IMAGE_REF}" >&2
  exit 1
fi

cd "${REPO_ROOT}"

printf 'Resetting %s from origin/main\n' "${BRANCH}"
git fetch origin main
# Lease compares against origin/<branch>. actions/checkout does not fetch it.
git fetch origin "${BRANCH}" 2>/dev/null || true
git checkout -B "${BRANCH}" origin/main

matches="$(grep -c -E '^crawler_image[[:space:]]*=' "${TFVARS}" || true)"
if [[ "${matches}" != 1 ]]; then
  printf 'expected 1 crawler_image assignment in %s, found %s\n' "${TFVARS_REL}" "${matches}" >&2
  exit 1
fi

current="$(sed -n -E 's/^crawler_image[[:space:]]*=[[:space:]]*"([^"]*)".*/\1/p' "${TFVARS}")"
if [[ "${current}" == "${IMAGE_REF}" ]]; then
  printf 'crawler_image already matches %s; nothing to do\n' "${IMAGE_REF}"
  exit 0
fi

printf 'Updating %s\n' "${TFVARS_REL}"
sed -i -E "s|^(crawler_image[[:space:]]*=[[:space:]]*)\"[^\"]*\"$|\\1\"${IMAGE_REF}\"|" "${TFVARS}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -- "${TFVARS}"
git commit -m "${COMMIT_MSG}"
git push --force-with-lease origin "HEAD:${BRANCH}"

body="$(sed \
  -e "s|{{IMAGE_REF}}|${IMAGE_REF}|g" \
  -e "s|{{SOURCE_SHA}}|${SOURCE_SHA}|g" \
  -e "s|{{RUN_URL}}|${RUN_URL}|g" \
  "${BODY_TEMPLATE}")"

pr_url="$(gh pr list --head "${BRANCH}" --base main --state open --json url --jq '.[0].url // empty')"
if [[ -n "${pr_url}" ]]; then
  gh pr edit "${pr_url}" --title "${PR_TITLE}" --body "${body}"
  printf 'Updated existing PR: %s\n' "${pr_url}"
  exit 0
fi

gh pr create --base main --head "${BRANCH}" --title "${PR_TITLE}" --body "${body}"
