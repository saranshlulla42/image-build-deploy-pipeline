"""Deploy a verified image, reverting the complete previous pod configuration on failure."""
import argparse
import copy
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
if __package__:
    from .verify_release import verify
else:
    from verify_release import verify

ROOT = Path(__file__).resolve().parents[1]
LOCK = "pipeline-release-lock"
STATE = "pipeline-release-state"
DEPLOYMENT = "app-deployment"


class ReleaseError(RuntimeError):
    pass


class Kube:
    def __init__(self, context, namespace, verify_url=None):
        self.base = ["kubectl", "--context", context, "--namespace", namespace]
        self.verify_url = verify_url

    def run(self, *args, document=None, timeout=180):
        result = subprocess.run(
            self.base + list(args),
            input=json.dumps(document) if document is not None else None,
            text=True, capture_output=True, timeout=timeout,
        )
        if result.returncode:
            raise ReleaseError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def get(self, resource, name):
        text = self.run("get", resource, name, "--ignore-not-found", "-o", "json")
        return json.loads(text) if text else None

    def apply(self, document):
        self.run("apply", "-f", "-", document=document)

    def rollout(self, timeout):
        self.run("rollout", "status", "deployment/" + DEPLOYMENT,
                 f"--timeout={timeout}s", timeout=timeout + 15)

    def verify(self, image, version, timeout):
        # A short-lived Job reaches the Service, rather than port-forwarding one pod.
        name = "release-check-" + uuid.uuid4().hex[:10]
        source = (ROOT / "scripts/verify_release.py").read_text()
        job = {
            "apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": name, "labels": {"app.kubernetes.io/part-of": "image-pipeline"}},
            "spec": {
                "backoffLimit": 0, "activeDeadlineSeconds": timeout,
                "ttlSecondsAfterFinished": 300,
                "template": {"spec": {
                    "restartPolicy": "Never", "automountServiceAccountToken": False,
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                                        "seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [{
                        "name": "verify", "image": image, "imagePullPolicy": "IfNotPresent",
                        "securityContext": {"allowPrivilegeEscalation": False,
                                            "capabilities": {"drop": ["ALL"]}},
                        "resources": {"requests": {"cpu": "10m", "memory": "24Mi"},
                                      "limits": {"cpu": "200m", "memory": "64Mi"}},
                        "command": ["python", "-c", source, "--url", "http://app-service",
                                    "--expected-version", version, "--timeout", str(max(1, timeout - 5))],
                    }],
                }},
            },
        }
        try:
            self.apply(job)
            self.run("wait", "--for=condition=complete", "job/" + name,
                     f"--timeout={timeout + 5}s", timeout=timeout + 15)
            print(self.run("logs", "job/" + name))
            if self.verify_url:
                print(json.dumps(verify(self.verify_url, version, timeout)))
        except Exception:
            try:
                print(self.run("logs", "job/" + name), file=sys.stderr)
            except Exception:
                pass
            raise
        finally:
            try:
                self.run("delete", "job", name, "--ignore-not-found", "--wait=false")
            except Exception as error:
                print(f"Verification job cleanup pending: {error}", file=sys.stderr)


def state_document(data):
    return {"apiVersion": "v1", "kind": "ConfigMap",
            "metadata": {"name": STATE}, "data": data}


def make_deployment(image, version, fault=False):
    document = yaml.safe_load((ROOT / "k8s/deployment.yaml").read_text())
    template = document["spec"]["template"]
    template["metadata"]["annotations"] = {"pipeline.source-commit": version}
    container = template["spec"]["containers"][0]
    container["image"] = image
    if fault:
        container["env"] = [{"name": "FAIL_HEALTH", "value": "true"}]
    return document


def deploy(kube, image, version, *, fault=False, rollout_timeout=120, verify_timeout=45, service_type="NodePort"):
    started = time.monotonic()
    owner = uuid.uuid4().hex
    report = {"started_at": datetime.now(timezone.utc).isoformat(),
              "image": image, "version": version, "outcome": "failed_preflight"}
    locked = False
    mutated = False
    previous = None
    old_state = None
    try:
        kube.run("create", "configmap", LOCK, "--from-literal=owner=" + owner)
        locked = True
        previous = kube.get("deployment", DEPLOYMENT)
        old_state = kube.get("configmap", STATE)
        if previous:
            if not old_state or not old_state.get("data", {}).get("image"):
                raise ReleaseError("Existing deployment has no verified release record; refusing to overwrite it")
            old = old_state["data"]
            old_image = next(c["image"] for c in previous["spec"]["template"]["spec"]["containers"]
                             if c["name"] == "app")
            if old_image != old["image"]:
                raise ReleaseError("Deployment differs from its verified release record")
            kube.rollout(rollout_timeout)
            kube.verify(old["image"], old["version"], verify_timeout)
        elif old_state:
            raise ReleaseError("Release record exists without its deployment; investigate before retrying")

        service = yaml.safe_load((ROOT / "k8s/service.yaml").read_text())
        service["spec"]["type"] = service_type
        if service_type == "ClusterIP":
            service["spec"]["ports"][0].pop("nodePort", None)
        kube.apply(service)
        mutated = True  # The API may accept a write even if its response is lost.
        kube.apply(make_deployment(image, version, fault))
        kube.rollout(rollout_timeout)
        kube.verify(image, version, verify_timeout)
        data = {"image": image, "version": version,
                "verified_at": datetime.now(timezone.utc).isoformat()}
        if old_state:
            data["previous_image"] = old_state["data"]["image"]
            data["previous_version"] = old_state["data"]["version"]
        kube.apply(state_document(data))
        report["outcome"] = "succeeded"
        return 0, report
    except Exception as error:
        report["error"] = str(error)
        if mutated:
            recovery_start = time.monotonic()
            try:
                if previous:
                    # Restore the full spec; a merge patch could leave failed env/config behind.
                    kube.run("patch", "deployment", DEPLOYMENT, "--type=json", "-p",
                             json.dumps([{"op": "replace", "path": "/spec",
                                          "value": previous["spec"]}]))
                    kube.rollout(rollout_timeout)
                    old = old_state["data"]
                    kube.verify(old["image"], old["version"], verify_timeout)
                    kube.apply(state_document(copy.deepcopy(old)))
                    report["outcome"] = "failed_rolled_back"
                    report["restored_version"] = old["version"]
                else:
                    kube.run("delete", "deployment", DEPLOYMENT, "--ignore-not-found", "--wait=true")
                    kube.run("delete", "configmap", STATE, "--ignore-not-found")
                    report["outcome"] = "failed_first_deployment"
                return 1, report
            except Exception as recovery_error:
                report["outcome"] = "failed_recovery"
                report["recovery_error"] = str(recovery_error)
                return 2, report
            finally:
                report["recovery_seconds"] = round(time.monotonic() - recovery_start, 3)
        return 1, report
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if locked:
            try:
                lock = kube.get("configmap", LOCK)
                if lock and lock.get("data", {}).get("owner") == owner:
                    kube.run("delete", "configmap", LOCK, "--wait=false")
            except Exception as error:
                report["lock_cleanup_error"] = str(error)
                print(f"Release lock needs inspection: {error}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="Explicit kubectl context; never silently use the current cluster")
    parser.add_argument("--namespace", default="image-pipeline")
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--allow-local-image", action="store_true")
    parser.add_argument("--fault-readiness", action="store_true", help="Local demo clusters only")
    parser.add_argument("--rollout-timeout", type=int, default=120)
    parser.add_argument("--verify-timeout", type=int, default=45)
    parser.add_argument("--service-type", choices=["NodePort", "ClusterIP"], default="NodePort")
    parser.add_argument("--report", default="artifacts/release.json")
    parser.add_argument("--verify-url", help="Also verify an HTTP route before promotion and after rollback")
    args = parser.parse_args()
    local = args.context.startswith("kind-") or args.context == "minikube"
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_version):
        parser.error("Expected version must be a full lowercase source commit")
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", args.image):
        if not (args.allow_local_image and local and re.fullmatch(r"demo-app:[a-z0-9._-]+", args.image)):
            parser.error("Use a GHCR image digest, or explicitly allow a demo-app image on a local demo cluster")
    if args.fault_readiness and not local:
        parser.error("Fault injection is restricted to kind/minikube demo contexts")
    if args.rollout_timeout < 1 or args.verify_timeout < 10:
        parser.error("Timeouts must be positive; verification needs at least 10 seconds")
    code, report = deploy(
        Kube(args.context, args.namespace, args.verify_url), args.image, args.expected_version,
        fault=args.fault_readiness, rollout_timeout=args.rollout_timeout,
        verify_timeout=args.verify_timeout,
        service_type=args.service_type,
    )
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
