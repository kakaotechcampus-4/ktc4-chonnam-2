"""Real HTTP writer must protect publish through DB callback termination."""
import os
import asyncio
from threading import Event

import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.api import upload


@pytest.mark.parametrize('failure', [False, True])
def test_actual_upload_holds_publish_lease_before_publish_through_registration(api_startup, monkeypatch, failure):
    startup, _ = api_startup
    app = create_app(startup=startup)
    comp = app.state.composition
    cleaners = [s for s in comp.cleanup.scanners if s.kind == 'orphan']
    assert len(cleaners) == 1, 'API P-6 composition missing'
    cleaner, = cleaners
    cleaner.registration = lambda locator: False
    original = upload.publish
    observed = []
    def publish(path, root):
        final = original(path, root)
        os.utime(final, (1, 1))
        assert cleaner.scan().count == 0
        assert final.exists()
        observed.append('publish')
        return final
    def register(self, case_id, path, filename):
        assert cleaner.scan().count == 0
        assert path.exists()
        observed.append('registration')
        if failure:
            raise RuntimeError('synthetic rollback')
        cleaner.registration = lambda locator: True
        return {'case_id': case_id}
    monkeypatch.setattr(upload, 'publish', publish)
    monkeypatch.setattr(ApiComposition, 'register_source', register)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post('/cases/case-synthetic/sources', files={'file': ('synthetic.mp4', b'synthetic', 'video/mp4')})
    assert response.status_code == (500 if failure else 201)
    assert observed == ['publish', 'registration']
    assert cleaner.scan().count == int(failure)


def test_route_cancellation_waits_for_registration_thread_before_releasing_lease(api_startup, monkeypatch):
    from daesingo.api.routes_sources import sources_router
    from test_sources import MEDIA, multipart
    startup, _ = api_startup
    app = create_app(startup=startup)
    comp = app.state.composition
    cleaner = next(s for s in comp.cleanup.scanners if s.kind == 'orphan')
    cleaner.registration = lambda locator: False
    entered, finish, done = Event(), Event(), Event()
    paths = []
    def register(self, case_id, path, filename):
        paths.append(path)
        os.utime(path, (1, 1))
        entered.set()
        assert finish.wait(10)
        assert path.exists()
        done.set()
        return {'case_id': case_id}
    monkeypatch.setattr(ApiComposition, 'register_source', register)
    class Request:
        headers = MEDIA
        async def stream(self):
            yield multipart()
    async def run():
        endpoint = sources_router(comp).routes[0].endpoint
        task = asyncio.create_task(endpoint('case-synthetic', Request()))
        try:
            assert await asyncio.to_thread(entered.wait, 10)
            task.cancel()
            # This handshake is the storage callback's explicit completion,
            # not a timing-based assumption about cancellation or DB release.
            assert cleaner.scan().count == 0 and not done.is_set()
        finally:
            finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert done.is_set() and paths[0].exists()
        assert cleaner.scan().count == 1
    try:
        asyncio.run(run())
    finally:
        finish.set()
        comp.close()


def test_orphan_lease_wait_consumes_existing_upload_deadline(api_startup, monkeypatch):
    from contextlib import contextmanager
    from daesingo.common.storage.cleanup import OrphanPublishScanner
    from test_sources import MEDIA, multipart
    startup, _ = api_startup
    app = create_app(startup=startup)
    comp = app.state.composition
    clock = [100.0]
    original = OrphanPublishScanner.in_use
    @contextmanager
    def delayed(self):
        with original(self) as value:
            clock[0] += 2000  # deterministic simulated lock wait, not a sleep
            yield value
    monkeypatch.setattr(OrphanPublishScanner, 'in_use', delayed)
    monkeypatch.setattr(upload, 'monotonic', lambda: clock[0])
    closed = []
    class Request:
        headers = MEDIA
        scope = {'extensions': {'daesingo.close': lambda: closed.append(True)}}
        class state:
            pass
        async def stream(self):
            yield multipart()
    async def run():
        with pytest.raises(upload.UploadAborted):
            async with upload.leased_source(Request(), comp):
                pytest.fail('lease wait escaped upload deadlines')
    try:
        asyncio.run(run())
        assert closed == [True]
    finally:
        comp.close()


@pytest.mark.parametrize('boundary', ['open', 'publish'])
def test_observed_producer_root_replacement_is_rejected(api_startup, monkeypatch, boundary):
    from contextlib import contextmanager
    from fastapi import HTTPException
    from daesingo.common.storage.cleanup import OrphanPublishScanner
    from test_sources import MEDIA, multipart
    startup, _ = api_startup
    app = create_app(startup=startup)
    comp = app.state.composition
    root = startup.config.media_root
    moved = root.parent/(root.name+'-moved')
    replaced = []
    def change():
        if os.name == 'nt':
            with pytest.raises(PermissionError):
                root.rename(moved)
        else:
            root.rename(moved)
            root.mkdir()
            replaced.append(True)
    if boundary == 'open':
        original = OrphanPublishScanner.in_use
        @contextmanager
        def lease(self):
            with original(self) as verify:
                change()
                yield verify
        monkeypatch.setattr(OrphanPublishScanner, 'in_use', lease)
    else:
        original_finish = upload._MultipartFile.finish
        def finish(self):
            original_finish(self)
            change()
        monkeypatch.setattr(upload._MultipartFile, 'finish', finish)
    class Request:
        headers = MEDIA
        async def stream(self):
            yield multipart()
    async def run():
        if os.name == 'nt':
            async with upload.leased_source(Request(), comp) as (path, filename):
                assert path.exists() and not replaced
        else:
            with pytest.raises(HTTPException) as error:
                async with upload.leased_source(Request(), comp):
                    pytest.fail('replacement root accepted')
            assert error.value.status_code == 503 and replaced
            assert not (root/'source').exists()
    try:
        asyncio.run(run())
    finally:
        comp.close()
