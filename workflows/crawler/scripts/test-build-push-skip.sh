#!/usr/bin/env bash
# Local check: when Artifact Registry already has the tag, build-push-image.sh
# must print image_ref and must not invoke docker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${ROOT}/scripts/build-push-image.sh"
FAKE_BIN="$(mktemp -d)"
DIGEST="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
trap 'rm -rf "${FAKE_BIN}"' EXIT

write_gcloud() {
  local mode="$1"
  cat >"${FAKE_BIN}/gcloud" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ "\${1:-}" == "artifacts" && "\${2:-}" == "docker" && "\${3:-}" == "images" && "\${4:-}" == "describe" ]]; then
  if [[ "${mode}" == "hit" ]]; then
    printf '%s\\n' "${DIGEST}"
    exit 0
  fi
  echo "NOT_FOUND" >&2
  exit 1
fi
echo "unexpected gcloud invocation: \$*" >&2
exit 1
EOF
  chmod +x "${FAKE_BIN}/gcloud"
}

write_docker() {
  cat >"${FAKE_BIN}/docker" <<EOF
#!/usr/bin/env bash
printf '%s\\n' "\$*" >>"${FAKE_BIN}/docker.log"
exit 42
EOF
  chmod +x "${FAKE_BIN}/docker"
}

run_script() {
  IMAGE_TAG="already-there" \
    REPO_URL="us-central1-docker.pkg.dev/haru256-devgist-ops/crawler" \
    IMAGE_NAME="crawler" \
    PLATFORM="linux/amd64" \
    PATH="${FAKE_BIN}:${PATH}" \
    "${SCRIPT}"
}

write_gcloud hit
write_docker
output="$(run_script 2>&1)"
printf '%s\n' "${output}"
echo "${output}" | grep -q "Reusing existing tag"
echo "${output}" | grep -q "image_ref: us-central1-docker.pkg.dev/haru256-devgist-ops/crawler/crawler@${DIGEST}"
if [[ -e "${FAKE_BIN}/docker.log" ]]; then
  echo "docker was invoked on a cache hit" >&2
  cat "${FAKE_BIN}/docker.log" >&2
  exit 1
fi
echo "ok: cache hit does not invoke docker"

write_gcloud miss
rm -f "${FAKE_BIN}/docker.log"
set +e
miss_output="$(run_script 2>&1)"
miss_status=$?
set -e
printf '%s\n' "${miss_output}"
if [[ "${miss_status}" -eq 0 ]]; then
  echo "expected docker to run and fail when the tag is missing" >&2
  exit 1
fi
if [[ ! -e "${FAKE_BIN}/docker.log" ]]; then
  echo "docker was not invoked on a cache miss" >&2
  exit 1
fi
grep -q "buildx" "${FAKE_BIN}/docker.log"
echo "ok: cache miss invokes docker"
