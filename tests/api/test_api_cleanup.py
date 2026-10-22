"""Cleanup belongs to API lifespan and upload ownership, never publish rows."""
import asyncio
from dataclasses import replace
import os
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
import pytest
from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.api.upload import receive_source, UploadAborted
from starlette.requests import ClientDisconnect
from test_sources import MEDIA, multipart


def old(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'abc')
    os.utime(path, (1, 1))
    return path


def test_api_lifespan_scans_once_and_closes_background_thread(api_startup):
    startup, _ = api_startup
    residue = old(startup.config.media_root/'staging'/'upload-abandon_')
    published = old(startup.config.media_root/'source'/'upload-publish_')
    app = create_app(startup=startup)
    assert residue.exists()
    with TestClient(app):
        assert not residue.exists(), 'API startup cleanup missing'
        assert published.exists()
        owner = app.state.composition.cleanup
        assert owner.thread.is_alive()
        later = old(residue)
        owner.start()
        assert later.exists()
    assert not owner.thread.is_alive()


@pytest.mark.parametrize('outcome', ['complete', 'idle', 'duration', 'disconnect', 'exception', 'cancel'])
def test_old_active_staging_survives_scan_then_abort_residue_is_reclaimable(api_startup, monkeypatch, outcome):
    startup, _ = api_startup
    app = create_app(startup=startup)
    composition = app.state.composition
    settings = startup.config.upload.model_copy(update={
        'idle_timeout_sec': 1, 'max_duration_sec': 1 if outcome == 'duration' else 2})
    object.__setattr__(startup, 'config', replace(startup.config, upload=settings))
    calls = []
    from daesingo.api import upload
    publish = upload.publish
    def during_publish(path, root):
        os.utime(path, (1, 1))
        composition.cleanup.scan()
        assert path.exists(), 'closed staging must remain leased through publish'
        return publish(path, root)
    monkeypatch.setattr(upload, 'publish', during_publish)
    class Request:
        headers = MEDIA
        scope = {'extensions': {'daesingo.close': lambda: calls.append('closed')}}
        class state:
            pass
        async def stream(self):
            yield multipart() if outcome == 'complete' else multipart()[:-14]
            path = next((startup.config.media_root/'staging').glob('upload-*'))
            os.utime(path, (1, 1))
            composition.cleanup.scan()
            assert path.exists(), 'active upload deleted by cleanup'
            if outcome in ('idle', 'duration'):
                # Deterministic receive timeout, no actual sleeping.
                raise TimeoutError()
            if outcome == 'disconnect':
                raise ClientDisconnect()
            if outcome == 'exception':
                raise RuntimeError('PRIVATE')
            if outcome == 'cancel':
                raise asyncio.CancelledError()
    try:
        if outcome == 'complete':
            result, _ = asyncio.run(receive_source(Request(), composition))
            assert result.parent == startup.config.media_root/'source'
            assert result.exists()
        else:
            error = (asyncio.CancelledError if outcome == 'cancel' else
                     RuntimeError if outcome == 'exception' else UploadAborted)
            with pytest.raises(error):
                asyncio.run(receive_source(Request(), composition))
            # Closing a buffered writer may refresh mtime. Age the abandoned
            # residue after close, just as elapsed wall time would do.
            for path in (startup.config.media_root/'staging').glob('upload-*'):
                os.utime(path, (1, 1))
            composition.cleanup.scan()
            assert not list((startup.config.media_root/'staging').glob('upload-*'))
        assert list((startup.config.media_root/'source').glob('*')) == ([result] if outcome == 'complete' else [])
    finally:
        composition.close()


def test_api_startup_failure_closes_all_owned_resources(api_startup, monkeypatch):
    startup, _ = api_startup
    app = create_app(startup=startup)
    composition = app.state.composition
    assert hasattr(composition, 'cleanup'), 'API cleanup lifecycle missing'
    def fail():
        raise RuntimeError('startup scan failed')
    monkeypatch.setattr(composition.cleanup, 'start', fail)
    with pytest.raises(RuntimeError, match='startup scan failed'):
        with TestClient(app):
            pass
    assert composition._closed and composition.cleanup.thread is None


def test_api_startup_error_is_not_replaced_by_secondary_close_failure(api_startup, monkeypatch):
    startup, _ = api_startup
    app = create_app(startup=startup)
    composition = app.state.composition
    assert composition.cleanup is not None
    def fail_start():
        raise RuntimeError('primary startup')
    def fail_close():
        raise ValueError('secondary close')
    monkeypatch.setattr(composition.cleanup, 'start', fail_start)
    monkeypatch.setattr(composition.cleanup, 'stop_and_join', fail_close)
    with pytest.raises(RuntimeError, match='primary startup'):
        with TestClient(app):
            pass
    assert composition._closed and composition.cleanup_failed
