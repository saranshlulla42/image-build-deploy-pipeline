from unittest.mock import Mock

import pytest

from scripts import verify_release


def test_wrong_version_is_rejected_even_with_http_200(monkeypatch):
    monkeypatch.setattr(verify_release, "request_json", Mock(side_effect=[
        {"status": "healthy", "version": "old"}, {"version": "old"},
    ]))
    with pytest.raises(RuntimeError, match="source commit"):
        verify_release.verify("http://service", "new", timeout=0)


def test_unhealthy_json_is_rejected(monkeypatch):
    monkeypatch.setattr(verify_release, "request_json", Mock(side_effect=[
        {"status": "unhealthy", "version": "new"}, {"version": "new"},
    ]))
    with pytest.raises(RuntimeError, match="not healthy"):
        verify_release.verify("http://service", "new", timeout=0)


def test_transient_failure_can_recover_within_deadline(monkeypatch):
    monkeypatch.setattr(verify_release, "request_json", Mock(side_effect=[
        OSError("not ready yet"), {"status": "healthy", "version": "new"}, {"version": "new"},
    ]))
    assert verify_release.verify("http://service", "new", timeout=1, interval=0)["status"] == "verified"


def test_verification_never_ignores_unreachable_service(monkeypatch):
    monkeypatch.setattr(verify_release, "request_json", Mock(side_effect=OSError("offline")))
    with pytest.raises(RuntimeError, match="offline"):
        verify_release.verify("http://service", "new", timeout=0)
