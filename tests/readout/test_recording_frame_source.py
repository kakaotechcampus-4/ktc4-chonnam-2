from types import SimpleNamespace

import pytest

from daesingo.readout import api, paddle_provider
from daesingo.readout.contracts import InputRef, OverlayTimeReadout
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
        return SimpleNamespace(
            frame_ref=f"fr_{locator['source_offset_sec']:.1f}",
            source_offset_sec=locator["source_offset_sec"] + 0.05,
        )

    def read_frame(self, frame_ref):
        return b"png-bytes"


def test_recording_frame_source_preserves_recording_frame_refs(monkeypatch):
    recording = FakeRecording()
    marker = object()
    monkeypatch.setattr(paddle_provider, "_decode_image", lambda content: marker)

    frames = paddle_provider.RecordingFrameSource(recording).frames("clip_real")

    offsets = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]  # SAMPLE_RATIOS × 10초
    assert [frame.frame_ref for frame in frames] == [f"fr_{100 + o:.1f}" for o in offsets]
    assert [frame.offset_sec for frame in frames] == pytest.approx(offsets)
    assert [frame.frame_offset_sec for frame in frames] == pytest.approx([o + 0.05 for o in offsets])
    assert [frame.image for frame in frames] == [marker] * len(offsets)
    assert recording.offsets == pytest.approx([100 + o for o in offsets])


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


def test_three_second_clip_does_not_request_after_exact_sample_due_to_float_dust(monkeypatch):
    recording = FakeRecording()
    recording.clip.duration_sec = 3.0
    recording.clip.timeline_range.start_sec = 0.0
    span = recording.clip.source_provenance.asset_spans[0]
    span.timeline_range = _range(0.0, 3.0)
    span.source_range = _range(0.0, 3.0)
    monkeypatch.setattr(paddle_provider, "_decode_image", lambda content: object())
    paddle_provider.RecordingFrameSource(recording).frames("clip_real")
    # Recording rejects a returned exact 0.6s frame for a 0.6000000000000001 request.
    assert recording.offsets == [0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4]


def test_incident_position_mapping_does_not_add_float_dust():
    from daesingo.readout.providers import IncidentClipFrames
    recording = FakeRecording()
    recording.clip.timeline_range.start_sec = 0.1
    span = recording.clip.source_provenance.asset_spans[0]
    span.timeline_range = _range(0.1, 3.1)
    span.source_range = _range(0.1, 3.1)
    IncidentClipFrames(recording, "clip_real").read_at(0.2)
    assert recording.offsets == [0.3]


def test_frame_after_requested_asset_span_has_no_overlay_anchor():
    from daesingo.readout.providers import IncidentClipFrames

    recording = FakeRecording()
    # Request at source 109.98s, but Recording's next frame is at 110.03s.
    frame, _, offset = IncidentClipFrames(recording, "clip_real").read_at_with_frame_offset(9.98)
    assert frame.source_offset_sec == pytest.approx(110.03)
    assert offset is None


def test_overlay_readout_serializes_the_decoded_frame_offset(monkeypatch):
    monkeypatch.setattr(paddle_provider, "_decode_image", lambda content: object())
    provider = paddle_provider.PaddleOcrProvider(
        paddle_provider.RecordingFrameSource(FakeRecording(), sample_ratios=(0.2, 0.3))
    )

    def boxes(clip_ref, frame):
        return [paddle_provider.TextBox(f"2026-10-31 14:00:1{int(frame.offset_sec)}", 1.0, ())]

    monkeypatch.setattr(provider, "_boxes", boxes)
    request = api.ReadRequest(
        case_id="case_1",
        candidate_id="candidate_1",
        input_ref=InputRef("clip_real", "readout-native", "SOURCE_DERIVED_INCIDENT_CLIP"),
    )
    run, readout = api.read_overlay_time(request, provider=provider)
    assert run.outcome == "SUCCEEDED"
    payload = readout.to_dict()
    assert payload["contract_version"] == "overlay-time-readout/v1.3"
    assert payload["observation"]["value"] == "2026-10-31T14:00:12+09:00"
    assert [sample["offset_sec"] for sample in payload["samples"]] == [2.0, 3.0]
    assert [sample["frame_offset_sec"] for sample in payload["samples"]] == [2.05, 3.05]
    assert OverlayTimeReadout.from_dict(payload).to_dict() == payload
