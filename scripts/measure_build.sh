#!/usr/bin/env bash
# Measures observed local builds. --no-cache does not evict the base image.
set -euo pipefail
SOURCE_COMMIT=$(git rev-parse HEAD)
export SOURCE_COMMIT
python3 - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import time

samples = []
for attempt in range(1, 4):
    for mode, flags in [("no-layer-cache", ["--no-cache"]), ("warm-cache", [])]:
        started = time.monotonic()
        subprocess.run(["docker", "build", *flags, "--build-arg",
                        "SOURCE_COMMIT=" + os.environ["SOURCE_COMMIT"],
                        "-t", "demo-app:benchmark", "."], check=True)
        samples.append({"attempt": attempt, "mode": mode,
                        "seconds": round(time.monotonic() - started, 3)})
output = Path("artifacts/build-benchmark.json")
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({"samples": samples}, indent=2) + "\n")
print(output.read_text())
PY
