import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from daesingo.api.public_access import PublicHTTPMiddleware
from daesingo.common.config import PublicSettings


def test_no_mode_or_approval_defaults_to_closed_public_boundary():
    settings = PublicSettings()
    assert settings.mode == "a1" and settings.policy_file is None


def test_empty_drip_cannot_extend_entire_body_deadline(monkeypatch):
    ticks = iter((0, 1, 14, 16))
    monkeypatch.setattr("daesingo.api.public_access.monotonic", lambda: next(ticks))
    reads, replies = [], []
    async def app(scope, receive, send):
        while True:
            await receive()
    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"", "more_body": True}
    async def send(message):
        replies.append(message)
    public = SimpleNamespace(origin=lambda headers: None)
    middleware = PublicHTTPMiddleware(app, composition=SimpleNamespace(public=public))
    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/public/session", "headers": []}, receive, send))
    assert len(reads) == 2
    assert replies[0]["status"] == 422


def test_enter_success_then_cancellation_releases_lease_without_masking(monkeypatch):
    calls = []
    @contextmanager
    def lease():
        calls.append("enter")
        try:
            yield
        finally:
            calls.append("exit")
    public = SimpleNamespace(token_owner=lambda request: b"owner", transaction=lambda cb: cb(None),
        ownership=SimpleNamespace(require_owner=lambda *args, **kw: None),
        cleanup=SimpleNamespace(scanners=[SimpleNamespace(kind="orphan", in_use=lease)]))
    async def storage(fn, *args):
        result = fn(*args)
        if fn.__name__ == "enter_guard":
            raise asyncio.CancelledError
        return result
    monkeypatch.setattr("daesingo.api.public_access._storage_call", storage)
    async def forbidden(*args):
        pytest.fail("app must not run after cancelled enter")
    middleware = PublicHTTPMiddleware(forbidden, composition=SimpleNamespace(public=public))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(middleware({"type": "http", "method": "GET", "path": "/cases/case_1/view", "headers": []}, forbidden, forbidden))
    assert calls == ["enter", "exit"]
