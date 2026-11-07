"""Actual API middleware with synthetic policy/shared DB; no paid provider."""
from dataclasses import replace
import hashlib
import json

from fastapi.testclient import TestClient
import pytest

from a1_support import policy_values, sqlite_engine
from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.case.store import CaseStore
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.policy import PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore


@pytest.fixture
def a1_app(api_startup, tmp_path, monkeypatch):
    engine = sqlite_engine(tmp_path / "public.sqlite")
    schema.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(schema.control.insert().values(id=1, accepting=False, policy_hash=None))
    values = policy_values(tmp_path)
    root = tmp_path / "official"
    root.mkdir()
    (root / "part.mp4").write_bytes(b"synthetic!")
    media = {"schema": "official-samples/v1", "samples": [{"sample_id": "test-only",
        "label": "Synthetic", "example_hint": "Turn", "authorization_ref": "TEST_ONLY",
        "files": [{"name": "part.mp4", "sha256": hashlib.sha256(b"synthetic!").hexdigest(),
                   "byte_size": 10, "duration_ms": 1000}]}]}
    raw = json.dumps(media).encode()
    (tmp_path / "manifest.json").write_bytes(raw)
    values["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "policy.private.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    path.chmod(0o600)
    startup, _ = api_startup
    startup = replace(startup, revision="1" * 40, config=replace(startup.config,
        public=startup.config.public.model_copy(update={"mode": "a1", "policy_file": path})))
    monkeypatch.setattr("daesingo.api.composition.create_api_engine", lambda *a: engine)
    monkeypatch.setattr("daesingo.api.composition.create_ready_engine", lambda *a: engine)
    cases = CaseStore()
    monkeypatch.setattr(ApiComposition, "_store", lambda *a: cases)
    from daesingo.recording.repository import InMemoryRecordingRepository
    recording = InMemoryRecordingRepository()
    monkeypatch.setattr(ApiComposition, "_recording_repository", lambda *a: recording, raising=False)
    app = create_app(startup=startup)
    store = PublicStore(PublicPolicy.model_validate(values), require_public=True)
    with engine.begin() as conn:
        store.set_open(conn, True)
    yield app, engine, store
    app.state.composition.close()


def session(client):
    response = client.post("/public/session", headers={"Origin": "https://testserver"})
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie


def test_missing_approval_serves_health_but_refuses_analysis_and_raw_upload(api_startup):
    startup, _ = api_startup
    startup = replace(startup, config=replace(startup.config,
        public=startup.config.public.model_copy(update={"mode": "a1"})))
    with TestClient(create_app(startup=startup), base_url="https://testserver") as client:
        assert client.get("/health/live").status_code == 200
        assert client.post("/cases/case_1/commands", json={"kind": "START_ANALYSIS"}).status_code == 503
        assert client.post("/cases/case_1/sources", content=b"unapproved").status_code == 403


def test_catalog_selects_only_safe_presentation_fields(a1_app):
    app, _, _ = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        result = client.get("/public/samples")
        assert result.status_code == 200
        text = result.text
        assert "Synthetic" in text and "1000" in text
        assert all(x not in text for x in ("authorization_ref", "sha256", "part.mp4", "samples_root"))


def test_cross_origin_session_and_case_creation_are_rejected(a1_app):
    app, _, _ = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/public/session", headers={"Origin": "https://other.example"}).status_code == 403
        session(client)
        assert client.post("/cases", headers={"Origin": "https://other.example"}).status_code == 403


def test_unknown_client_token_is_replaced_by_server_random_identity(a1_app):
    from daesingo.api.public_access import COOKIE
    app, _, _ = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        result = client.post("/public/session", headers={"Origin": "https://testserver",
            "Cookie": COOKIE + "=" + "A" * 43})
        assert result.status_code == 201
        assert COOKIE + "=" + "A" * 43 not in result.headers["set-cookie"]


def test_actual_case_creation_binds_owner_and_other_cookie_cannot_read_any_path(a1_app):
    app, engine, _ = a1_app
    with TestClient(app, base_url="https://testserver") as first:
        session(first)
        created = first.post("/cases", headers={"Origin": "https://testserver"})
        assert created.status_code == 201
        case_id = created.json()["case_id"]
        assert first.get(f"/cases/{case_id}/view").status_code == 200
        first.cookies.clear()
        session(first)
        for path in ("view", "frames/frame_1", "assets/asset_1", "candidate-videos/clip_1"):
            denied = first.get(f"/cases/{case_id}/{path}", headers={"Range": "bytes=0-10"})
            assert denied.status_code == 404 and denied.json()["case_view"] is None
        assert first.post(f"/cases/{case_id}/commands", json={},
                          headers={"Origin": "https://testserver"}).status_code == 404


def test_direct_upload_is_rejected_without_receiving_or_creating_files(a1_app):
    app, _, _ = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        result = client.post("/cases/case_1/sources", content=b"PRIVATE_UNAPPROVED")
        assert result.status_code == 403 and "PRIVATE" not in result.text
        root = app.state.composition.startup.config.media_root
        assert not list((root / "source").glob("*")) and not list((root / "staging").glob("upload-*"))


def test_official_id_route_uses_real_registration_and_reuses_binding(a1_app, monkeypatch):
    from daesingo.recording.probe import LocalSource, ProbedStream
    def probe(self, path):
        return LocalSource(path, path.stat().st_size, path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(), 1.0, (ProbedStream(0, "VIDEO", 1.0),))
    monkeypatch.setattr("daesingo.recording.probe.FfprobeMediaProbe.probe", probe)
    app, _, _ = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        session(client)
        created = client.post("/cases", headers={"Origin": "https://testserver"})
        cid = created.json()["case_id"]
        path = f"/cases/{cid}/official-samples"
        for _ in range(2):
            accepted = client.post(path, json={"sample_id": "test-only"}, headers={"Origin": "https://testserver"})
            assert accepted.status_code == 201
            assert accepted.json()["case_view"]["manifest_summary"]["file_count"] == 1
        root = app.state.composition.startup.config.media_root
        assert len(list((root / "source").glob("*"))) == 1
        denied = client.post(path, json={"sample_id": "unknown"}, headers={"Origin": "https://testserver"})
        assert denied.status_code == 422
        assert len(list((root / "source").glob("*"))) == 1
