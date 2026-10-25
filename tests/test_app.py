import json

import pytest

from app.app import create_app


@pytest.fixture
def client(tmp_path):
    info = tmp_path / "build-info.json"
    info.write_text(json.dumps({"commit": "a" * 40}))
    return create_app(info).test_client()


def test_application_serves_embedded_commit(client):
    assert client.get("/").json["version"] == "a" * 40
    assert client.get("/version").json == {"version": "a" * 40}


def test_environment_cannot_impersonate_another_release(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "fake-new-version")
    assert client.get("/version").json["version"] == "a" * 40


def test_health_and_liveness_are_separate(client, monkeypatch):
    assert client.get("/health").status_code == 200
    monkeypatch.setenv("FAIL_HEALTH", "true")
    assert client.get("/health").status_code == 503
    assert client.get("/live").status_code == 200


def test_missing_artifact_identity_is_explicit(tmp_path):
    client = create_app(tmp_path / "missing.json").test_client()
    assert client.get("/version").json["version"] == "development"


def test_invalid_artifact_identity_prevents_startup(tmp_path):
    path = tmp_path / "build-info.json"
    path.write_text(json.dumps({"commit": "fake"}))
    with pytest.raises(ValueError):
        create_app(path)
