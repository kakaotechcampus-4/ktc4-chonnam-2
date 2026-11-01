"""Runtime issuance seam; Case position/selection implementations are not shipped here."""
from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.db.errors import CommitOutcomeUnknown, BeforeCommitFailure
from daesingo.recording import RecordingCapabilityError
from test_search_handlers import fixtures


def inputs():
    from daesingo.search import CandidateEvent
    value = fixtures()[1].candidates[0].model_dump(mode="json")
    value["span"].update(start_ms=1000, end_ms=2000, representative_ms=1500)
    candidate = CandidateEvent.model_validate(value)
    value.update(candidate_id="candidate-second", rank=2)
    value["span"].update(start_ms=4000, end_ms=5000, representative_ms=4500)
    second = CandidateEvent.model_validate(value)
    return SimpleNamespace(case_id="case", timeline_ref={"timeline_id": candidate.span.timeline_id,
        "revision": candidate.span.timeline_revision}, video_stream_refs=("video", "video-other"),
        candidate=candidate, frames_current=True, thumbnail_candidates=(candidate, second))


def setup(*, error=None, cancel=False, position=None):
    data, calls = inputs(), []
    context = ExecutionContext("exec", "job", "case", "INCIDENT_CLIP_BUILD", 1, "trace")
    clip = SimpleNamespace(model_dump=lambda **kw: {"preview": True})
    # These are explicit test-only Case stand-ins. Production uses neither.
    def preview(clip_json, span, representative_ms):
        assert clip_json == {"preview": True} and representative_ms == 1500
        calls.append("preview-position")
        return ("video", 1.5) if position is None else position
    def thumbnail(resolution, span, representative_ms):
        assert resolution["requested_range"] == {"start_sec": span["start_ms"] / 1000,
                                                  "end_sec": span["end_ms"] / 1000}
        calls.append(("thumbnail-position", representative_ms))
        return ("video", 1.5) if representative_ms == 1500 else ("video-other", .5)
    class Recording:
        def get_media_stream(self, ref):
            calls.append(("stream", ref))
            return SimpleNamespace(media_type="VIDEO", source_asset_ref="asset-" + ref)
        def owns_asset(self, case_id, ref):
            assert case_id == "case"
            return True
        def resolve_span(self, timeline, requested, *, media_stream_refs):
            assert timeline == data.timeline_ref and media_stream_refs == list(data.video_stream_refs)
            calls.append(("span", requested))
            return SimpleNamespace(model_dump=lambda **kw: {"requested_range": requested})
        def resolve_frame(self, locator):
            calls.append(("frame", locator))
            assert locator["kind"] == "STREAM_POSITION"
            if cancel: context.cancel_signal.request()
            if error: raise error
            return SimpleNamespace(frame_ref="frame-" + locator["media_stream_ref"])
    return data, context, clip, Recording(), preview, thumbnail, calls


def issuer(preview, thumbnail):
    return import_module("daesingo.worker.incident_frames").IncidentFrameIssuer(
        preview_position=preview, candidate_position=thumbnail)


def test_preview_and_thumbnail_share_result_but_other_candidate_resolves_own_range():
    data, ctx, clip, recording, preview, thumbnail, calls = setup()
    result = issuer(preview, thumbnail)(ctx, data, clip, recording)
    assert result == {"preview_frame_ref": "frame-video", "candidate_frame_refs": {
        data.candidate.candidate_id: "frame-video", "candidate-second": "frame-video-other"}}
    assert len([c for c in calls if c[0] == "frame"]) == 2
    assert [c[1] for c in calls if c[0] == "span"] == [
        {"start_sec": 1, "end_sec": 2}, {"start_sec": 4, "end_sec": 5}]


@pytest.mark.parametrize("code", ["FRAME_NOT_FOUND", "STREAM_UNAVAILABLE", "OUT_OF_RANGE", "TEMPORARY_FAILURE"])
def test_allowed_frame_refusal_is_null_and_same_position_not_retried(code):
    data, ctx, clip, recording, preview, thumbnail, calls = setup(error=RecordingCapabilityError(code, "private"))
    assert issuer(preview, thumbnail)(ctx, data, clip, recording) == {
        "preview_frame_ref": None, "candidate_frame_refs": {data.candidate.candidate_id: None, "candidate-second": None}}
    assert len([c for c in calls if c[0] == "frame"]) == 2


@pytest.mark.parametrize("error", [RecordingCapabilityError("UNKNOWN_REF", "bad binding"),
    RecordingCapabilityError("UNKNOWN_CODE", "private"), OperationalError("private", {}, Exception("db")),
    CommitOutcomeUnknown(), BeforeCommitFailure("db"), ValueError("persistence"), OSError("persistence")])
def test_unapproved_errors_propagate(error):
    data, ctx, clip, recording, preview, thumbnail, _ = setup(error=error)
    with pytest.raises(type(error)):
        issuer(preview, thumbnail)(ctx, data, clip, recording)


def test_cancel_after_frame_does_not_publish_null_success():
    data, ctx, clip, recording, preview, thumbnail, calls = setup(cancel=True)
    with pytest.raises(CancellationRequested): issuer(preview, thumbnail)(ctx, data, clip, recording)
    assert len([c for c in calls if c[0] == "frame"]) == 1


def test_stale_selection_or_generation_never_calls_case_or_recording():
    data, ctx, clip, recording, preview, thumbnail, calls = setup()
    data.frames_current = False
    assert issuer(preview, thumbnail)(ctx, data, clip, recording) == {
        "preview_frame_ref": None, "candidate_frame_refs": {}}
    assert calls == []


@pytest.mark.parametrize("mode", ["foreign", "audio", "unselected", "negative", "nan"])
def test_position_must_be_explicit_owned_video(mode):
    data, ctx, clip, recording, preview, thumbnail, calls = setup(
        position=("unknown", 1) if mode == "unselected" else
        ("video", -1) if mode == "negative" else ("video", float("nan")) if mode == "nan" else None)
    if mode == "foreign": recording.owns_asset = lambda *args: False
    if mode == "audio": recording.get_media_stream = lambda ref: SimpleNamespace(media_type="AUDIO", source_asset_ref="asset")
    with pytest.raises(ValueError): issuer(preview, thumbnail)(ctx, data, clip, recording)
    assert not [c for c in calls if c[0] == "frame"]


def test_case_ambiguity_is_null_without_frame_call():
    data, ctx, clip, recording, _, _, calls = setup()
    assert issuer(lambda *args: None, lambda *args: None)(ctx, data, clip, recording) == {
        "preview_frame_ref": None, "candidate_frame_refs": {data.candidate.candidate_id: None, "candidate-second": None}}
    assert not [c for c in calls if c[0] == "frame"]


def test_case_or_span_errors_are_never_caught_as_frame_refusals():
    data, ctx, clip, recording, preview, thumbnail, calls = setup()
    def fail(*args, **kwargs): raise RecordingCapabilityError("TEMPORARY_FAILURE", "not frame issuance")
    with pytest.raises(RecordingCapabilityError): issuer(fail, thumbnail)(ctx, data, clip, recording)
    recording.resolve_span = fail
    with pytest.raises(RecordingCapabilityError): issuer(preview, thumbnail)(ctx, data, clip, recording)


def test_three_candidates_are_issued_without_reusing_selected_clip_provenance():
    from daesingo.search import CandidateEvent
    data, ctx, clip, recording, preview, thumbnail, calls = setup()
    third = data.thumbnail_candidates[-1].model_dump(mode="json")
    third.update(candidate_id="candidate-third", rank=3)
    third["span"].update(start_ms=6000, end_ms=7000, representative_ms=6500)
    data.thumbnail_candidates += (CandidateEvent.model_validate(third),)
    def positions(resolution, span, representative_ms):
        if representative_ms == 6500:
            assert resolution["requested_range"] == {"start_sec": 6, "end_sec": 7}
            return "video-other", .7
        return thumbnail(resolution, span, representative_ms)
    result = issuer(preview, positions)(ctx, data, clip, recording)
    assert len(result["candidate_frame_refs"]) == 3
    assert len([c for c in calls if c[0] == "frame"]) == 3  # preview + 3 thumbnails, one shared
    assert [c[1] for c in calls if c[0] == "span"][-1] == {"start_sec": 6, "end_sec": 7}


@pytest.mark.parametrize("payload", [
    {"incident_clip_ref": "clip"},
    {"incident_clip_ref": "clip", "preview_frame_ref": None, "candidate_frame_refs": None},
    {"incident_clip_ref": "clip", "preview_frame_ref": "frame", "candidate_frame_refs": {"candidate": "frame", "b": None}},
])
def test_worker_reader_accepts_legacy_and_nullable_payload_without_mutating_receipt(payload):
    module = import_module("daesingo.worker.produced_reader")
    original = deepcopy(payload)
    row = {"kind": "incident_clip_result", "ref": "receipt", "job_kind": "INCIDENT_CLIP_BUILD",
           "execution_id": "exec", "case_id": "case", "payload": payload}
    conn = SimpleNamespace(execute=lambda statement: SimpleNamespace(
        mappings=lambda: SimpleNamespace(one_or_none=lambda: row)))
    result = module.worker_produced_reader()(conn, "INCIDENT_CLIP_BUILD", ({"kind": "incident_clip_result", "ref": "receipt"},))
    assert result == {**payload, "preview_frame_ref": payload.get("preview_frame_ref"),
                      "candidate_frame_refs": payload.get("candidate_frame_refs") or {}}
    assert payload == original


@pytest.mark.parametrize("update", [
    {"incident_clip_ref": ""}, {"preview_frame_ref": {"frame_ref": "frame"}}, {"preview_frame_ref": 1},
    {"preview_frame_ref": ""}, {"candidate_frame_refs": []}, {"candidate_frame_refs": {"a": {"frame_ref": "frame"}}},
    {"candidate_frame_refs": {"a": True}}, {"candidate_frame_refs": {"": None}},
    {"candidate_frame_refs": {str(i): None for i in range(4)}},
])
def test_worker_consumer_rejects_malformed_refs(update):
    module = import_module("daesingo.worker.produced_reader")
    with pytest.raises(ValueError): module.assemble_produced("INCIDENT_CLIP_BUILD", ({"incident_clip_ref": "clip", **update},))


def test_non_clip_payload_keeps_existing_single_object_semantics():
    module = import_module("daesingo.worker.produced_reader")
    assert module.assemble_produced("OTHER", ({"x": 1},)) == {"x": 1}
    with pytest.raises(ValueError): module.assemble_produced("OTHER", ({"x": 1}, {"x": 2}))
