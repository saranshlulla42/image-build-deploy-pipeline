#!/usr/bin/env bash
# Explicit context, image digest and expected source commit are required.
set -euo pipefail
exec python3 scripts/release.py "$@"
