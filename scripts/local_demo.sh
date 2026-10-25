#!/usr/bin/env bash
# Run from the repository root with the virtual environment activated.
set -euo pipefail
command -v docker >/dev/null
command -v kind >/dev/null
command -v kubectl >/dev/null
docker info >/dev/null
if ! kind get clusters | tr -d '\r' | grep -qx pipeline-demo; then
  kind create cluster --name pipeline-demo --config k8s/kind.yaml \
    --image kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5 --wait 120s
fi
SOURCE_COMMIT=$(git rev-parse HEAD)
if [ -n "$(git status --porcelain --untracked-files=all -- app Dockerfile)" ]; then
  echo "Commit application/container changes before building a traceable release." >&2
  exit 1
fi
docker build --provenance=false --build-arg "SOURCE_COMMIT=$SOURCE_COMMIT" -t "demo-app:$SOURCE_COMMIT" .
python3 scripts/container_smoke.py --image "demo-app:$SOURCE_COMMIT" --expected-version "$SOURCE_COMMIT"
python3 scripts/integration_demo.py --context kind-pipeline-demo \
  --image "demo-app:$SOURCE_COMMIT" --version "$SOURCE_COMMIT"
echo "Local demo remains available at http://127.0.0.1:30080"
