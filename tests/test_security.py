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


def test_scan_of_another_reference_cannot_authorize_current_image():
    payload = report()
    payload["ArtifactName"] = "demo-app:old"
    with pytest.raises(ValueError, match="reference"):
        evaluate(payload, expected_image="demo-app:new")


def test_stale_report_for_same_tag_cannot_authorize_rebuilt_content():
    payload = report()
    payload["Metadata"] = {"ImageID": "sha256:old"}
    with pytest.raises(ValueError, match="content"):
        evaluate(payload, expected_image_id="sha256:new")
