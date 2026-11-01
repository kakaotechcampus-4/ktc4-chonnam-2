"""T1-before issuance with Case-owned position functions; no T2 capability.

This seam is deliberately not enabled by production composition until the Case
helpers and result consumers are available. Never substitute test selectors.
"""
import math
from typing import Any

from daesingo.recording import ContractRef, RecordingCapabilityError


# Only resolve_frame refusals are optional. UNKNOWN_REF signals broken binding.
# Metadata/resolve_span/Case/checkpoint/context/persistence errors stay outside.
FRAME_REFUSALS = frozenset({"FRAME_NOT_FOUND", "STREAM_UNAVAILABLE", "OUT_OF_RANGE", "TEMPORARY_FAILURE"})


class IncidentFrameIssuer:
    def __init__(self, *, preview_position, candidate_position):
        self.preview_position, self.candidate_position = preview_position, candidate_position

    def __call__(self, context, data, clip, recording):
        context.checkpoint()
        result: dict[str, Any] = {"preview_frame_ref": None, "candidate_frame_refs": {}}
        if not data.frames_current:
            return result
        candidate = data.candidate
        if candidate is None:
            raise ValueError("fixed preview candidate required")
        selected = data.video_stream_refs
        if not selected or len(set(selected)) != len(selected):
            raise ValueError("explicit VIDEO selection required")
        # Validate the entire Case selection, including streams not used by the
        # selected clip. Other candidates must resolve their own source spans.
        for ref in selected:
            stream = recording.get_media_stream(ref)
            context.checkpoint()
            if stream.media_type != "VIDEO" or not recording.owns_asset(data.case_id,
                    ContractRef(kind="source_asset", ref=stream.source_asset_ref)):
                raise ValueError("frame selection is not owned VIDEO")
            context.checkpoint()
        cache: dict[tuple[str, float], str | None] = {}

        def issue(position):
            context.checkpoint()
            if position is None:
                return None
            ref, offset = position
            if (ref not in selected or isinstance(offset, bool) or not isinstance(offset, (float, int))
                    or not math.isfinite(offset) or offset < 0):
                raise ValueError("invalid Case STREAM_POSITION")
            key = (ref, offset)
            if key not in cache:
                try:
                    frame = recording.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": ref,
                                                     "source_offset_sec": offset})
                except RecordingCapabilityError as error:
                    if error.code not in FRAME_REFUSALS:
                        raise
                    cache[key] = None
                else:
                    cache[key] = frame.frame_ref
                context.checkpoint()
            return cache[key]

        span = candidate.span.model_dump(mode="json")
        result["preview_frame_ref"] = issue(self.preview_position(clip.model_dump(mode="json"), span,
                                                                  candidate.span.representative_ms))
        refs: dict[str, str | None] = {}
        for item in data.thumbnail_candidates:
            context.checkpoint()
            span = item.span.model_dump(mode="json")
            if (span["timeline_id"] != data.timeline_ref["timeline_id"]
                    or span["timeline_revision"] != data.timeline_ref["revision"]):
                raise ValueError("thumbnail timeline binding mismatch")
            if item.span.representative_ms is None:
                refs[item.candidate_id] = None
                continue
            resolution = recording.resolve_span(data.timeline_ref,
                {"start_sec": item.span.start_ms / 1000, "end_sec": item.span.end_ms / 1000},
                **({"media_stream_ref": selected[0]} if len(selected) == 1 else {"media_stream_refs": list(selected)}))
            context.checkpoint()
            refs[item.candidate_id] = issue(self.candidate_position(resolution.model_dump(mode="json"), span,
                                                                   item.span.representative_ms))
        result["candidate_frame_refs"] = refs
        context.checkpoint()
        return result
