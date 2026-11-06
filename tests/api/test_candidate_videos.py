import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.case.store import CaseNotFound
from daesingo.recording import RecordingCapabilityError
from test_sources import envelope

BODY = b'0123456789'
PATH = '/cases/case_video/candidate-videos/opaque'


@pytest.fixture
def video_app(api_startup, monkeypatch):
    startup, output = api_startup
    monkeypatch.setattr(ApiComposition, 'load_candidate_video', lambda *args: (BODY, 'video/mp4'), raising=False)
    app = create_app(startup=startup)
    yield app, output
    app.state.composition.close()


def test_stored_video_is_inline_with_no_store_and_accept_ranges(video_app):
    with TestClient(video_app[0]) as client:
        for _ in range(2):
            response = client.get(PATH)
            assert response.status_code == 200 and response.content == BODY
            assert response.headers['content-type'] == 'video/mp4'
            assert response.headers['content-disposition'] == 'inline'
            assert response.headers['cache-control'] == 'private, no-store'
            assert response.headers['accept-ranges'] == 'bytes'


@pytest.mark.parametrize('header,expected,content_range', [
    ('bytes=2-5', b'2345', 'bytes 2-5/10'),
    ('bytes=7-', b'789', 'bytes 7-9/10'),
    ('bytes=-3', b'789', 'bytes 7-9/10'),
    ('bytes=0-999', BODY, 'bytes 0-9/10'),
    ('bytes=-999', BODY, 'bytes 0-9/10'),
])
def test_byte_ranges_allow_browser_seeking(video_app, header, expected, content_range):
    with TestClient(video_app[0]) as client:
        response = client.get(PATH, headers={'Range': header})
    assert response.status_code == 206 and response.content == expected
    assert response.headers['content-range'] == content_range
    assert int(response.headers['content-length']) == len(expected)


@pytest.mark.parametrize('header', ['bytes=10-', 'bytes=7-2', 'bytes=-0'])
def test_unsatisfiable_range_is_416(video_app, header):
    with TestClient(video_app[0]) as client:
        response = client.get(PATH, headers={'Range': header})
    assert response.status_code == 416
    assert response.headers['content-range'] == 'bytes */10'


@pytest.mark.parametrize('header', ['invalid', 'items=0-1', 'bytes=one-two', 'bytes=0-1,4-5'])
def test_unsupported_or_malformed_ranges_are_ignored(video_app, header):
    with TestClient(video_app[0]) as client:
        response = client.get(PATH, headers={'Range': header})
    assert response.status_code == 200 and response.content == BODY


@pytest.mark.parametrize('failure,status,code', [
    (CaseNotFound('private'), 404, 'http.not_found'),
    (RecordingCapabilityError('UNKNOWN_REF', 'private'), 404, 'http.not_found'),
    (RecordingCapabilityError('UNAVAILABLE', 'private'), 404, 'http.ref_unavailable'),
    (RecordingCapabilityError('TEMPORARY_FAILURE', 'private'), 503, 'http.dependency_unavailable'),
])
def test_errors_use_existing_private_envelope(video_app, monkeypatch, failure, status, code):
    def fail(*args): raise failure
    monkeypatch.setattr(ApiComposition, 'load_candidate_video', fail)
    with TestClient(video_app[0], raise_server_exceptions=False) as client:
        response = client.get(PATH)
    assert response.status_code == status and response.json() == envelope(code)


def test_if_range_without_issued_validator_returns_full_representation(video_app):
    with TestClient(video_app[0]) as client:
        response = client.get(PATH, headers={'Range': 'bytes=2-5', 'If-Range': '"old"'})
    assert response.status_code == 200 and response.content == BODY


def test_large_range_numbers_do_not_overflow_or_allocate_large_integers(video_app):
    with TestClient(video_app[0]) as client:
        response = client.get(PATH, headers={'Range': 'bytes=' + '9' * 5000 + '-'})
    assert response.status_code == 416
