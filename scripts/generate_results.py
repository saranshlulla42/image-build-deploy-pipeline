"""Render a reproducible local validation report from retained experiment artifacts."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--output", type=Path, default=Path("docs/RESULTS.md"))
    parser.add_argument("--snapshot", action="store_true", help="Copy evidence beside the report for a submission")
    args = parser.parse_args()
    def read(name):
        return json.loads((args.artifacts / name).read_text())
    initial = read("initial-release.json")
    update = read("update-release.json")
    update_traffic = read("update-traffic.json")
    failure = read("failed-release.json")
    failure_traffic = read("failure-traffic.json")
    wrong = read("wrong-version-release.json")
    first = read("first-release-failure.json")
    integration = read("integration-summary.json")
    build = read("container-build.json")
    scan = read("trivy-full.json")
    security = read("security-decision.json")
    suites = ET.parse(args.artifacts / "unit-tests.xml").getroot().iter("testsuite")
    totals = Counter()
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            totals[key] += int(suite.attrib.get(key, 0))
    findings = [v for result in scan["Results"] for v in result.get("Vulnerabilities", [])]
    counts = Counter(v["Severity"] for v in findings)
    live_promotion = args.artifacts / "source-change-release.json"
    promotion = json.loads(live_promotion.read_text()) if live_promotion.exists() else None
    promotion_traffic = read("source-change-traffic.json") if promotion else None
    succeeded = (totals["failures"] == totals["errors"] == 0 and totals["tests"] > 0
                 and integration["passed"] and security["passed"]
                 and update_traffic["passed"] and failure_traffic["passed"]
                 and failure["outcome"] == wrong["outcome"] == "failed_rolled_back"
                 and first["outcome"] == "failed_first_deployment")
    if promotion:
        succeeded = succeeded and promotion["outcome"] == "succeeded" and promotion_traffic["passed"]
    headline = "Passed" if succeeded else "Failed: inspect the linked artifacts"
    rows = [
        ("Application, release, scan-policy and traffic tests", f"{totals['tests']} tests; {totals['failures']} failures; {totals['errors']} errors"),
        ("Initial verified release", f"{initial['outcome']}; {initial['elapsed_seconds']} s"),
        ("Rolling update", f"{update['outcome']}; {update['elapsed_seconds']} s"),
        ("Rolling-update traffic", f"{update_traffic['requests']} requests; {update_traffic['failures']} failures; {update_traffic['elapsed_seconds']} s; {update_traffic['observed_requests_per_second']} req/s"),
        ("Unhealthy candidate", failure["outcome"]),
        ("Unhealthy candidate recovery", f"{failure['recovery_seconds']} s from detected failure to verified restoration"),
        ("Traffic during failed release/recovery", f"{failure_traffic['requests']} requests; {failure_traffic['failures']} failures; {failure_traffic['elapsed_seconds']} s"),
        ("Wrong expected source version", f"{wrong['outcome']}; recovery {wrong['recovery_seconds']} s"),
        ("First release failure", first["outcome"]),
        ("Cached-layer build observation", f"{build['build_seconds']} s; not a cold-build benchmark"),
        ("Image size", f"{build['size_bytes']} bytes ({build['size_bytes'] / 1048576:.2f} MiB reported by Docker)"),
        ("Actual vulnerability scan", f"{len(findings)} package findings: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))),
        ("Security policy", f"{len(security['blocked'])} fixable HIGH/CRITICAL blocked findings; {len(security['unfixed_high_critical'])} unfixed HIGH/CRITICAL package findings retained"),
        ("Persistent cloud deployment", "Not configured; no cloud account supplied"),
        ("Updated GitHub workflow execution", "Not executed remotely; local actionlint validation passed"),
        ("GHCR publishing of updated code", "Not performed from this workspace"),
    ]
    if promotion:
        rows.insert(9, ("Promotion between real source revisions", f"{promotion['outcome']}; {promotion['elapsed_seconds']} s; {promotion_traffic['requests']} requests; {promotion_traffic['failures']} failures"))
    text = "# Recorded validation results\n\n"
    text += f"Local validation: **{headline}**. Generated {datetime.now(timezone.utc).isoformat()}.\n\n"
    text += "Environment: macOS arm64 Docker host, Linux arm64 application container, one local kind node. Application runtime: Python 3.12. Unit tests were run with the local Python interpreter; see the JUnit report.\n\n"
    text += "| Check | Observed result |\n|---|---|\n"
    text += "\n".join(f"| {name} | {value} |" for name, value in rows) + "\n\n"
    text += f"Five-scenario integration artifact source: `{integration['source_commit']}`. Latest built artifact source: `{build['source_commit']}`.\n\n"
    if promotion_traffic:
        text += "Observed source revisions during the final promotion:\n\n"
        text += "\n".join(f"- `{version}`: {count} requests" for version, count in promotion_traffic["versions"].items()) + "\n\n"
    text += "## Interpretation\n\n"
    text += "These are single local experiment runs, not statistical availability guarantees. The first rolling-update test uses two tags for one artifact to isolate rollout mechanics. The final promotion, when recorded above, uses two real Git revisions and separately built artifacts. Traffic uses NodePort routing throughout the command, including verification/recovery and a final observation interval.\n\n"
    text += "Recovery time starts after failure detection; it excludes the time spent waiting for rollout/verification failure. Failed release reports deliberately record nonzero command results even when recovery succeeds.\n\n"
    text += "Security policy permits unfixed HIGH/CRITICAL findings while reporting them. The image is not vulnerability-free; findings are package-level occurrences and can repeat the same vulnerability across packages. No intentionally vulnerable image was deployed to demonstrate the policy. Fixture tests simulate rejection separately.\n\n"
    text += "No cold/warm-cache comparison, cloud uptime measurement, provider bill, or new remote Actions run is claimed. Earlier inconsistent benchmark figures have been replaced by these retained measurements.\n\n"
    if args.snapshot:
        evidence = args.output.parent / "evidence"
        evidence.mkdir(exist_ok=True)
        names = [path.name for path in args.artifacts.glob("*.json")] + ["unit-tests.xml", "integration.log", "container-smoke.log"]
        for name in sorted(set(names)):
            source = args.artifacts / name
            if source.is_file():
                shutil.copy2(source, evidence / name)
        text += "## Retained evidence\n\n"
        text += "\n".join(f"- [{path.name}](evidence/{path.name})" for path in sorted(evidence.iterdir()) if path.is_file()) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(text)
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
