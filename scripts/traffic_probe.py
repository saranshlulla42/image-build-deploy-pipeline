"""Measure HTTP availability through a stable Service endpoint for an entire command."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.verify_release import request_json
except ModuleNotFoundError:
    from verify_release import request_json


def probe(url, command, *, interval=0.1, grace=1, timeout=300, expected_exit=0):
    # Fail before starting a mutation if the baseline endpoint cannot be reached.
    baseline = request_json(url)
    if not isinstance(baseline.get("version"), str):
        raise ValueError("Baseline response has no artifact version")
    report = {"started_at": datetime.now(timezone.utc).isoformat(),
              "url": url, "requests": 0, "failures": 0, "versions": {}, "errors": []}
    started = time.monotonic()
    process = subprocess.Popen(command, start_new_session=True)
    finished_at = None
    try:
        while True:
            sample_start = time.monotonic()
            report["requests"] += 1
            try:
                version = request_json(url, timeout=2)["version"]
                report["versions"][version] = report["versions"].get(version, 0) + 1
            except (OSError, ValueError, KeyError) as error:
                report["failures"] += 1
                if len(report["errors"]) < 20:
                    report["errors"].append(str(error))
            code = process.poll()
            now = time.monotonic()
            if code is not None and finished_at is None:
                finished_at = now
            if finished_at is not None and now - finished_at >= grace:
                break
            if now - started > timeout:
                raise TimeoutError("Traffic measurement exceeded its deadline")
            time.sleep(max(0, interval - (time.monotonic() - sample_start)))
        report["command_exit"] = process.returncode
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["observed_requests_per_second"] = round(report["requests"] / max(report["elapsed_seconds"], .001), 2)
        report["passed"] = report["failures"] == 0 and process.returncode == expected_exit
        return (0 if report["passed"] else 1), report
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="NodePort/Ingress/Service URL; not a pod port-forward")
    parser.add_argument("--output", default="artifacts/traffic.json")
    parser.add_argument("--expected-exit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Supply a rollout/release command after --")
    try:
        code, report = probe(args.url, command, expected_exit=args.expected_exit, timeout=args.timeout)
    except Exception as error:
        code, report = 1, {"passed": False, "error": str(error)}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
