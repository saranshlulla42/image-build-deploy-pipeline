"""Real Kubernetes demonstrations. Run only against an explicit local demo context."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from verify_release import verify

ROOT = Path(__file__).resolve().parents[1]


def run(*command, expected=0):
    result = subprocess.run(list(command), cwd=ROOT)
    if result.returncode != expected:
        raise RuntimeError(f"Command exited {result.returncode}; expected {expected}: {command[0]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--namespace", default="image-pipeline")
    parser.add_argument("--url", default="http://127.0.0.1:30080")
    parser.add_argument("--scenario", choices=["all", "update", "failure", "rollback"], default="all")
    args = parser.parse_args()
    if not args.context.startswith("kind-"):
        parser.error("This integration suite uses kind; pass an explicitly named kind demo context")
    if not args.image.startswith("demo-app:"):
        parser.error("Use a local demo-app image for this suite")
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    kube = ["kubectl", "--context", args.context]
    run(*kube, "create", "namespace", args.namespace) if subprocess.run(
        kube + ["get", "namespace", args.namespace], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode else None
    update_image = args.image + "-update"
    run("docker", "tag", args.image, update_image)
    run("kind", "load", "docker-image", args.image, update_image,
        "--name", args.context.removeprefix("kind-"))

    def release(image, label, *, expected_version=args.version, fault=False, namespace=args.namespace):
        command = [sys.executable, "scripts/release.py", "--context", args.context,
                   "--namespace", namespace, "--image", image,
                   "--expected-version", expected_version, "--allow-local-image",
                   "--rollout-timeout", "25" if fault else "120",
                   "--verify-timeout", "12",
                   "--report", "artifacts/" + label + ".json"]
        return command + (["--fault-readiness"] if fault else []) + (
            ["--service-type", "ClusterIP"] if namespace != args.namespace else []
        )

    summary = {"environment": "local-kind", "context": args.context,
               "source_commit": args.version, "scenarios": [], "passed": False}
    started = time.monotonic()
    try:
        run(*release(args.image, "initial-release"))
        verify(args.url, args.version, timeout=15)
        summary["scenarios"].append("initial-release")
        if args.scenario in {"all", "update"}:
            run(sys.executable, "scripts/traffic_probe.py", "--url", args.url,
                "--output", "artifacts/update-traffic.json", "--",
                *release(update_image, "update-release"))
            summary["scenarios"].append("rolling-update")
        if args.scenario in {"all", "failure", "rollback"}:
            run(sys.executable, "scripts/traffic_probe.py", "--url", args.url,
                "--expected-exit", "1", "--output", "artifacts/failure-traffic.json", "--",
                *release(args.image, "failed-release", fault=True))
            failure = json.loads((artifacts / "failed-release.json").read_text())
            if failure["outcome"] != "failed_rolled_back":
                raise RuntimeError("Failed candidate did not verify restoration")
            verify(args.url, args.version, timeout=15)
            summary["scenarios"].append("unhealthy-release-and-rollback")
        if args.scenario == "all":
            wrong = "0" * 40 if args.version != "0" * 40 else "1" * 40
            run(*release(args.image, "wrong-version-release", expected_version=wrong), expected=1)
            if json.loads((artifacts / "wrong-version-release.json").read_text())["outcome"] != "failed_rolled_back":
                raise RuntimeError("Wrong artifact identity did not trigger recovery")
            verify(args.url, args.version, timeout=15)
            summary["scenarios"].append("wrong-version-rejected")
            first_namespace = args.namespace + "-first-failure"
            run(*kube, "create", "namespace", first_namespace)
            try:
                # Cluster-wide NodePorts are unique: use a ClusterIP Service for this isolated first-release fault.
                # The fault occurs before a version-check Job is needed.
                run(*release(args.image, "first-release-failure", fault=True,
                             namespace=first_namespace), expected=1)
                result = json.loads((artifacts / "first-release-failure.json").read_text())
                if result["outcome"] != "failed_first_deployment":
                    raise RuntimeError("First-release failure reported the wrong recovery state")
                summary["scenarios"].append("first-deployment-failure")
            finally:
                run(*kube, "delete", "namespace", first_namespace, "--wait=false")
        summary["passed"] = True
        return 0
    except Exception as error:
        summary["error"] = str(error)
        raise
    finally:
        summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (artifacts / "integration-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
