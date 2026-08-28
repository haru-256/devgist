#!/usr/bin/env bash
set -euo pipefail

# Write the WIF credential config for Cursor Cloud ADC.
# CURSOR_WIF_PROJECT_NUMBER comes from a Cursor Secret whose type is
# Environment Variable, not Runtime Secret or Build Secret.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_number="${CURSOR_WIF_PROJECT_NUMBER:-}"
mint="${SCRIPT_DIR}/cursor-gcp-oidc"
config_path="${HOME}/.config/gcloud/cursor-wif.json"

if [[ -z "${project_number}" ]]; then
  printf 'CURSOR_WIF_PROJECT_NUMBER is not set (ops terraform output ops_project_number)\n' >&2
  exit 1
fi
if [[ ! "${project_number}" =~ ^[0-9]+$ ]]; then
  printf 'CURSOR_WIF_PROJECT_NUMBER must be digits, got: %s\n' "${project_number}" >&2
  exit 1
fi
if [[ ! -x "${mint}" ]]; then
  printf 'mint helper is not executable: %s\n' "${mint}" >&2
  exit 1
fi

audience="//iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/cursor/providers/oidc"

mkdir -p "$(dirname "${config_path}")"
cat >"${config_path}" <<EOF
{
  "type": "external_account",
  "audience": "${audience}",
  "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
  "token_url": "https://sts.googleapis.com/v1/token",
  "universe_domain": "googleapis.com",
  "credential_source": {
    "executable": {
      "command": "${mint}",
      "timeout_millis": 10000
    }
  }
}
EOF

printf 'ADC config: %s\n' "${config_path}"
