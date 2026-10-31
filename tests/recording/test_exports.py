"""Real exports: wrong crop, missing byte measurement or mutable refs break these."""
import struct
import subprocess

import pytest

from daesingo.recording import RecordingService, RecordingCapabilityError
from daesingo.recording.repository import InMemoryRecordingRepository
from daesingo.recording.models import IncidentClip, FrameRef


@pytest.fixture
def export_service(tmp_path):
    video = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=s=160x96:r=10:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=30)
    frame = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
        "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"],
        check=True, capture_output=True, timeout=30).stdout
    repo = InMemoryRecordingRepository()
    clip = IncidentClip.model_validate({"contract": "IncidentClip", "contract_version": "analysis-source-derived/v1",
        "incident_clip_ref": "clip", "asset_kind": "INCIDENT_CLIP", "source_provenance": {
            "timeline_ref": {"timeline_id": "tl", "revision": 1}, "requested_range": {"start_sec": 0, "end_sec": 1},
            "asset_spans": [{"sequence": 0, "source_asset_ref": "source", "media_stream_ref": "video",
                "source_range": {"start_sec": 0, "end_sec": 1}, "timeline_range": {"start_sec": 0, "end_sec": 1}}]},
        "media_stream_refs": ["video"], "byte_size": video.stat().st_size, "availability": "AVAILABLE",
        "duration_sec": 1, "timeline_ref": {"timeline_id": "tl", "revision": 1},
        "timeline_range": {"start_sec": 0, "end_sec": 1}})
    repo.add_prepared_media(clip, video.read_bytes(), case_id="case")
    repo.add_frame(FrameRef(contract="FrameRef", contract_version="source-asset-media-stream/v1",
        frame_ref="frame", media_stream_ref="video", source_offset_sec=.2), content=frame, image_format="png")
    assert hasattr(RecordingService, "export_plate_image"), "Recording export capability missing"
    from daesingo.recording.exports import LocalExportMaterializer
    with RecordingService(repo, export_materializer=LocalExportMaterializer(temp_root=tmp_path), case_id="case") as service:
        yield service, repo


def plate(**overrides):
    return {"incident_clip_ref": "clip", "frame_ref": "frame", "plate_bbox_xywh": [10, 10, 40, 20],
        "max_byte_size": 30_000_000, **overrides}


def test_plate_actual_crop_size_provenance_and_immutable_regeneration(export_service):
    service, repo = export_service
    first = service.export_plate_image(**plate())
    content = service.open_derived_asset(first.derived_asset_ref).stream.read()
    assert first.derived_role == "PLATE_IMAGE" and first.byte_size == len(content) > 0
    facts = service.lookup_asset_facts({"kind": "derived_asset", "ref": first.derived_asset_ref})
    assert facts.derived_role == "PLATE_IMAGE" and facts.byte_size == first.byte_size and facts.availability == "AVAILABLE"
    assert struct.unpack(">II", content[16:24]) == (40, 20)
    assert {(r.kind, r.ref) for r in first.source_refs} >= {("incident_clip", "clip"), ("source_asset", "source")}
    transform = service.get_export_transform(first.transform_ref)
    assert transform["input"] == plate() and transform["operations"][0]["crop_xywh"] == [10, 10, 40, 20]
    second = service.export_plate_image(**plate(plate_bbox_xywh=[11, 10, 40, 20]))
    assert first.derived_asset_ref != second.derived_asset_ref and first.transform_ref != second.transform_ref
    assert service.get_derived_asset(first.derived_asset_ref) == first
    assert service.open_derived_asset(first.derived_asset_ref).stream.read() == content


def test_plate_attempts_limit_inside_single_call_and_distinguishes_exhaustion(export_service):
    service, repo = export_service
    result = service.export_plate_image(**plate(max_byte_size=150))
    assert 0 < result.byte_size <= 150
    assert len(service.get_export_transform(result.transform_ref)["operations"]) > 1
    before = repo.get_case_assets("case")
    with pytest.raises(RecordingCapabilityError) as raised:
        service.export_plate_image(**plate(max_byte_size=1))
    assert raised.value.code == "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE"
    assert repo.get_case_assets("case") == before


@pytest.mark.parametrize("changes", [{"frame_ref": "missing"}, {"plate_bbox_xywh": [-1, 0, 4, 2]},
    {"plate_bbox_xywh": [150, 0, 40, 20]}, {"max_byte_size": True}, {"max_byte_size": 0}])
def test_plate_invalid_inputs_are_safe_generation_failures(export_service, changes):
    service, _ = export_service
    with pytest.raises(RecordingCapabilityError) as raised:
        service.export_plate_image(**plate(**changes))
    assert raised.value.code == "PLATE_IMAGE_EXPORT_FAILED"
    assert "missing" not in str(raised.value)


@pytest.mark.parametrize("needed,value", [(False, None), (True, "2026-06-20T14:19:56+09:00")])
def test_report_preserves_clip_and_stamps_requested_value(export_service, needed, value):
    service, repo = export_service
    asset = service.export_report_video(incident_clip_ref="clip", post_stamp={"needed": needed, "value": value})
    opened = service.open_derived_asset(asset.derived_asset_ref)
    try:
        content = opened.stream.read()
    finally:
        opened.stream.close()
    assert asset.derived_role == "REPORT_VIDEO" and asset.byte_size == len(content) > 0
    assert asset.duration_sec == 1
    assert service.get_export_transform(asset.transform_ref)["input"] == {
        "incident_clip_ref": "clip", "post_stamp": {"needed": needed, "value": value}}
    assert b"ftyp" in content[:32]


def test_frame_outside_clip_is_not_exportable(export_service):
    service, repo = export_service
    original = repo.get_frame("frame")
    repo.add_frame(original.model_copy(update={"frame_ref": "outside", "source_offset_sec": 1.0}))
    with pytest.raises(RecordingCapabilityError) as raised:
        service.export_plate_image(**plate(frame_ref="outside"))
    assert raised.value.code == "PLATE_IMAGE_EXPORT_FAILED"
