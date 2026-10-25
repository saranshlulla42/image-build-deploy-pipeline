"""Deploy the tested digest through Azure Run Command and validate guest evidence."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys

if __package__:
    from .verify_release import verify
else:
    from verify_release import verify

ROOT = Path(__file__).resolve().parents[1]
FILES = ["scripts/release.py", "scripts/verify_release.py", "k8s/deployment.yaml", "k8s/service.yaml"]


def make_script(image, version):
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("Use an immutable GHCR digest")
    if not re.fullmatch(r"[0-9a-f]{40}", version):
        raise ValueError("Use the full source commit")
    payload = {"image": image, "version": version,
               "files": {name: (ROOT / name).read_text() for name in FILES}}
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
    remote = base64.b64encode((ROOT / "scripts/azure_vm_remote.py").read_bytes()).decode()
    # Only base64 enters the shell; image references never become shell syntax.
    return "#!/bin/sh\nexec python3 - '" + encoded + "' <<'PIPELINE_PY'\n" + \
        "import base64\nexec(base64.b64decode('" + remote + "'))\nPIPELINE_PY\n"


def parse_result(response, image, version):
    messages = "\n".join(item.get("message", "") for item in response.get("value", []))
    codes = re.findall(r"^PIPELINE_EXIT_CODE=(-?\d+)\s*$", messages, re.MULTILINE)
    reports = re.findall(r"^PIPELINE_REPORT=([A-Za-z0-9+/=]+)\s*$", messages, re.MULTILINE)
    if len(codes) != 1 or len(reports) != 1:
        raise ValueError("Azure guest evidence missing or ambiguous; inspect VM before retrying")
    report = json.loads(base64.b64decode(reports[0], validate=True))
    if int(codes[0]) != 0 or report.get("outcome") != "succeeded":
        raise ValueError("Guest release failed: " + json.dumps(report))
    if report.get("image") != image or report.get("version") != version:
        raise ValueError("Guest evidence does not match the requested artifact")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--report-dir", default="artifacts")
    args = parser.parse_args()
    output = Path(args.report_dir)
    output.mkdir(parents=True, exist_ok=True)
    script = output / "azure-command.sh"
    try:
        script.write_text(make_script(args.image, args.version))
        result = subprocess.run(["az", "vm", "run-command", "invoke", "--resource-group", args.resource_group,
                                 "--name", args.vm_name, "--command-id", "RunShellScript",
                                 "--scripts", "@" + str(script), "--output", "json"],
                                text=True, capture_output=True, timeout=1500)
        (output / "azure-command-response.json").write_text(result.stdout)
        if result.returncode:
            raise RuntimeError("Azure Run Command failed: " + result.stderr[-1500:])
        report = parse_result(json.loads(result.stdout), args.image, args.version)
        # The VM also checks its nginx route inside the rollback transaction.
        # This independent check proves public reachability from the CI runner.
        report["public_check"] = verify(args.url, args.version, 45)
        (output / "azure-release.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        script.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
