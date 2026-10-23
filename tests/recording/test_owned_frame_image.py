"""A cross-case unavailable image must never reveal its availability."""
import pytest
from daesingo.recording import RecordingService, RecordingCapabilityError
from daesingo.recording.repository import InMemoryRecordingRepository
from test_ownership_reads import seed, PNG


@pytest.mark.parametrize('content', [PNG, None, b'unknown-format'])
def test_owned_stored_image_and_isolated_failures(content):
    repo = InMemoryRecordingRepository()
    frame, _ = seed(repo)
    # Seed legacy/missing bytes through Recording's repository test boundary.
    repo._frame_content[frame.frame_ref] = content
    service = RecordingService(repo)
    assert callable(getattr(service, 'read_owned_frame_image', None)), 'owned read capability missing'
    for case, ref in [('case-b', frame.frame_ref), ('case-a', 'missing')]:
        with pytest.raises(RecordingCapabilityError) as error:
            service.read_owned_frame_image(case, ref)
        assert error.value.code == 'UNKNOWN_REF'
    if content == PNG:
        image = service.read_owned_frame_image('case-a', frame.frame_ref)
        assert image.content == PNG and image.content_type == 'image/png'
    else:
        with pytest.raises(RecordingCapabilityError) as error:
            service.read_owned_frame_image('case-a', frame.frame_ref)
        assert error.value.code == 'FRAME_NOT_FOUND'
