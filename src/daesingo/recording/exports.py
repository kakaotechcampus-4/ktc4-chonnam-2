"""Recording-owned export requests and media strategy; no Evidence policy here."""
import copy
import hashlib
import json
import struct
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import RecordingCapabilityError
from .media_content import actual_media_type, png
from .models import ContractRef, DerivedAsset


def export_fingerprint(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    incident_clip_ref: str = Field(min_length=1)


class PlateImageRequest(_Request):
    frame_ref: str = Field(min_length=1)
    plate_bbox_xywh: list[int] = Field(min_length=4, max_length=4)
    max_byte_size: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_bbox(self):
        x, y, w, h = self.plate_bbox_xywh
        if min(x, y) < 0 or min(w, h) <= 0:
            raise ValueError("invalid plate region")
        return self


class PostStamp(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    needed: bool
    value: str | None

    @model_validator(mode="after")
    def valid_value(self):
        if self.needed:
            value = datetime.fromisoformat(self.value) if self.value is not None else None
            if value is None or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("offset-aware stamp value required")
        elif self.value is not None:
            raise ValueError("unused stamp value")
        return self


class ReportVideoRequest(_Request):
    post_stamp: PostStamp


class LocalExportMaterializer:
    """Bounded PNG downscale and H.264 text stamping on detached bytes.

    PNG starts at the requested full crop. Only an actual size excess triggers
    downscale; the 1x1 attempt is the finite last candidate. These are Recording
    strategy values, not submission policy or Contract defaults.
    """
    def __init__(self, *, temp_root=None, ffmpeg="ffmpeg", timeout_sec=120):
        self.temp_root, self.ffmpeg, self.timeout_sec = temp_root, ffmpeg, timeout_sec

    def _run(self, args, *, content=None, cwd=None):
        result = subprocess.run([self.ffmpeg, "-nostdin", "-v", "error", *args],
            input=content, capture_output=True, cwd=cwd, timeout=self.timeout_sec, check=False)
        if result.returncode:
            raise ValueError("export encoding failed")
        return result.stdout

    def plate(self, content, bbox, limit):
        if not png(content) or len(content) < 24:
            raise ValueError("invalid source frame")
        width, height = struct.unpack(">II", content[16:24])
        x, y, w, h = bbox
        if x + w > width or y + h > height:
            raise ValueError("region exceeds frame")
        operations = [{"crop_xywh": bbox}]
        out_w, out_h = w, h
        while True:
            filters = f"crop={w}:{h}:{x}:{y}:exact=1,scale={out_w}:{out_h}:flags=lanczos"
            output = self._run(["-f", "image2pipe", "-i", "pipe:0", "-vf", filters,
                "-frames:v", "1", "-c:v", "png", "-compression_level", "9", "-f", "image2pipe", "pipe:1"], content=content)
            if not png(output):
                raise ValueError("invalid export output")
            if len(output) <= limit:
                return output, operations
            if out_w == out_h == 1:
                raise RecordingCapabilityError("PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE", "이미지 출력 제한을 충족할 수 없습니다")
            out_w, out_h = max(1, out_w // 2), max(1, out_h // 2)
            operations.append({"resize_wh": [out_w, out_h]})

    def report(self, content, stamp):
        if actual_media_type(content) != "video/mp4":
            raise ValueError("invalid clip content")
        if not stamp.needed:
            return content, [{"copy": True, "post_stamp_applied": False}]
        with TemporaryDirectory(prefix="export-", dir=self.temp_root) as name:
            root = Path(name)
            (root / "input.mp4").write_bytes(content)
            # A text file keeps the value out of the filter grammar and argv.
            (root / "stamp.txt").write_text(stamp.value, encoding="utf-8")
            self._run(["-i", "input.mp4", "-map", "0:v:0", "-an", "-sn", "-dn",
                "-vf", "drawtext=textfile=stamp.txt:fontcolor=white:fontsize=16:box=1:boxcolor=black@0.7:x=4:y=4",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "output.mp4"], cwd=root)
            output = (root / "output.mp4").read_bytes()
        if actual_media_type(output) != "video/mp4":
            raise ValueError("invalid report output")
        return output, [{"encoding": "h264/veryfast/crf23/yuv420p", "post_stamp_applied": True,
                         "value": stamp.value}]


class RecordingExports:
    """Public capability mixin. Worker supplies an execution-local detached repo."""
    def _export_clip(self, ref):
        clip = self.get_incident_clip(ref)
        if self._analysis_closed or self._export_materializer is None or clip.availability != "AVAILABLE":
            raise ValueError("export source unavailable")
        return clip

    def export_plate_image(self, *, incident_clip_ref, frame_ref, plate_bbox_xywh, max_byte_size):
        try:
            request = PlateImageRequest(incident_clip_ref=incident_clip_ref, frame_ref=frame_ref,
                plate_bbox_xywh=plate_bbox_xywh, max_byte_size=max_byte_size)
            clip = self._export_clip(request.incident_clip_ref)
            frame = self._repository.get_frame(request.frame_ref)
            content = self._repository.get_frame_content(request.frame_ref)
            if frame is None or not any(frame.media_stream_ref == s.media_stream_ref
                    and s.source_range.start_sec <= frame.source_offset_sec < s.source_range.end_sec
                    for s in clip.source_provenance.asset_spans):
                raise ValueError("frame not in clip")
            output, operations = self._export_materializer.plate(content, request.plate_bbox_xywh, request.max_byte_size)
        except RecordingCapabilityError as error:
            if error.code == "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE":
                raise RecordingCapabilityError(error.code, "이미지 출력 제한을 충족할 수 없습니다") from None
            raise RecordingCapabilityError("PLATE_IMAGE_EXPORT_FAILED", "번호판 이미지 생성에 실패했습니다") from None
        except (ValueError, TypeError, OSError, subprocess.SubprocessError):
            raise RecordingCapabilityError("PLATE_IMAGE_EXPORT_FAILED", "번호판 이미지 생성에 실패했습니다") from None
        return self._store_export("PLATE_IMAGE", request, clip, output, operations)

    def export_report_video(self, *, incident_clip_ref, post_stamp):
        try:
            request = ReportVideoRequest(incident_clip_ref=incident_clip_ref, post_stamp=post_stamp)
            clip = self._export_clip(request.incident_clip_ref)
            stored = self._repository.get_prepared_content(ContractRef(kind="incident_clip", ref=incident_clip_ref))
            if stored is None or len(stored[0]) != clip.byte_size:
                raise ValueError("clip content unavailable")
            output, operations = self._export_materializer.report(stored[0], request.post_stamp)
        except (RecordingCapabilityError, ValueError, TypeError, OSError, subprocess.SubprocessError):
            raise RecordingCapabilityError("REPORT_VIDEO_EXPORT_FAILED", "영상 생성에 실패했습니다") from None
        return self._store_export("REPORT_VIDEO", request, clip, output, operations)

    def _store_export(self, role, request, clip, content, operations):
        transform = {"strategy": "recording-export/v1", "input": request.model_dump(mode="json"), "operations": operations}
        transform_ref = "transform_" + export_fingerprint(transform).split(":")[1]
        asset = DerivedAsset(contract="DerivedAsset", contract_version="analysis-source-derived/v1",
            derived_asset_ref="da_" + uuid4().hex, asset_kind="DERIVED_ASSET", derived_role=role,
            source_refs=[ContractRef(kind="incident_clip", ref=clip.incident_clip_ref),
                *[ContractRef(kind="source_asset", ref=ref) for ref in dict.fromkeys(
                    s.source_asset_ref for s in clip.source_provenance.asset_spans)]],
            byte_size=len(content), availability="AVAILABLE", duration_sec=clip.duration_sec if role == "REPORT_VIDEO" else None,
            timeline_ref=clip.timeline_ref, timeline_range=clip.timeline_range, transform_ref=transform_ref)
        self._repository.add_export_transform(transform_ref, transform)
        self._repository.add_derived_asset(asset, content=content,
            content_type="video/mp4" if role == "REPORT_VIDEO" else "image/png", case_id=self._case_id)
        return asset.model_copy(deep=True)

    def get_export_transform(self, ref):
        value = self._repository.get_export_transform(ref)
        if value is None:
            raise RecordingCapabilityError("NOT_FOUND", "등록된 변환 이력이 없습니다")
        return copy.deepcopy(value)


def export_snapshot(repository, case_id, request):
    """Detach immutable media bytes before entering the public capability."""
    from .repository import InMemoryRecordingRepository
    from .service import RecordingService
    snapshot = InMemoryRecordingRepository()
    clip_ref = request["incident_clip_ref"]
    with RecordingService(repository) as source:
        clip = source.get_incident_clip(clip_ref)
        if (ContractRef(kind="incident_clip", ref=clip_ref) not in repository.get_case_assets(case_id)
                or not all(source.owns_asset(case_id, ContractRef(kind="source_asset", ref=s.source_asset_ref))
                           for s in clip.source_provenance.asset_spans)):
            raise ValueError("export clip ownership mismatch")
    content = repository.get_prepared_content(ContractRef(kind="incident_clip", ref=clip_ref))
    if content is None:
        snapshot.add_incident_clip(clip)
    else:
        snapshot.add_prepared_media(clip, content[0])
    if "frame_ref" in request:
        owned = repository.get_owned_frame(case_id, request["frame_ref"])
        if owned is None:
            raise ValueError("export frame ownership mismatch")
        frame, content = owned
        snapshot.add_frame(frame, content=content, image_format="png" if content else None)
    return snapshot


def publish_exports(snapshot, repository, case_id):
    for ref in snapshot.get_case_assets(case_id):
        if ref.kind != "derived_asset":
            continue
        asset = snapshot.get_derived_asset(ref.ref)
        content, media_type = snapshot.get_derived_content(ref.ref)
        repository.add_export_transform(asset.transform_ref, snapshot.get_export_transform(asset.transform_ref))
        repository.add_derived_asset(asset, content=content, content_type=media_type, case_id=case_id)
