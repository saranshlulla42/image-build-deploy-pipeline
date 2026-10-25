import pytest

from scripts.security_gate import evaluate


def finding(severity="HIGH", fixed="1.2.3"):
    return {"Severity": severity, "FixedVersion": fixed,
            "VulnerabilityID": "CVE-TEST-0001", "PkgName": "fixture-only"}


def report(*findings):
    return {"SchemaVersion": 2, "Results": [{"Vulnerabilities": list(findings)}]}


def test_fixable_high_severity_finding_blocks_release():
    assert not evaluate(report(finding()))["passed"]


def test_unfixed_critical_finding_remains_visible():
    decision = evaluate(report(finding("CRITICAL", "")))
    assert decision["passed"]
    assert len(decision["unfixed_high_critical"]) == 1


def test_medium_finding_does_not_block_this_policy():
    assert evaluate(report(finding("MEDIUM")))["passed"]


@pytest.mark.parametrize("payload", [{}, {"SchemaVersion": 2}, {"SchemaVersion": 2, "Results": []}])
def test_missing_scan_cannot_be_treated_as_clean(payload):
    with pytest.raises(ValueError):
        evaluate(payload)
