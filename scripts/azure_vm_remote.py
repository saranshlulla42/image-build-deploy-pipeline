"""Executed by Azure Run Command on the dedicated demo VM; never prints credentials."""
import base64
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

import yaml


def main(encoded):
    code = 1
    report = {"outcome": "failed_remote_setup"}
    try:
        payload = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)))
        if not Path("/var/lib/image-pipeline/bootstrap-complete").is_file():
            raise RuntimeError("VM bootstrap is incomplete; inspect cloud-init before deploying")
        root = Path("/var/lib/image-pipeline/releases")
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="release-", dir=root) as directory:
            directory = Path(directory)
            for name, content in payload["files"].items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe source file path")
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            # The administrator config and signing authority remain on the VM.
            # Each release receives a short-lived namespace-scoped service account token.
            environment = os.environ.copy()
            environment["KUBECONFIG"] = "/etc/rancher/k3s/k3s.yaml"
            token = subprocess.check_output(
                ["kubectl", "-n", "image-pipeline", "create", "token", "pipeline-deployer", "--duration=30m"],
                env=environment, text=True).strip()
            admin = yaml.safe_load(Path(environment["KUBECONFIG"]).read_text())
            config = {"apiVersion": "v1", "kind": "Config", "current-context": "azure-demo",
                      "clusters": [{"name": "demo", "cluster": admin["clusters"][0]["cluster"]}],
                      "contexts": [{"name": "azure-demo", "context": {"cluster": "demo", "user": "deployer", "namespace": "image-pipeline"}}],
                      "users": [{"name": "deployer", "user": {"token": token}}]}
            kubeconfig = directory / "release.kubeconfig"
            kubeconfig.touch(mode=0o600)
            kubeconfig.write_text(yaml.safe_dump(config))
            environment["KUBECONFIG"] = str(kubeconfig)
            output = directory / "report.json"
            logfile = root / (payload["version"] + ".log")
            command = [sys.executable, str(directory / "scripts/release.py"),
                       "--context", "azure-demo", "--namespace", "image-pipeline",
                       "--image", payload["image"], "--expected-version", payload["version"],
                       "--verify-url", "http://127.0.0.1", "--rollout-timeout", "240",
                       "--verify-timeout", "90", "--report", str(output)]
            with logfile.open("w") as log:
                code = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                      cwd=directory, timeout=1200).returncode
            if output.exists():
                report = json.loads(output.read_text())
            else:
                report["error"] = "Release did not produce a report; inspect the VM log"
            (root / (payload["version"] + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    except Exception as error:
        report["error"] = str(error)
        traceback.print_exc(file=sys.stderr)
    # Azure can return a successful ARM response for a failed guest command.
    # Keep the final evidence small enough for Run Command's 4096-byte output limit.
    compact = {key: report[key] for key in
               ("outcome", "image", "version", "restored_version", "elapsed_seconds", "recovery_seconds")
               if key in report}
    if "error" in report:
        compact["error"] = str(report["error"])[-500:]
    print("PIPELINE_REPORT=" + base64.b64encode(json.dumps(compact).encode()).decode())
    print("PIPELINE_EXIT_CODE=" + str(code))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
