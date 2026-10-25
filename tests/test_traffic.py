import sys

from scripts import traffic_probe


def test_dropped_requests_fail_the_measurement(monkeypatch):
    responses = iter([{"version": "old"}, OSError("connection dropped"), {"version": "new"}])
    def request(*args, **kwargs):
        result = next(responses, {"version": "new"})
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(traffic_probe, "request_json", request)
    code, report = traffic_probe.probe("http://service", [sys.executable, "-c", "pass"],
                                      grace=0, interval=.001)
    assert code == 1 and report["failures"] == 1


def test_failed_rollout_is_not_hidden_by_healthy_http(monkeypatch):
    monkeypatch.setattr(traffic_probe, "request_json", lambda *a, **k: {"version": "old"})
    code, report = traffic_probe.probe("http://service", [sys.executable, "-c", "raise SystemExit(1)"],
                                      grace=0, interval=.001)
    assert code == 1 and report["command_exit"] == 1


def test_expected_failed_release_can_demonstrate_successful_recovery(monkeypatch):
    monkeypatch.setattr(traffic_probe, "request_json", lambda *a, **k: {"version": "old"})
    code, report = traffic_probe.probe("http://service", [sys.executable, "-c", "raise SystemExit(1)"],
                                      grace=0, interval=.001, expected_exit=1)
    assert code == 0 and report["passed"]


def test_failed_recovery_is_never_accepted_as_expected_release_failure(monkeypatch):
    monkeypatch.setattr(traffic_probe, "request_json", lambda *a, **k: {"version": "old"})
    code, report = traffic_probe.probe("http://service", [sys.executable, "-c", "raise SystemExit(2)"],
                                      grace=0, interval=.001, expected_exit=1)
    assert code == 1 and not report["passed"]
