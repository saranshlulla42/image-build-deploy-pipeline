import copy
import json

import pytest

from scripts.release import DEPLOYMENT, LOCK, STATE, ReleaseError, deploy, make_deployment

OLD_VERSION = "a" * 40
NEW_VERSION = "b" * 40
OLD_IMAGE = "ghcr.io/example/app@sha256:" + "1" * 64
NEW_IMAGE = "ghcr.io/example/app@sha256:" + "2" * 64


class FakeKube:
    """API state simulator for fault paths; real rollout tests run separately on kind."""
    def __init__(self, existing=True, fail_rollouts=(), fail_verifications=()):
        self.objects = {}
        if existing:
            self.objects[("deployment", DEPLOYMENT)] = make_deployment(OLD_IMAGE, OLD_VERSION)
            self.objects[("configmap", STATE)] = {"data": {"image": OLD_IMAGE, "version": OLD_VERSION}}
        self.fail_rollouts = set(fail_rollouts)
        self.fail_verifications = set(fail_verifications)
        self.rollouts = 0
        self.verifications = 0
        self.events = []

    def get(self, resource, name):
        return copy.deepcopy(self.objects.get((resource, name)))

    def run(self, *args, **kwargs):
        self.events.append(args)
        if args[0] == "create":
            if ("configmap", LOCK) in self.objects:
                raise ReleaseError("Lock already exists")
            self.objects[("configmap", LOCK)] = {"data": {"owner": args[-1].split("=", 2)[2]}}
        elif args[0] == "patch":
            patch = json.loads(args[-1])
            self.objects[("deployment", DEPLOYMENT)]["spec"] = patch[0]["value"]
        elif args[0] == "delete":
            self.objects.pop((args[1], args[2]), None)
        return ""

    def apply(self, document):
        self.events.append(("apply", document["kind"]))
        resource = {"Deployment": "deployment", "ConfigMap": "configmap", "Service": "service"}[document["kind"]]
        self.objects[(resource, document["metadata"]["name"])] = copy.deepcopy(document)

    def rollout(self, timeout):
        self.rollouts += 1
        if self.rollouts in self.fail_rollouts:
            raise ReleaseError("Rollout stalled")

    def verify(self, image, version, timeout):
        self.verifications += 1
        self.events.append(("verify", image, version))
        if self.verifications in self.fail_verifications:
            raise ReleaseError("Unexpected artifact version")


def test_success_only_records_verified_candidate():
    kube = FakeKube()
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 0 and report["outcome"] == "succeeded"
    state = kube.get("configmap", STATE)["data"]
    assert state["image"] == NEW_IMAGE
    assert state["previous_image"] == OLD_IMAGE
    assert kube.get("configmap", LOCK) is None


@pytest.mark.parametrize("failure", ["rollout", "version"])
def test_failed_candidate_restores_full_spec_and_verified_record(failure):
    kube = FakeKube(fail_rollouts=(2,) if failure == "rollout" else (),
                    fail_verifications=(2,) if failure == "version" else ())
    original = kube.get("deployment", DEPLOYMENT)["spec"]
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION, fault=True)
    assert code == 1 and report["outcome"] == "failed_rolled_back"
    assert kube.get("deployment", DEPLOYMENT)["spec"] == original
    assert kube.get("configmap", STATE)["data"]["image"] == OLD_IMAGE
    assert kube.get("configmap", LOCK) is None


def test_recovery_failure_has_distinct_nonzero_status():
    kube = FakeKube(fail_rollouts=(2, 3))
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 2 and report["outcome"] == "failed_recovery"
    assert "recovery_error" in report


def test_first_release_failure_never_claims_rollback():
    kube = FakeKube(existing=False, fail_rollouts=(1,))
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_first_deployment"
    assert kube.get("deployment", DEPLOYMENT) is None
    assert "restored_version" not in report


def test_existing_unmanaged_deployment_is_not_overwritten():
    kube = FakeKube()
    kube.objects.pop(("configmap", STATE))
    original = kube.get("deployment", DEPLOYMENT)
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_preflight"
    assert kube.get("deployment", DEPLOYMENT) == original


def test_drift_is_rejected_before_mutating_deployment():
    kube = FakeKube()
    kube.objects[("configmap", STATE)]["data"]["image"] = NEW_IMAGE
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_preflight"
    assert not any(event[0] == "apply" for event in kube.events)


def test_unhealthy_baseline_is_not_overwritten():
    kube = FakeKube(fail_verifications=(1,))
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_preflight"
    assert kube.get("deployment", DEPLOYMENT)["spec"]["template"]["spec"]["containers"][0]["image"] == OLD_IMAGE


def test_concurrent_release_cannot_take_lock_or_modify_state():
    kube = FakeKube()
    kube.objects[("configmap", LOCK)] = {"data": {"owner": "another-release"}}
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_preflight"
    assert kube.get("configmap", LOCK)["data"]["owner"] == "another-release"
    assert not any(event[0] == "apply" for event in kube.events)


def test_api_response_loss_after_candidate_write_still_restores_previous_spec():
    class LostResponse(FakeKube):
        def apply(self, document):
            super().apply(document)
            if document["kind"] == "Deployment":
                raise ReleaseError("API response lost after accepted write")
    kube = LostResponse()
    original = kube.get("deployment", DEPLOYMENT)["spec"]
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_rolled_back"
    assert kube.get("deployment", DEPLOYMENT)["spec"] == original


def test_record_write_failure_does_not_leave_unrecorded_candidate_running():
    class FailedRecord(FakeKube):
        fail_once = True
        def apply(self, document):
            super().apply(document)
            if document["kind"] == "ConfigMap" and self.fail_once:
                self.fail_once = False
                raise ReleaseError("Record write response lost")
    kube = FailedRecord()
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 1 and report["outcome"] == "failed_rolled_back"
    assert kube.get("configmap", STATE)["data"]["image"] == OLD_IMAGE


def test_first_release_records_success_without_inventing_previous_release():
    kube = FakeKube(existing=False)
    code, report = deploy(kube, NEW_IMAGE, NEW_VERSION)
    assert code == 0 and report["outcome"] == "succeeded"
    assert "previous_image" not in kube.get("configmap", STATE)["data"]
