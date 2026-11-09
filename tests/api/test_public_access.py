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


def test_intake_mode_remains_available_when_catalog_is_unavailable(a1_app):
    app, _, _ = a1_app
    app.state.composition.public.catalog = None
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/public/samples").status_code == 503
        assert client.get("/public/intake-mode").json() == {"upload_enabled": False}


def test_closed_gate_does_not_hide_jobless_domain_validation_or_owner_view(a1_app):
    app, engine, store = a1_app
    with TestClient(app, base_url="https://testserver") as client:
        session(client)
        created = client.post("/cases", headers={"Origin": "https://testserver"}).json()
        cid, rev = created["case_id"], created["case_view"]["case_rev"]
        with engine.begin() as conn:
            store.set_open(conn, False)
        assert client.get(f"/cases/{cid}/view").status_code == 200
        result = client.post(f"/cases/{cid}/commands", headers={"Origin": "https://testserver"},
            json={"case_id": cid, "expected_case_rev": rev, "kind": "MARK_REVIEWED", "payload": {}})
        # INTAKE does not allow MARK_REVIEWED; this must be Case's validation,
        # rather than a public 503 before learning whether a job is generated.
        assert result.status_code == 409 and result.json()["error"]["code"] == "case.command.not_allowed"


@pytest.mark.parametrize("local_work", [False, True])
def test_source_object_cannot_replace_admission_class(monkeypatch, local_work):
    from types import SimpleNamespace
    from daesingo.api.public_access import PublicAPI
    public = object.__new__(PublicAPI)
    seen = []
    public.ready = lambda: None
    public.store = SimpleNamespace(accepting=lambda conn: None, local_accepting=lambda conn: None,
        _bound_case=lambda conn, cid, **kw: seen.append(kw["local"]))
    bound = [{"source_asset_ref": "source", "sha256": "a"*64, "byte_size": 10, "duration_ms": 1000}]
    public.require = lambda conn, cid: {"sources": bound}
    monkeypatch.setattr("daesingo.api.public_access.source_duration_ms", lambda source: 1000)
    repository = SimpleNamespace(get_local_source=lambda ref: SimpleNamespace(sha256="a"*64, byte_size=10))
    public.check_sources(None, SimpleNamespace(case_id="owned", sources=[{"source_asset_ref": "source"}]), repository,
                         local=local_work)
    assert seen == [local_work] and type(seen[0]) is bool


def test_api_preserves_saved_change_and_persistent_not_queued_notice_during_stop(a1_app, monkeypatch):
    # This substitutes only the Case command to isolate Runtime's save/defer
    # port. Actual Case correction semantics have separate domain tests.
    from daesingo.api.composition import case_api
    from daesingo.case.command import CommandResult
    app, engine, store = a1_app
    def saved(payload, *, store, admit_auto_exports, **kwargs):
        case = store.load_for_update(payload["case_id"])
        case.description = "TEST_ONLY_SAVED_CHANGE"
        case.case_rev += 1
        store.save(case)
        assert admit_auto_exports([{"job_id": "TEST_ONLY_EXPORT", "case_id": case.case_id, "kind": "REPORT_VIDEO_EXPORT"}]) is False
        return CommandResult({"ok": True, "error": None, "case_view": case_api.get_view(case.case_id, store=store)})
    with TestClient(app, base_url="https://testserver") as client:
        session(client)
        created = client.post("/cases", headers={"Origin": "https://testserver"}).json()
        cid, rev = created["case_id"], created["case_view"]["case_rev"]
        with engine.begin() as conn:
            store.set_open(conn, False)
        monkeypatch.setattr(case_api, "execute_command", saved)
        response = client.post(f"/cases/{cid}/commands", headers={"Origin": "https://testserver"},
            json={"case_id": cid, "expected_case_rev": rev, "kind": "MARK_REVIEWED", "payload": {}})
        assert response.status_code == 200
        view = response.json()["case_view"]
        assert view["description"] == "TEST_ONLY_SAVED_CHANGE" and view["case_rev"] == rev + 1
        note = [n for n in view["notices"] if n["code"] == "public.local_work_not_queued"]
        assert len(note) == 1 and note[0]["message_key"] == "notice.public_local_jobs_stopped" and note[0]["actions"] == []
        assert [n for n in client.get(f"/cases/{cid}/view").json()["notices"] if n["code"] == note[0]["code"]] == note
        client.cookies.clear()
        assert client.get(f"/cases/{cid}/view").status_code == 404


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
