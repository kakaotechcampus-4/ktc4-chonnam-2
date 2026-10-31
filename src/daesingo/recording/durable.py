"""Recording-owned immutable media and observation snapshots (not Contracts)."""
import hashlib
import json

from .media_content import actual_media_type, descriptor
from .models import AnalysisSource, IncidentClip
from .time_sources import ObservedTimeSources, TimeSourceCandidate, TimeSourceCheck


def media_identity(media):
    if isinstance(media, AnalysisSource):
        return "analysis_source", media.analysis_source_ref
    if isinstance(media, IncidentClip):
        return "incident_clip", media.incident_clip_ref
    raise ValueError("unsupported prepared media")


def prepared_content(media, content):
    media_identity(media)
    if (not isinstance(content, bytes) or media.byte_size != len(content)
            or media.availability != "AVAILABLE" or actual_media_type(content) != "video/mp4"):
        raise ValueError("inconsistent prepared media")
    return descriptor(content, "video/mp4")


def stable_media(media, content):
    kind, _ = media_identity(media)
    field = kind + "_ref"
    snapshot = media.model_dump(mode="json", exclude={field})
    fingerprint = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(fingerprint + hashlib.sha256(content).digest()).hexdigest()
    return media.model_copy(update={field: ("as_" if kind == "analysis_source" else "clip_") + digest})


def observation_payload(observed):
    return {"candidates": [c.model_dump(mode="json") for c in observed.candidates],
            "checks": [c.model_dump(mode="json") for c in observed.checks]}


def observation_from_payload(payload):
    return ObservedTimeSources(tuple(TimeSourceCandidate.model_validate_json(json.dumps(c)) for c in payload["candidates"]),
                              tuple(TimeSourceCheck.model_validate_json(json.dumps(c)) for c in payload["checks"]))
