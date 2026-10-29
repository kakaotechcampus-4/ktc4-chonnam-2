"""#351 order timing and relay of module-owned export inputs and limits."""
import copy

from daesingo.case import jobs
from daesingo.recording.exports import export_fingerprint

EXPORT_KINDS = frozenset({"REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"})


def build_export_requests(clip_ref, plate_readout, time_resolution, max_byte_size):
    stamp = time_resolution["post_stamp"]
    report = {"incident_clip_ref": clip_ref, "post_stamp": {"needed": stamp["needed"],
        "value": time_resolution["resolved"]["value"] if stamp["needed"] else None}}
    result = {"REPORT_VIDEO_EXPORT": report}
    best = (plate_readout or {}).get("best_frame") or {}
    if best.get("frame_ref") is not None and best.get("plate_bbox_xywh") is not None:
        result["PLATE_IMAGE_EXPORT"] = {"incident_clip_ref": clip_ref, "frame_ref": best["frame_ref"],
            "plate_bbox_xywh": copy.deepcopy(best["plate_bbox_xywh"]), "max_byte_size": max_byte_size}
    return result


def issue_missing_exports(case, adapter, view):
    from daesingo.case.service import report_video_missing
    if adapter is None or not hasattr(adapter, "get_export_requests"):
        return
    # Same #351 predicate as the visible missing-video notice. Plate is optional
    # and shares the response gate, even when report video already exists.
    selected = [c for c in view.get("candidates", []) if c["selected"]]
    if (not (view.get("evidence") or {}).get("record_id") or len(selected) != 1
            or selected[0]["situation_confirmation"] not in {"CONFIRMED", "CORRECTED", "USER_UNSURE"}
            or not any(c["code"] == "package.asset.report_video.exists"
                       for c in (view.get("requirements_package") or {}).get("checks", []))):
        return
    for kind, request in adapter.get_export_requests().items():
        if kind not in EXPORT_KINDS:
            raise ValueError("unsupported export request")
        if kind == "REPORT_VIDEO_EXPORT" and not report_video_missing(view):
            continue
        fingerprint = export_fingerprint({"kind": kind, "input": request})
        if any(r["kind"] == kind and r["input_fingerprint"] == fingerprint for r in case.job_records):
            continue
        jobs.issue_job(case, kind, input_fingerprint=fingerprint, export_input=request)


def export_notices(case, executions, view, requests):
    """Only current input failures; no raw failure detail is exposed."""
    for kind, code, action in (("REPORT_VIDEO_EXPORT", "recording.report_video_export_failed", "GENERATE_REPORT_VIDEO"),
                              ("PLATE_IMAGE_EXPORT", "recording.plate_image_export_failed", "GENERATE_PLATE_IMAGE")):
        records = [r for r in case.job_records if r["kind"] == kind
                   and r["job_id"] in case.export_inputs and case.export_inputs[r["job_id"]] == requests.get(kind)]
        if not records:
            continue
        record = records[-1]
        terminal = max((e for e in executions if e["job_id"] == record["job_id"]),
                       key=lambda e: e["attempt"], default=None)
        if terminal is None or terminal["status"] != "FAILED":
            continue
        failure = terminal.get("failure_kind")
        if failure not in {"REPORT_VIDEO_EXPORT_FAILED", "PLATE_IMAGE_EXPORT_FAILED", "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE"}:
            continue
        running = any(j["kind"] == kind for j in view["running_jobs"])
        actions = [] if running or failure == "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE" else [action]
        view["notices"].append({"code": code, "severity": "ERROR", "blocking": kind == "REPORT_VIDEO_EXPORT",
            "message_key": "notice." + code.split(".", 1)[1], "actions": actions})
    return view
