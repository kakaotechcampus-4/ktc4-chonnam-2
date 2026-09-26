from types import SimpleNamespace

import pytest

from daesingo.readout import paddle_provider
from daesingo.readout.providers import ProviderError
from daesingo.recording import RecordingCapabilityError


def _range(start, end):
    return SimpleNamespace(start_sec=start, end_sec=end)


class FakeRecording:
    def __init__(self):
        span = SimpleNamespace(
            timeline_range=_range(10.0, 20.0),
            source_range=_range(100.0, 110.0),
            media_stream_ref="ms_video",
        )
        self.clip = SimpleNamespace(
            duration_sec=10.0,
            timeline_range=SimpleNamespace(start_sec=10.0),
            source_provenance=SimpleNamespace(asset_spans=[span]),
        )
        self.offsets = []

    def get_incident_clip(self, clip_ref):
        assert clip_ref == "clip_real"
        return self.clip

    def resolve_frame(self, locator):
        self.offsets.append(locator["source_offset_sec"])
        return SimpleNamespace(frame_ref=f"fr_{locator['source_offset_sec']:.1f}")

    def read_frame(self, frame_ref):
        return b"png-bytes"


def test_recording_frame_source_preserves_recording_frame_refs(monkeypatch):
    recording = FakeRecording()
    marker = object()
    monkeypatch.setattr(paddle_provider, "_decode_image", lambda content: marker)

    frames = paddle_provider.RecordingFrameSource(recording).frames("clip_real")

    assert [frame.frame_ref for frame in frames] == ["fr_103.0", "fr_105.0", "fr_107.0"]
    assert [frame.offset_sec for frame in frames] == [3.0, 5.0, 7.0]
    assert [frame.image for frame in frames] == [marker, marker, marker]
    assert recording.offsets == [103.0, 105.0, 107.0]


def test_recording_frame_source_maps_recording_failure_to_provider_failure(monkeypatch):
    recording = FakeRecording()
    monkeypatch.setattr(
        recording,
        "resolve_frame",
        lambda locator: (_ for _ in ()).throw(RecordingCapabilityError("FRAME_NOT_FOUND", "missing")),
    )

    with pytest.raises(ProviderError) as raised:
        paddle_provider.RecordingFrameSource(recording).frames("clip_real")

    assert (raised.value.kind, raised.value.code) == ("INFRA", "READOUT_FRAME_ACCESS_FAILED")
