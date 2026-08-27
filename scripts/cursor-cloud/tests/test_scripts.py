#!/usr/bin/env python3
"""Checks for Cursor Cloud WIF helpers. Stdlib only."""

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINT = ROOT / "cursor-gcp-oidc"
SETUP = ROOT / "setup-adc.sh"
AUDIENCE = (
    "//iam.googleapis.com/projects/123456789012/locations/global/"
    "workloadIdentityPools/cursor/providers/oidc"
)


def run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(args, text=True, capture_output=True, env=merged)


class HelpersTest(unittest.TestCase):
    _sockets: list[socket.socket] = []

    def test_setup_adc_writes_direct_access_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run(
                [str(SETUP)],
                {"HOME": str(home), "CURSOR_WIF_PROJECT_NUMBER": "123456789012"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(
                (home / ".config/gcloud/cursor-wif.json").read_text()
            )
            self.assertNotIn("service_account_impersonation_url", config)
            self.assertEqual(config["audience"], AUDIENCE)
            self.assertEqual(
                config["credential_source"]["executable"]["command"], str(MINT)
            )

    def test_mint_forwards_audience(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            socket_path = tmp_path / "api.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(socket_path))
            self._sockets.append(server)
            stub_dir = tmp_path / "bin"
            stub_dir.mkdir()
            fixture = tmp_path / "mint.json"
            request_log = tmp_path / "request.json"
            fixture.write_text(
                json.dumps({"token": "header.payload.sig", "expires_at": 1_700_000_000})
                + "\n"
            )
            stub = stub_dir / "curl"
            stub.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
payload=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d) payload="$2"; shift 2 ;;
    --unix-socket|-H) shift 2 ;;
    --fail|-sS|-s) shift ;;
    *) shift ;;
  esac
done
printf '%s\\n' "${{payload}}" > {request_log.as_posix()!r}
cat {fixture.as_posix()!r}
"""
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            result = run(
                [str(MINT)],
                {
                    "PATH": f"{stub_dir}:{os.environ['PATH']}",
                    "GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE": AUDIENCE,
                    "CURSOR_AGENT_SOCKET": str(socket_path),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(body["id_token"], "header.payload.sig")
            self.assertEqual(json.loads(request_log.read_text())["aud"], AUDIENCE)


if __name__ == "__main__":
    unittest.main()
