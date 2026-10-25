# Automated image build and deployment pipeline

A course project that tests a Flask service, builds a Docker image once, scans it, exercises Kubernetes releases and recovery, then publishes the exact tested image to GHCR.

**Current scope:** local Kubernetes integration is runnable without a cloud account. Persistent cloud deployment is implemented as a gated workflow job and remains unconfigured until a cluster and credentials are supplied. A green local test is not proof of a persistent cloud deployment.

## What happens on a change?

```text
pull request -> application/failure tests -> build -> container smoke test
             -> vulnerability scan -> real kind rollout/recovery tests

main -> all checks above -> transfer tested image -> publish to GHCR by unique tag
     -> record image digest
     -> persistent deployment, if explicitly enabled
     -> otherwise report "cloud deployment not configured"
```

The release command checks readiness and the source version embedded in the image. On failure it restores the previous Deployment spec and verifies recovery. A failed attempted release still exits nonzero after a successful rollback.

## Run the project locally

Use macOS/Linux or a Linux shell with Docker, Python 3.12+, kubectl and kind. Docker must be running. The kind demo uses a dedicated cluster named `pipeline-demo` and localhost port 30080; it does not deploy into your current kubectl context.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m pytest --junitxml=artifacts/unit-tests.xml
bash scripts/local_demo.sh
```

The local helper requires application/container changes to be committed so the embedded source commit identifies real source history. It creates its own cluster, builds the image, then demonstrates:

1. Initial verified deployment.
2. Rolling update while sampling traffic through a NodePort.
3. A deliberately unhealthy candidate, automatic restoration, and continued traffic sampling.
4. A healthy HTTP response with an unexpected source version, which is rejected.
5. First-deployment failure with no false claim of rollback.

The update image is a second local tag for the same built artifact; this deliberately exercises rollout mechanics without inventing a second source commit. The wrong-version scenario deliberately requests a nonmatching identity to test rejection.

After the demo, open:

- Application: http://127.0.0.1:30080/
- Embedded source version: http://127.0.0.1:30080/version
- Readiness: http://127.0.0.1:30080/health

The cluster stays running locally until you remove it. This does not make it a cloud service.

## Run individual checks

```bash
# Replace these values with your actual demo context/image/commit.
python scripts/release.py --context kind-pipeline-demo --namespace image-pipeline \
  --image demo-app:FULL_COMMIT --expected-version FULL_COMMIT --allow-local-image

# Sample a stable Service/NodePort URL throughout a command; never port-forward a pod.
python scripts/traffic_probe.py --url http://127.0.0.1:30080 \
  --output artifacts/traffic.json -- YOUR_RELEASE_COMMAND

# Scan locally with Trivy 0.76.1, then evaluate the full report.
trivy image --scanners vuln --format json --output artifacts/trivy-full.json demo-app:FULL_COMMIT
python scripts/security_gate.py --report artifacts/trivy-full.json

# Optional benchmark: three builds with layer caching disabled and three warm builds.
bash scripts/measure_build.sh
```

The scan policy blocks fixable HIGH/CRITICAL findings. Unfixed HIGH/CRITICAL findings remain visible in the decision report. A missing/malformed scan or scanner execution failure blocks the pipeline. This policy does not certify an image as vulnerability-free.

## GitHub setup

1. Push this code to a repository you control; open a pull request to run validation.
2. The workflow already declares scoped token permissions. No personal token or permission to approve pull requests is required for publishing.
3. Merge into `main` to validate and publish the tested artifact.
4. GHCR package visibility is independent of repository visibility. For the supplied persistent workflow, explicitly make the image package public. It checks anonymous access before deployment.
5. Open the Actions run and download `validation-evidence` for test reports, scan findings, rollout results and traffic measurements.
6. Follow [persistent deployment setup](docs/CLOUD_SETUP.md) only when you have a cloud account/cluster.

An amd64 image is built in GitHub. The target cluster must support amd64. Local images use the local Docker architecture.

## Repository map

- `app/`: Flask application and hash-locked runtime dependencies.
- `tests/`: application, release failure-path, scan-policy and traffic-check tests.
- `scripts/release.py`: explicit-target deployment, namespace lock, verification and recovery.
- `scripts/verify_release.py`: readiness plus artifact identity check.
- `scripts/traffic_probe.py`: full-command traffic sampling with truthful exit codes.
- `scripts/integration_demo.py`: actual Kubernetes experiment orchestration.
- `k8s/`: Deployment, Service, local kind configuration and optional cloud bootstrap RBAC.
- `.github/workflows/pipeline.yml`: validation, publish and optional persistent release.
- `docs/`: explanations, measured results, cloud setup and demonstration instructions.

## Limitations

- Two pods on one local node do not provide protection against node failure.
- Rolling updates aim to reduce interruption; zero failures in a measured sample is not a universal zero-downtime guarantee.
- There is one application and one deployment environment, with no database/migration rollback.
- The namespace must be dedicated to this project; the release tool refuses to overwrite a deployment without its verified state record.
- A ConfigMap lock serializes releases. An interrupted runner can leave a lock; inspect the environment before removing it. See the cloud guide.
- Snapshot rollback restores the Deployment spec, not Service/IAM/network changes or a deleted image.
- Runtime and base-image dependencies are pinned; upgrades require refreshing locks/digests, rescanning and retesting.
- The cloud job has not run until credentials and an actual persistent cluster are configured.

## Cleanup

```bash
kind delete cluster --name pipeline-demo
```

This removes only the named local demo cluster. Cloud resources require separate teardown in your provider account; stopping a VM can leave billable disks/IPs. Preserve experimental evidence first.
