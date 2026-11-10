"""Audited local jobs; command names and provider labels are not a boundary.

Export/preview handlers perform local Recording work without UsageSink.begin.
Production OCR uses a durable local usage observation, not an external paid call;
its claimed kind, operation, provider, pricing and Run intent must all match.
Clip and unknown/future kinds retain the guarded analysis path.
"""
from types import MappingProxyType

LOCAL_OCR_OPERATIONS = MappingProxyType({"PLATE_READ": "READOUT_PLATE",
                                       "OVERLAY_TIME_READ": "READOUT_OVERLAY_TIME"})
LOCAL_OCR_KINDS = frozenset(LOCAL_OCR_OPERATIONS)
LOCAL_RESULT_KINDS = frozenset({"REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT", "CANDIDATE_VIDEO_PREVIEW"}) | LOCAL_OCR_KINDS


def local_ocr_usage(kind, snapshot):
    """The fixed production Readout producer, checked against its live claim.

    Only Worker-owned snapshots reach this check. The production registry binds
    these kinds to RecordingOcrFactory/PaddleOcrProvider with warmed local models;
    no HTTP payload or environment setting can select a different exemption.
    """
    return (kind in LOCAL_OCR_KINDS and snapshot.get("operation") == LOCAL_OCR_OPERATIONS[kind]
            and snapshot.get("provider_label") == "ocr-local"
            and snapshot.get("pricing_id") == "local-2026-09" and snapshot.get("unit") == "per_second"
            and snapshot.get("planned_run_kind") == "readout_run"
            and isinstance(snapshot.get("planned_run_ref"), str) and bool(snapshot["planned_run_ref"].strip())
            and snapshot.get("direct_no_run") is False)


def local_only(jobs):
    return bool(jobs) and all(job["kind"] in LOCAL_RESULT_KINDS for job in jobs)
