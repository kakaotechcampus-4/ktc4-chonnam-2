"""신고용 export(신고 영상 · 번호판 이미지) 발주 시점 판단과 입력 전달.

export 입력과 크기 상한은 각 모듈이 정한 값을 그대로 옮긴다. case는 언제 발주할지와
실패 notice만 만든다(#351).
"""
import copy

from daesingo.case import jobs
from daesingo.recording.exports import export_fingerprint

EXPORT_KINDS = frozenset({"REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"})
# READY에 필요 없는 export — 자리가 모자라면 먼저 뺀다(#675).
OPTIONAL_EXPORT_KINDS = frozenset({"PLATE_IMAGE_EXPORT"})


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


def gate_auto_exports(case, adapter, view, admit, *, since):
    """빠진 export를 복사본에 발주하고 `admit`이 `job_records[since:]`를 받아들인 case를 돌려준다(#675).

    번호판 이미지는 READY 조건이 아니다(Package에 있을 때만 싣는다). 신고영상과 함께 거절되면 번호판
    이미지를 빼고 한 번 더 묻는다 — 자리가 하나뿐이어도 필수 신고영상은 발주된다. 신고영상까지
    거절되면 선택 항목에 자리를 쓰지 않는다. 받아들여진 것이 없으면 원래 `case`를 그대로 돌려준다.

    거절된 admission은 호출자 savepoint로 되돌아가 흔적이 없으므로 같은 admission 키로 다시 물어도 된다.
    `since`는 admission이 함께 볼 범위다 — 반영 경로는 이번 export만, command는 이번 command의 job 전체."""
    for skip in (frozenset(), OPTIONAL_EXPORT_KINDS):
        candidate = copy.deepcopy(case)
        before = len(candidate.job_records)
        issue_missing_exports(candidate, adapter, view, skip=skip)
        fresh = candidate.job_records[before:]
        if not fresh:
            break
        if admit(copy.deepcopy(candidate.job_records[since:])):
            return candidate
        if not any(r["kind"] in OPTIONAL_EXPORT_KINDS for r in fresh):
            break
    return case


def issue_missing_exports(case, adapter, view, *, skip=frozenset()):
    """`skip`의 kind는 이번에 발주하지 않는다(`gate_auto_exports`가 선택 항목을 뺄 때)."""
    from daesingo.case.service import report_video_missing
    if adapter is None or not hasattr(adapter, "get_export_requests"):
        return
    # Same #351 predicate as the visible missing-video notice
    # (= `case.report_video_not_generated` notice가 쓰는 `service.report_video_missing()` 조건). Plate is optional
    # and shares the same gate, even when report video already exists.
    # #597: no situation-response gate. An assembled EvidenceRecord (record_id) is
    # the gate — Fine OBSERVED assembles before any response; UNCERTAIN only after
    # USER_UNSURE (evidence disposition), so it still waits for the response.
    selected = [c for c in view.get("candidates", []) if c["selected"]]
    if (not (view.get("evidence") or {}).get("record_id") or len(selected) != 1
            or not any(c["code"] == "package.asset.report_video.exists"
                       for c in (view.get("requirements_package") or {}).get("checks", []))):
        return
    for kind, request in adapter.get_export_requests().items():
        if kind not in EXPORT_KINDS:
            raise ValueError("unsupported export request")
        if kind in skip:
            continue
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
