"""DerivedAsset HTTP: safe headers and typed failures at the public loader boundary."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.case.store import CaseNotFound, InvalidCaseId
from daesingo.common.db.errors import BeforeCommitFailure, CommitOutcomeUnknown
from daesingo.recording import RecordingCapabilityError
from test_frames import PNG, request
from test_sources import envelope

PATH = '/cases/case_asset/assets/opaque'


@pytest.fixture
def asset_app(api_startup, monkeypatch):
    startup, output = api_startup
    monkeypatch.setattr(ApiComposition, 'load_asset', lambda self, case, ref: (PNG, 'image/png'), raising=False)
    app = create_app(startup=startup)
    yield app, output
    app.state.composition.close()


def test_asset_headers_bytes_and_range_is_ignored(asset_app):
    app, _ = asset_app
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get(PATH, headers={'Range': 'bytes=0-1'})
            assert response.status_code == 200 and response.content == PNG
            assert response.headers['content-type'] == 'image/png'
            assert response.headers['content-length'] == str(len(PNG))
            assert response.headers['content-disposition'] == 'attachment; filename="daesingo_asset.png"'
            assert response.headers['cache-control'] == 'private, no-store'
            assert 'content-range' not in response.headers


@pytest.mark.parametrize('failure,status,code', [
    (CaseNotFound('PRIVATE'), 404, 'http.not_found'),
    (InvalidCaseId('PRIVATE'), 404, 'http.not_found'),
    *((RecordingCapabilityError(c, 'PRIVATE /secret/original.mp4'), s, h) for c, s, h in (
        ('UNKNOWN_REF', 404, 'http.not_found'), ('INVALID_REF_KIND', 404, 'http.not_found'),
        ('UNAVAILABLE', 404, 'http.ref_unavailable'), ('TEMPORARY_FAILURE', 503, 'http.dependency_unavailable'),
        ('OTHER', 500, 'http.internal_error'))),
    (BeforeCommitFailure('disconnect'), 503, 'http.dependency_unavailable'),
    (CommitOutcomeUnknown(), 500, 'http.internal_error'),
    (ValueError('PRIVATE validation'), 500, 'http.internal_error'),
    (RuntimeError('PRIVATE TEMPORARY_FAILURE mysql://secret'), 500, 'http.internal_error'),
])
def test_asset_typed_errors_and_diagnostics_are_private(asset_app, monkeypatch, failure, status, code):
    app, output = asset_app
    def fail(*args):
        raise failure
    monkeypatch.setattr(ApiComposition, 'load_asset', fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.get(PATH + '?filename=PRIVATE', headers={'Authorization': 'PRIVATE'})
        assert result.status_code == status and result.json() == envelope(code)
        assert 'content-disposition' not in result.headers
    assert not any(s in output.getvalue() + result.text for s in ('PRIVATE', '/secret', 'Traceback', 'mysql://'))


def test_unrecognized_media_type_cannot_guess_a_filename(asset_app, monkeypatch):
    app, _ = asset_app
    monkeypatch.setattr(ApiComposition, 'load_asset', lambda *args: (PNG, 'text/plain; PRIVATE'))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(PATH)
        assert response.status_code == 500 and response.json() == envelope('http.internal_error')
        assert 'content-disposition' not in response.headers


def test_assets_do_not_consume_frame_permits(asset_app, monkeypatch):
    app, _ = asset_app
    async def run():
        entered = asyncio.Queue()
        release = asyncio.Event()
        async def send(message):
            if message['type'] == 'http.response.body' and message.get('body'):
                await entered.put(True)
                await release.wait()
        tasks = [asyncio.create_task(request(app, path=PATH, send=send)) for _ in range(3)]
        try:
            for _ in tasks:
                await asyncio.wait_for(entered.get(), 3)
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.run(run())
