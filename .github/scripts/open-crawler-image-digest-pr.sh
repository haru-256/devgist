#!/usr/bin/env bash
set -euo pipefail

# app-dev tfvars の crawler_image を更新し、digest PR を作成または更新する。
#
# 必須 env: IMAGE_REF, GH_TOKEN
# 任意 env: SOURCE_SHA, RUN_URL
# origin への push と GitHub API が使えること。
#
# ブランチ ci/crawler-image-digest は毎回 origin/main から作り直す。
# tfvars がすでに IMAGE_REF なら no-op。

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

# actions/checkout は remote.origin.fetch を main に狭める。
# origin/main を更新し、digest ブランチは origin/<branch> へ明示マップする。
# 素の `git fetch origin <branch>` は FETCH_HEAD だけ更新し、lease 用の
# tracking ref が立たない。初回はリモートにブランチが無いので失敗してよい。
printf 'Resetting %s from origin/main\n' "${BRANCH}"
git fetch origin main
git fetch origin "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" || true
# 毎回 origin/main から作り直す。upstream を origin/main に付けると、
# 引数なしの --force-with-lease が dest を main の SHA と比べて stale になる。
git checkout --no-track -B "${BRANCH}" origin/main

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
# --force-with-lease=<dest>:<expect>。expect は「リモート dest はまだこの SHA」。
# tracking ref があればそれを expect にする。無ければ空 expect（未作成）で作る。
# 引数なしの --force-with-lease は local upstream を見るので使わない。
if git rev-parse --verify "refs/remotes/origin/${BRANCH}" >/dev/null 2>&1; then
  git push --force-with-lease="refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" \
    origin "HEAD:${BRANCH}"
else
  git push --force-with-lease="refs/heads/${BRANCH}:" origin "HEAD:${BRANCH}"
fi

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
