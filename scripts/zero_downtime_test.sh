#!/usr/bin/env bash
# Usage: bash scripts/zero_downtime_test.sh --url NODEPORT_URL -- <release command>
set -euo pipefail
exec python3 scripts/traffic_probe.py "$@"
