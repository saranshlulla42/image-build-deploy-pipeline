import base64
import json

import pytest

from scripts.azure_deploy import make_script, parse_result

IMAGE = "ghcr.io/example/app@sha256:" + "a" * 64
VERSION = "b" * 40


def response(code=0, **changes):
    report = {"outcome": "succeeded", "image": IMAGE, "version": VERSION, **changes}
    encoded = base64.b64encode(json.dumps(report).encode()).decode()
    return {"value": [{"code": "ProvisioningState/succeeded", "message":
                       f"Enable succeeded:\n[stdout]\nPIPELINE_REPORT={encoded}\nPIPELINE_EXIT_CODE={code}\n[stderr]\n"}]}


def test_accepts_only_matching_successful_guest_evidence():
    assert parse_result(response(), IMAGE, VERSION)["version"] == VERSION


@pytest.mark.parametrize("reply", [
    response(1, outcome="failed_rolled_back"),
    response(2, outcome="failed_recovery"),
    response(0, outcome="failed_preflight"),
    response(version="c" * 40),
    response(image=IMAGE.replace("a" * 64, "d" * 64)),
    {"value": [{"code": "ProvisioningState/succeeded", "message": "Enable succeeded"}]},
])
def test_arm_success_cannot_hide_guest_failure_or_wrong_artifact(reply):
    with pytest.raises(ValueError):
        parse_result(reply, IMAGE, VERSION)


def test_duplicate_evidence_is_rejected():
    reply = response()
    reply["value"] *= 2
    with pytest.raises(ValueError, match="ambiguous"):
        parse_result(reply, IMAGE, VERSION)


def test_mutable_or_shell_images_rejected_before_remote_execution():
    for image in ["ghcr.io/example/app:latest", IMAGE + "; id"]:
        with pytest.raises(ValueError):
            make_script(image, VERSION)
