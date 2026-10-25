"""Apply the documented policy to a completed Trivy JSON vulnerability report."""
import argparse
import json
import sys
from pathlib import Path


def evaluate(report, expected_image=None, expected_image_id=None):
    if expected_image is not None and report.get("ArtifactName") != expected_image:
        raise ValueError("Scan report belongs to a different image reference")
    if expected_image_id is not None and report.get("Metadata", {}).get("ImageID") != expected_image_id:
        raise ValueError("Scan report does not match the built image content")
    if report.get("SchemaVersion") != 2 or not isinstance(report.get("Results"), list) or not report["Results"]:
        raise ValueError("Missing or unsupported Trivy scan results")
    blocked, unfixed = [], []
    for result in report["Results"]:
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list):
            raise ValueError("Malformed vulnerability list")
        for vulnerability in vulnerabilities:
            if vulnerability["Severity"] not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                raise ValueError("Unsupported vulnerability severity")
            if vulnerability["Severity"] in {"HIGH", "CRITICAL"}:
                entry = {"id": vulnerability["VulnerabilityID"],
                         "package": vulnerability["PkgName"],
                         "severity": vulnerability["Severity"],
                         "fixed_version": vulnerability.get("FixedVersion", "")}
                (blocked if entry["fixed_version"] else unfixed).append(entry)
    return {"policy": "block-fixable-high-critical", "passed": not blocked,
            "blocked": blocked, "unfixed_high_critical": unfixed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--expected-image-id", required=True)
    parser.add_argument("--output", default="artifacts/security-decision.json")
    args = parser.parse_args()
    try:
        decision = evaluate(json.loads(Path(args.report).read_text()),
                            args.expected_image, args.expected_image_id)
        code = 0 if decision["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        decision, code = {"passed": False, "error": str(error)}, 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2) + "\n")
    print(json.dumps(decision, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
