"""Actual HTTP emit paths, MySQL composition and sensitive input canaries."""
import json

import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.common.logging.catalog import validate_event, EVENTS
from test_cases_view_mysql import api_db
from test_sources import multipart, MEDIA

pytestmark = pytest.mark.mysql


@pytest.mark.mysql_check('observability', 'catalog', parameter='api')
@pytest.mark.mysql_check('observability', 'privacy', parameter='http_inputs')
def test_http_catalog_checks_real_emitters_and_never_exposes_private_inputs(api_db, monkeypatch):
    startup, output, engine = api_db
    private = ('12가3456', '37.123456,127.123456 상세 위치', 'PRIVATE_VIDEO_FRAME_BYTES',
               'PRIVATE_AI_REQUEST_RESPONSE', 'PRIVATE_FREE_TEXT', 'sk_PRIVATE_API_KEY',
               'PRIVATE_ACCESS_TOKEN', 'PRIVATE_SECRET', 'PRIVATE_RAW_PROVIDER')
    def register(self, case_id, path, original_filename):
        assert path.read_bytes() == '|'.join(private).encode()
        return {'case_id':case_id, 'source_asset_ref':'safe', 'case_view':{}}
    monkeypatch.setattr(ApiComposition, 'register_source', register)
    app = create_app(startup=startup)
    with TestClient(app) as client:
        created = client.post('/cases', content='|'.join(private)).json()
        identity = created['case_id']
        assert client.get(f'/cases/{identity}/view').status_code == 200
        assert client.get('/cases/missing/view').status_code == 404
        assert client.get('/health/ready').status_code == 200
        assert client.get(f'/cases/{identity}/frames/unknown').status_code == 404
        assert client.get(f'/cases/{identity}/assets/unknown').status_code == 404
        assert client.post(f'/cases/{identity}/sources', headers=MEDIA,
            content=multipart(filename='private-12가3456.mp4', content='|'.join(private).encode())).status_code == 201
        assert client.post(f'/cases/{identity}/sources', content='|'.join(private),
            headers={'content-type':'application/octet-stream'}).status_code == 415
        assert client.post(f'/cases/{identity}/commands', content='|'.join(private),
            headers={'content-type':'application/json'}).status_code == 400
        assert client.post(f'/cases/{identity}/commands',
            content=b'x'*(startup.config.upload.json_max_bytes+1),
            headers={'content-type':'application/json'}).status_code == 413
        # Existing source-limit emitter, without transferring a GiB body.
        assert client.post(f'/cases/{identity}/sources', headers={
            'content-type':'multipart/form-data; boundary=boundary',
            'content-length':str(startup.config.upload.max_bytes+1)}).status_code == 413
    captured = [json.loads(line) for line in output.getvalue().splitlines()]
    events = [value for value in captured if value['event'] in EVENTS]
    for value in events:
        validate_event(value)
    names = {e['event'] for e in events}
    assert {'api.view.completed','api.view.request_rate','api.view.latency_ms',
        'api.request.completed','api.request.rejected_413_count','api.ready.completed','api.upload.failed',
        'api.frame.request_rate','api.frame.wait_ms','api.frame.latency_ms',
        'api.asset.download_latency_ms','api.asset.bytes','api.upload.bytes',
        'api.upload.duration_ms','api.upload.rejected_413_count','api.request.failed'} <= names
    assert any(e['event']=='api.request.completed' and e['status']=='413' for e in events)
    assert sum(e['event']=='api.view.request_rate' for e in events) == 2
    assert sum(e['event']=='api.view.latency_ms' for e in events) == 2
    assert {e['status'] for e in events if e['event']=='api.upload.failed'} == {'413','415'}
    assert not any(value in output.getvalue() for value in (*private,str(startup.config.media_root)))
    assert engine.pool.checkedout() == 0
