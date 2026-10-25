#!/usr/bin/env bash
# Requires --context kind-NAME --image demo-app:TAG --version FULL_COMMIT.
set -euo pipefail
exec python3 scripts/integration_demo.py --scenario failure "$@"
