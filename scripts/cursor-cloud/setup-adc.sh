#!/usr/bin/env bash
set -euo pipefail

# Write the WIF credential config for Cursor Cloud ADC. Env vars for ADC
# come from Cursor Secrets, not from this script.

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

python3 - "${audience}" "${mint}" "${config_path}" <<'PY'
import json
import sys
from pathlib import Path

audience, executable, output = sys.argv[1], sys.argv[2], sys.argv[3]
path = Path(output)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    json.dumps(
        {
            "type": "external_account",
            "audience": audience,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "token_url": "https://sts.googleapis.com/v1/token",
            "universe_domain": "googleapis.com",
            "credential_source": {
                "executable": {
                    "command": executable,
                    "timeout_millis": 10000,
                }
            },
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"wrote {path}", file=sys.stderr)
PY

printf 'ADC config: %s\n' "${config_path}"
