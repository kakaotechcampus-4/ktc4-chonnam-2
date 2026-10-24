"""RT-08(c) transport: opaque JSON, bounded receive, table-only status."""
import asyncio
from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient
from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.case import CommandResult


@pytest.mark.parametrize("ok,code,view,appended,status", [
    (True, None, {"case_id": "case_http", "running_jobs": [1]}, [1], 202),
    (True, None, {"case_id": "case_http"}, [], 200),
    (False, "invalid_payload", None, [], 422),
    (False, "unknown_target", None, [], 404),
    (False, "unknown_target", {"case_id": "case_http"}, [], 409),
    (False, "stale_revision", {"case_id": "case_http"}, [], 409),
    (False, "future_code", None, [], 409),
])
def test_status_uses_result_only_and_preserves_body(api_startup, monkeypatch, ok, code, view, appended, status):
    startup, _ = api_startup
    body = {"ok": ok, "error": None if ok else {"code": "case.command." + code, "message_key": "domain.key"}, "case_view": view}
    seen = []
    def execute(self, payload, trace_id):
        seen.append((payload, trace_id))
        return CommandResult(body, appended)
    monkeypatch.setattr(ApiComposition, "execute_command", execute, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases/case_http/commands", json={"kind": "PRIVATE_UNKNOWN"})
    assert response.status_code == status and response.json() == body
    assert response.headers.get("location") == ("/cases/case_http/view" if status == 202 else None)
    assert seen[0][0] == {"kind": "PRIVATE_UNKNOWN"} and seen[0][1].startswith("tr_")


@pytest.mark.parametrize("payload", [None, [], 1, "PRIVATE", True, {}, {"case_id": 1}])
def test_all_json_shapes_reach_case_unchanged(api_startup, monkeypatch, payload):
    startup, stream = api_startup
    seen = []
    def execute(self, value, trace_id):
        seen.append(value)
        return CommandResult({"ok": False, "error": {"code": "case.command.invalid_payload", "message_key": "command.invalid_payload"}, "case_view": None})
    monkeypatch.setattr(ApiComposition, "execute_command", execute, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases/case_http/commands", content=json.dumps(payload), headers={"Content-Type": "application/json; charset=utf-8"})
    assert response.status_code == 422 and seen == [payload]
    assert "PRIVATE" not in stream.getvalue()


@pytest.mark.parametrize("content,media,status", [
    (b"{}", "text/plain", 415), (b"{}", "application/problem+json", 415),
    (b"{}", "", 415), (b"{PRIVATE", "application/json", 400),
    (b"\xff", "application/json", 400), (b'{"case_id":"PRIVATE_other"}', "application/json", 400),
    (b"x" * 65, "application/json", 413),
])
def test_transport_failures_never_call_case_or_disclose_input(api_startup, monkeypatch, content, media, status):
    startup, stream = api_startup
    startup = replace(startup, config=replace(startup.config, upload=startup.config.upload.model_copy(update={"json_max_bytes": 64})))
    def forbidden(*args):
        raise AssertionError("Case must not run")
    monkeypatch.setattr(ApiComposition, "execute_command", forbidden, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases/case_http/commands?PRIVATE", content=content, headers={"Content-Type": media, "X-Trace-Id": "PRIVATE"})
    code = {400: "malformed_request", 413: "payload_too_large", 415: "unsupported_media_type"}[status]
    assert response.status_code == status
    assert response.json() == {"ok": False, "error": {"code": "http." + code, "message_key": "http." + code}, "case_view": None}
    assert "PRIVATE" not in response.text and "PRIVATE" not in stream.getvalue()


@pytest.mark.parametrize("declared", [None, b"1", b"999999999"])
def test_stream_limit_checks_actual_bytes_before_db_and_stops_receiving(api_startup, monkeypatch, declared):
    startup, stream = api_startup
    startup = replace(startup, config=replace(startup.config, upload=startup.config.upload.model_copy(update={"json_max_bytes": 8})))
    monkeypatch.setattr(ApiComposition, "execute_command", lambda *a: pytest.fail("DB called"), raising=False)
    app = create_app(startup=startup)
    messages = []
    chunks = iter([b" " * 8, b"x", b"PRIVATE"])
    receives = []
    async def invoke():
        async def receive():
            chunk = next(chunks)
            receives.append(chunk)
            return {"type": "http.request", "body": chunk, "more_body": True}
        async def send(message):
            messages.append(message)
        headers = [(b"content-type", b"application/json")]
        if declared is not None:
            headers.append((b"content-length", declared))
        await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/cases/case_http/commands", "raw_path": b"/cases/case_http/commands", "query_string": b"", "root_path": "", "headers": headers, "server": ("testserver", 80), "client": ("testclient", 123)}, receive, send)
    try:
        asyncio.run(invoke())
        assert messages[0]["status"] == 413 and b"PRIVATE" not in b"".join(m.get("body", b"") for m in messages)
        assert len(receives) <= 2
    finally:
        app.state.composition.close()
    assert '"event":"api.request.rejected_413_count"' in stream.getvalue()
