#!/usr/bin/env bash
# recovery_seconds is written to artifacts/failed-release.json; no fabricated threshold pass.
set -euo pipefail
exec python3 scripts/integration_demo.py --scenario rollback "$@"
