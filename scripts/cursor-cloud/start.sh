#!/usr/bin/env bash
set -euo pipefail

# Cursor Cloud Agent `start` entrypoint.
#
# 1. ADC / WIF wiring is mandatory: if it fails the boot must fail, because
#    everything downstream (GCS, crawler) depends on it.
# 2. CodeRabbit CLI auth is best-effort: it must never break the boot. The
#    CLI needs an *agentic* API key; a user API key returns a non-zero exit,
#    which previously made `start` fail even though ADC was fine.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/setup-adc.sh"

if [[ -n "${CODERABBIT_API_KEY:-}" ]]; then
  if coderabbit auth login --api-key "${CODERABBIT_API_KEY}"; then
    printf 'coderabbit auth login: ok\n'
  else
    printf 'coderabbit auth login failed (non-fatal); CODERABBIT_API_KEY must be an agentic API key\n' >&2
  fi
else
  printf 'CODERABBIT_API_KEY not set; skipping coderabbit auth login\n'
fi
