import pytest

from daesingo.recording import ContractRef, RecordingCapabilityError, RecordingService
from tests.recording.test_local_incident_clip import media, resolution, setup


def test_public_video_read_returns_generated_mp4_without_reencoding(media, tmp_path, monkeypatch):
    service, repo, _, ref, video, adapter, _ = setup(media, tmp_path)
    service._durable_prepared = True
    with service:
        clip = service.build_incident_clip(resolution(service, ref, video, 0.35, 1.26))
    def unexpected(*args, **kwargs): pytest.fail('read must never encode')
    monkeypatch.setattr(adapter, 'materialize', unexpected)
    with RecordingService(repo) as reader:
        opened = reader.open_incident_video(clip.incident_clip_ref)
        with opened.stream:
            content = opened.stream.read()
        assert opened.content_type == 'video/mp4'
        assert len(content) == opened.byte_size == clip.byte_size
        assert b'ftyp' in content[:32]
        again = reader.open_incident_video(clip.incident_clip_ref)
        with again.stream: assert again.stream.read() == content


def test_video_read_missing_and_unavailable_are_distinct(media, tmp_path):
    service, repo, _, ref, video, _, _ = setup(media, tmp_path)
    service._durable_prepared = True
    with service:
        clip = service.build_incident_clip(resolution(service, ref, video, 0.35, 1.26))
    with RecordingService(repo) as reader:
        with pytest.raises(RecordingCapabilityError) as missing: reader.open_incident_video('unknown')
        assert missing.value.code == 'UNKNOWN_REF'
        repo._prepared_content.pop(('incident_clip', clip.incident_clip_ref))
        with pytest.raises(RecordingCapabilityError) as unavailable: reader.open_incident_video(clip.incident_clip_ref)
        assert unavailable.value.code == 'UNAVAILABLE'


@pytest.mark.parametrize('failure', [FileNotFoundError('/media/clip.mp4'), PermissionError('/media/clip.mp4')])
def test_video_read_storage_io_failure_is_unavailable(media, tmp_path, monkeypatch, failure):
    service, repo, _, ref, video, _, _ = setup(media, tmp_path)
    service._durable_prepared = True
    with service:
        clip = service.build_incident_clip(resolution(service, ref, video, 0.35, 1.26))
    def broken(_ref): raise failure
    monkeypatch.setattr(repo, 'get_prepared_content', broken)
    with RecordingService(repo) as reader:
        with pytest.raises(RecordingCapabilityError) as unavailable:
            reader.open_incident_video(clip.incident_clip_ref)
    assert unavailable.value.code == 'UNAVAILABLE'
    assert unavailable.value.__cause__ is None and '/media' not in str(unavailable.value)
