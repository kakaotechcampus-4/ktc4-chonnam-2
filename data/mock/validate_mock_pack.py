#!/usr/bin/env python3
"""Lightweight Mock Pack validator.

Not a full per-Contract schema validator (the codebase has no Pydantic/contract
models yet to reuse — see docs/mock/04_mock_validation_report.md). This script
only checks mechanically-verifiable things:

  1. every JSON file under data/mock parses
  2. a small set of required top-level keys exist per known fixture kind
  3. a small set of closed enums only contain registered values
  4. every {"kind": ..., "ref": ...}-shaped ContractRef resolves to an object
     that was actually defined somewhere in the same scenario's fixtures
     (referential connectivity across modules, requirement #13)
  5. every scenario manifest's `artifacts` paths exist on disk
  6. a handful of cheap invariants: start <= end on ranges, ReadoutRun/JobExecution
     outcome<->failure consistency, PlateReadout best_frame offset falling inside
     the candidate's own span (time/interval consistency, requirement #14)

Exit code is non-zero if any check fails. Findings are grouped and printed;
this script does NOT silently "fix" anything it finds wrong in a fixture —
per the task's rule, problems are reported (here, and in
docs/mock/04_mock_validation_report.md), never auto-corrected.
"""
import json
import sys
from pathlib import Path

# Windows 콘솔(cp949)에서 em dash 등 non-ASCII 출력 문자 때문에 UnicodeEncodeError로 죽는
# 문제 수정(2026-09-09, 김대원·신유민 #16·#17 이슈 지적). 검증 자체는 PASS/FAIL과 무관하게
# 항상 UTF-8로 출력한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent  # data/mock
MODULES = ["recording", "search", "readout", "evidence", "case", "common"]

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        err(f"[PARSE] {path.relative_to(ROOT.parent.parent)}: {e}")
        return None


def find_all_fixture_files():
    files = []
    for m in MODULES:
        d = ROOT / m
        if d.is_dir():
            files.extend(sorted(d.glob("scenario_*.json")))
    files.extend(sorted((ROOT / "scenarios").glob("scenario_*.json")))
    files.extend(sorted((ROOT / "expected").glob("*.json")))
    if (ROOT / "manifest.json").exists():
        files.append(ROOT / "manifest.json")
    return files


# ---- 1. parse check + collect per-scenario module documents -----------------

scenario_docs = {}  # scenario_id -> {module: parsed_doc}
all_docs = {}  # path -> parsed_doc

for path in find_all_fixture_files():
    doc = load_json(path)
    all_docs[path] = doc
    if doc is None:
        continue
    if path.parent.name in MODULES:
        sid = doc.get("scenario_id")
        module = doc.get("module")
        if sid is None or module is None:
            err(f"[REQUIRED_FIELD] {path}: missing top-level 'scenario_id' or 'module' wrapper key")
            continue
        if module != path.parent.name:
            err(f"[REQUIRED_FIELD] {path}: module='{module}' does not match directory '{path.parent.name}'")
        scenario_docs.setdefault(sid, {})[module] = doc

# ---- 2. required top-level keys per fixture kind (spot checks) --------------

REQUIRED_KEYS = {
    "recording": ["source_assets", "media_streams", "frame_refs", "recording_timelines"],
    "search": ["analysis_scopes", "analysis_run_candidate_events"],
    "readout": ["readout_runs"],
    "evidence": ["time_resolutions", "evidence_records"],
    "case": ["job_records", "case_views"],
    "common": ["job_executions", "usage_records"],
}

for sid, mods in scenario_docs.items():
    for module, keys in REQUIRED_KEYS.items():
        if module not in mods:
            continue  # module intentionally absent from this scenario (documented in scenario manifest)
        doc = mods[module]
        for k in keys:
            if k not in doc:
                err(f"[REQUIRED_FIELD] {sid}/{module}: missing required key '{k}'")

# ---- 3. closed enum checks ----------------------------------------------
#
# Every set below is a CLOSED value space fixed by a Final Contract. The contract
# that owns each one is named in the comment; do not add values here without a
# contract change.

# contract-analysis-scope.md §7 · contract-visual-evidence.md §4-2
VISUAL_EVENT_TYPES = {
    "SIGNAL", "CENTER_LINE_CROSSING", "SOLID_LINE_LANE_CHANGE", "MOTORCYCLE_HELMET_NON_USE",
}

CLOSED_ENUMS = {
    # contract-readout-run.md §6
    ("readout_runs", "outcome"): {"SUCCEEDED", "PARTIAL", "FAILED"},
    ("readout_runs", "operation"): {"PLATE_READ", "OVERLAY_TIME_READ"},
    # contract-job-execution.md §6
    # job-execution/v1.1 (이슈 #33 A-2)에서 CANCELLED 추가 — 이 세트가 그때 갱신되지 않고 남아 있었다
    ("job_executions", "status"): {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "STALE", "CANCELLED"},
    # contract-requirement-report-package.md §3
    ("requirement_reports", "overall"): {"PASS", "WARN", "BLOCK", "UNKNOWN"},
    ("requirement_reports", "scope"): {"EVIDENCE", "FINAL_PACKAGE"},
    # contract-time-resolution.md §2
    ("time_resolutions", "status"): {"OK", "NEEDS_REVIEW", "UNKNOWN"},
    # contract-source-asset-media-stream.md §3.5 · §2.1
    ("source_assets", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("source_assets", "asset_kind"): {"SOURCE_ASSET"},
    ("media_streams", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("media_streams", "media_type"): {"VIDEO", "AUDIO"},
    ("media_streams", "role"): {"FRONT", "REAR", "UNKNOWN"},
    ("asset_facts", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("asset_facts", "asset_kind"): {"SOURCE_ASSET", "ANALYSIS_SOURCE", "INCIDENT_CLIP", "DERIVED_ASSET"},
    ("asset_facts", "derived_role"): {"REPORT_VIDEO", "PLATE_IMAGE"},
    # contract-recording-timeline-asset-span.md §2·§9·§15
    ("recording_timelines", "timeline_status"): {"USABLE", "USABLE_RELATIVE_ONLY", "PARTIAL", "UNUSABLE"},
    ("time_source_candidates", "source_kind"): {"FILENAME", "FILE_METADATA", "VENDOR_METADATA"},
    ("span_resolutions", "status"): {"COMPLETE", "PARTIAL", "FAILED"},
    # contract-analysis-source-derived.md §7.3 · §8
    ("derived_assets", "derived_role"): {"REPORT_VIDEO", "PLATE_IMAGE"},
    ("derived_assets", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("incident_clips", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("analysis_sources", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("remote_copies", "availability"): {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"},
    ("deletion_reports", "status"): {"COMPLETE", "PARTIAL", "FAILED"},
    # contract-visual-evidence.md §3·§4-1
    ("visual_evidences", "verification"): {"OBSERVED", "NOT_OBSERVED", "UNCERTAIN"},
    ("visual_evidences", "visual_event_type"): VISUAL_EVENT_TYPES,
}

OBSERVATION_STATUSES = {"OK", "NEEDS_REVIEW", "UNKNOWN", "ERROR", "NOT_APPLICABLE"}
INFO_STATES = {
    "INFO_AI_ESTIMATED", "INFO_SOURCE_VERIFIED", "INFO_USER_CONFIRMED",
    "INFO_NEEDS_REVIEW", "INFO_UNKNOWN",
}
# contract-correction-record.md §4 (v1.1, SITUATION_CHANGE added)
CORRECTION_RECORD_KINDS = {
    "TIME_HINT_EDIT", "OTHER_CANDIDATE", "PLATE_MANUAL_EDIT", "PLATE_REREAD",
    "SPAN_ADJUST", "REPORT_TYPE_CHANGE", "EVENT_TIME_MANUAL", "TIMELINE_REBASE",
    "SITUATION_CHANGE",
}
# contract-job-record-case-view.md B절 §7 (v1.3, 이슈 #39 B-2 이후 값 공간)
SITUATION_CONFIRMATION_VALUES = {"NOT_ASKED", "CONFIRMED", "CORRECTED", "USER_UNSURE"}
# contract-evidence-record-needs.md §4.6-1 (v1.3)
SITUATION_RESPONSE_VALUES = {"CONFIRMED", "CORRECTED", "USER_UNSURE"}
# contract-usage-record.md §5 (v1.2)
RUN_REF_REASON_VALUES = {"DIRECT_NO_RUN", "RUN_NOT_PRODUCED"}
# CaseView B절 §5-7 — the six *_display fields review_needed/reason_code aggregate over
SIX_DISPLAY_FIELDS = (
    "case_type_display", "report_type_display", "violation_display",
    "plate_display", "event_time_display", "location_display",
)


def check_enum(where, value, allowed, *, nullable=True):
    if value is None and nullable:
        return
    if value not in allowed:
        err(f"[ENUM] {where} = {value!r} not in {sorted(allowed)}")


for sid, mods in scenario_docs.items():
    for module, doc in mods.items():
        for (array_key, field), allowed in CLOSED_ENUMS.items():
            for i, item in enumerate(doc.get(array_key, [])):
                check_enum(f"{sid}/{module}.{array_key}[{i}].{field}", item.get(field), allowed)

    # --- search: AnalysisScope / AnalysisRun / CandidateEvent / VisualEvidence nested ---
    search_doc = mods.get("search", {})
    for i, scope in enumerate(search_doc.get("analysis_scopes", [])):
        for t in scope.get("target_event_types", []):
            check_enum(f"{sid}/search.analysis_scopes[{i}].target_event_types", t, VISUAL_EVENT_TYPES, nullable=False)
        for j, tr in enumerate(scope.get("time_ranges", [])):
            check_enum(f"{sid}/search.analysis_scopes[{i}].time_ranges[{j}].kind",
                       tr.get("kind"), {"ABSOLUTE", "TIMELINE_RELATIVE"})
    for i, block in enumerate(search_doc.get("analysis_run_candidate_events", [])):
        run = block.get("analysis_run", {})
        base = f"{sid}/search.analysis_run_candidate_events[{i}].analysis_run"
        check_enum(f"{base}.operation", run.get("operation"), {"CANDIDATE_SEARCH", "VISUAL_VERIFY"}, nullable=False)
        check_enum(f"{base}.outcome", run.get("outcome"), {"SUCCEEDED", "PARTIAL", "FAILED"}, nullable=False)
        for j, cand in enumerate(block.get("candidates", [])):
            check_enum(f"{base}/candidates[{j}].event_type_hint", cand.get("event_type_hint"), VISUAL_EVENT_TYPES)
    for i, ve in enumerate(search_doc.get("visual_evidences", [])):
        base = f"{sid}/search.visual_evidences[{i}]"
        target = ve.get("target") or {}
        check_enum(f"{base}.target.association_status", target.get("association_status"),
                   {"MATCHED", "AMBIGUOUS", "NOT_FOUND"})
        for j, prim in enumerate(ve.get("primitives", [])):
            check_enum(f"{base}.primitives[{j}].state", prim.get("state"),
                       {"PRESENT", "ABSENT", "UNCERTAIN"}, nullable=False)

    # --- readout: Observation envelope + target association ---
    readout_doc = mods.get("readout", {})
    for key in ("plate_readouts", "overlay_time_readouts"):
        for i, r in enumerate(readout_doc.get(key, [])):
            base = f"{sid}/readout.{key}[{i}]"
            obs = r.get("observation") or {}
            check_enum(f"{base}.observation.status", obs.get("status"), OBSERVATION_STATUSES, nullable=False)
            ta = r.get("target_association")
            if ta is not None:
                check_enum(f"{base}.target_association.status", ta.get("status"),
                           {"ASSOCIATED", "LOW_CONFIDENCE", "AMBIGUOUS", "FAILED", "NOT_PROVIDED"}, nullable=False)

    # --- evidence: RequirementCheck / EvidenceNeeds / DeletionReport items ---
    evidence_doc = mods.get("evidence", {})
    for i, rep in enumerate(evidence_doc.get("requirement_reports", [])):
        for j, chk in enumerate(rep.get("checks", [])):
            base = f"{sid}/evidence.requirement_reports[{i}].checks[{j}]"
            check_enum(f"{base}.category", chk.get("category"),
                       {"EVIDENCE", "TIME", "VEHICLE", "LOCATION", "ASSET", "DEADLINE", "REPORT_CONTENT"},
                       nullable=False)
            check_enum(f"{base}.outcome", chk.get("outcome"), {"PASS", "WARN", "BLOCK", "UNKNOWN"}, nullable=False)
    for i, needs in enumerate(evidence_doc.get("evidence_needs", [])):
        for j, item in enumerate(needs.get("items", [])):
            base = f"{sid}/evidence.evidence_needs[{i}].items[{j}]"
            check_enum(f"{base}.kind", item.get("kind"), {"OVERLAY_TIME_OCR", "PLATE_REREAD"}, nullable=False)
            check_enum(f"{base}.would_fill", item.get("would_fill"), {"OCCURRED_AT", "VEHICLE_NUMBER"}, nullable=False)
    for i, rec in enumerate(evidence_doc.get("evidence_records", [])):
        ev_type = ((rec.get("event") or {}).get("visual_event_type") or {}).get("value")
        check_enum(f"{sid}/evidence.evidence_records[{i}].event.visual_event_type.value", ev_type, VISUAL_EVENT_TYPES)
        occ = rec.get("occurred_at")
        if occ is not None:
            check_enum(f"{sid}/evidence.evidence_records[{i}].occurred_at.resolution_status",
                       occ.get("resolution_status"), {"OK", "NEEDS_REVIEW"}, nullable=False)
        sit = rec.get("situation_response")
        if sit is not None:
            check_enum(f"{sid}/evidence.evidence_records[{i}].situation_response.value",
                       sit.get("value"), SITUATION_RESPONSE_VALUES, nullable=False)
    recording_doc = mods.get("recording", {})
    for i, dr in enumerate(recording_doc.get("deletion_reports", [])):
        for j, item in enumerate(dr.get("items", [])):
            check_enum(f"{sid}/recording.deletion_reports[{i}].items[{j}].result", item.get("result"),
                       {"DELETED", "NOT_FOUND", "PENDING_EXPIRY", "FAILED"}, nullable=False)

    # --- case: CaseView enums ---
    case_doc = mods.get("case", {})
    for i, cv in enumerate(case_doc.get("case_views", [])):
        base = f"{sid}/case.case_views[{i}]"
        check_enum(f"{base}.stage", cv.get("stage"),
                   {"INTAKE", "SEARCHING", "CANDIDATE_REVIEW", "EVIDENCE_REVIEW", "READY"}, nullable=False)
        for j, step in enumerate(cv.get("progress", [])):
            # case-view/v1.3에서 PARTIAL 추가(CANCELLED→PARTIAL 흡수 포함) — 이 세트도 그때 누락됐었다
            check_enum(f"{base}.progress[{j}].state", step.get("state"),
                       {"PENDING", "RUNNING", "DONE", "FAILED", "PARTIAL"}, nullable=False)
        for j, nt in enumerate(cv.get("notices", [])):
            check_enum(f"{base}.notices[{j}].severity", nt.get("severity"), {"INFO", "WARN", "ERROR"}, nullable=False)
        for j, rj in enumerate(cv.get("running_jobs", [])):
            check_enum(f"{base}.running_jobs[{j}].status", rj.get("status"), {"PENDING", "RUNNING"}, nullable=False)
        for j, cand in enumerate(cv.get("candidates", [])):
            # 이슈 #39 Required-5: contract-job-record-case-view.md B§7 ① — 값 공간이
            # NOT_ASKED/CONFIRMED/REJECTED/UNKNOWN에서 NOT_ASKED/CONFIRMED/CORRECTED/USER_UNSURE로
            # 정정됐다(v1.3). 구 값이 남아있으면 이 검사가 잡는다.
            check_enum(f"{base}.candidates[{j}].situation_confirmation", cand.get("situation_confirmation"),
                       SITUATION_CONFIRMATION_VALUES, nullable=False)
        ev = cv.get("evidence")
        if ev:
            for disp in SIX_DISPLAY_FIELDS:
                d = ev.get(disp)
                if d is not None:
                    check_enum(f"{base}.evidence.{disp}.info_state", d.get("info_state"), INFO_STATES, nullable=False)
        for req_key in ("requirements_evidence", "requirements_package"):
            req = cv.get(req_key)
            if req is not None:
                check_enum(f"{base}.{req_key}.readiness", req.get("readiness"),
                           {"PASS", "WARN", "BLOCK", "UNKNOWN"}, nullable=False)
    for i, cr in enumerate(case_doc.get("correction_records", [])):
        check_enum(f"{sid}/case.correction_records[{i}].kind", cr.get("kind"),
                   CORRECTION_RECORD_KINDS, nullable=False)

    # --- common: UsageRecord.run_ref.kind is a field-level closed set ---
    for i, u in enumerate(mods.get("common", {}).get("usage_records", [])):
        run_ref = u.get("run_ref")
        if run_ref is not None:
            check_enum(f"{sid}/common.usage_records[{i}].run_ref.kind", run_ref.get("kind"),
                       {"analysis_run", "readout_run"}, nullable=False)
        if u.get("run_ref_reason") is not None:
            check_enum(f"{sid}/common.usage_records[{i}].run_ref_reason", u.get("run_ref_reason"),
                       RUN_REF_REASON_VALUES, nullable=False)

# ---- 4. build a registry of every opaque ID defined in a scenario, then check refs resolve --

ID_FIELD_CANDIDATES = [
    "source_asset_ref", "media_stream_ref", "frame_ref", "timeline_id", "candidate_id",
    "run_id", "readout_id", "usage_id", "scope_id", "incident_clip_ref", "derived_asset_ref",
    "remote_copy_ref", "analysis_source_ref", "job_id", "execution_id", "case_id",
    "eval_fixture_id", "visual_evidence_id", "correction_id",
]

REF_OBJECT_ID_FIELDS = {
    # array_key -> field holding this object's own opaque id (when it's a nested ContractRef, not a plain string)
    "evidence_records": ("record_ref", "ref"),
    "time_resolutions": ("resolution_ref", "ref"),
    "evidence_needs": None,  # keyed by basis_record_ref, no own id field
    "requirement_reports": ("requirement_report_ref", "ref"),
    "report_packages": ("package_ref", "ref"),
}


def collect_defined_ids(scenario_docs_for_sid):
    defined = set()
    for module, doc in scenario_docs_for_sid.items():
        for key, val in doc.items():
            if key in ("scenario_id", "module"):
                continue
            if not isinstance(val, list):
                continue
            for item in val:
                if not isinstance(item, dict):
                    continue
                for f in ID_FIELD_CANDIDATES:
                    if f in item and isinstance(item[f], str):
                        defined.add(item[f])
                for f in ("run_ref", "record_ref", "resolution_ref", "requirement_report_ref", "package_ref"):
                    if f in item and isinstance(item[f], dict) and "ref" in item[f]:
                        defined.add(item[f]["ref"])
                # case_ref / job_id inside job_records, case_views etc already covered by plain fields
                if key == "case_views":
                    if "case_id" in item:
                        defined.add(item["case_id"])
                    # case_views[].candidates[].candidate_id is case's own denormalized copy — it
                    # is a legitimate defining occurrence in scenarios where no PlateReadout/search
                    # candidate block exists to define it first (e.g. an infra-failure scenario
                    # where plate_readouts=[] because the run never completed). Previously this
                    # nested shape silently relied on readout's plate_readouts[].candidate_id
                    # (a direct, shallow field) to define the ID in every existing scenario.
                    for cand in item.get("candidates", []) or []:
                        if isinstance(cand, dict) and isinstance(cand.get("candidate_id"), str):
                            defined.add(cand["candidate_id"])
                # analysis_run_candidate_events[].candidates[].candidate_id — same nested shape
                # in search's fixture; register it too so search alone can define a candidate_id
                # without depending on readout also happening to define it.
                if key == "analysis_run_candidate_events":
                    for cand in item.get("candidates", []) or []:
                        if isinstance(cand, dict) and isinstance(cand.get("candidate_id"), str):
                            defined.add(cand["candidate_id"])
        # eval fixture own id
        if "eval_fixture_id" in doc:
            defined.add(doc["eval_fixture_id"])
    return defined


def walk_refs(node, path, out):
    """Collect every {'kind':..., 'ref': <str>} occurrence."""
    if isinstance(node, dict):
        if set(node.keys()) >= {"kind", "ref"} and isinstance(node.get("ref"), str) and isinstance(node.get("kind"), str):
            out.append((path, node["kind"], node["ref"]))
        for k, v in node.items():
            walk_refs(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_refs(v, f"{path}[{i}]", out)


# kinds that intentionally reference something outside this scenario's own fixture set
# (opaque, deliberately not materialized as a mock artifact — see scenario manifest note).
# - external_source: raw upload/ingest source metadata; no Final Data Contract in the
#   14-contract set owns ExternalSource's own field schema, so it is referenced by
#   SourceAsset but never materialized as its own mock artifact here.
# 2026-09-10: correction_record removed from this set — contract-correction-record.md is now
# Final (v1.1, evidence Consumer Review 6건 반영), so CorrectionRecord refs must resolve to an
# actual fixture object. CorrectionRecord's contract owner AND runtime producer are both case
# (이슈 #39 Required-2), so the fixture object lives in case's own file — see
# case/scenario_correction_rerun_001.json correction_records[]; evidence only holds a
# ContractRef pointer to it (evidence_records[].provenance.correction_refs).
EXEMPT_KINDS = {"external_source"}

def collect_defined_by_kind(mods):
    """kind (as used in ContractRef) -> set of ids that legitimately carry that kind."""
    by_kind = {}

    def add(kind, value):
        if isinstance(value, str):
            by_kind.setdefault(kind, set()).add(value)

    for module, doc in mods.items():
        for a in doc.get("source_assets", []):
            add("source_asset", a.get("source_asset_ref"))
        for a in doc.get("media_streams", []):
            add("media_stream", a.get("media_stream_ref"))
        for a in doc.get("frame_refs", []):
            add("frame", a.get("frame_ref"))
        for a in doc.get("analysis_sources", []):
            add("analysis_source", a.get("analysis_source_ref"))
        for a in doc.get("incident_clips", []):
            add("incident_clip", a.get("incident_clip_ref"))
        for a in doc.get("derived_assets", []):
            add("derived_asset", a.get("derived_asset_ref"))
        for a in doc.get("remote_copies", []):
            add("remote_copy", a.get("remote_copy_ref"))
        for a in doc.get("time_source_candidates", []):
            add("time_source_candidate", a.get("candidate_id"))
        for block in doc.get("analysis_run_candidate_events", []):
            add("analysis_run", (block.get("analysis_run") or {}).get("run_id"))
            for cand in block.get("candidates", []):
                add("candidate_event", cand.get("candidate_id"))
        for a in doc.get("visual_evidences", []):
            add("visual_evidence", a.get("visual_evidence_id"))
        for a in doc.get("readout_runs", []):
            add("readout_run", a.get("run_id"))
        for a in doc.get("plate_readouts", []):
            add("plate_readout", a.get("readout_id"))
        for a in doc.get("overlay_time_readouts", []):
            add("overlay_time_readout", a.get("readout_id"))
        for a in doc.get("time_resolutions", []):
            add("time_resolution", (a.get("resolution_ref") or {}).get("ref"))
        for a in doc.get("evidence_records", []):
            add("evidence_record", (a.get("record_ref") or {}).get("ref"))
        for a in doc.get("requirement_reports", []):
            add("requirement_report", (a.get("requirement_report_ref") or {}).get("ref"))
        for a in doc.get("report_packages", []):
            add("report_package", (a.get("package_ref") or {}).get("ref"))
        for a in doc.get("correction_records", []):
            add("correction_record", a.get("correction_id"))
        for a in doc.get("case_views", []):
            add("case", a.get("case_id"))
        for a in doc.get("job_records", []):
            add("case", a.get("case_id"))
    return by_kind


defined_ids_by_scenario = {}
defined_by_kind_by_scenario = {}

for sid, mods in scenario_docs.items():
    defined = collect_defined_ids(mods)
    defined_ids_by_scenario[sid] = defined
    by_kind = collect_defined_by_kind(mods)
    defined_by_kind_by_scenario[sid] = by_kind
    refs = []
    for module, doc in mods.items():
        walk_refs(doc, f"{sid}/{module}", refs)
    for path, kind, ref in refs:
        if kind in EXEMPT_KINDS:
            continue
        if ref not in defined:
            err(f"[DANGLING_REF] {path}: {{kind:'{kind}', ref:'{ref}'}} does not resolve to any ID defined within scenario '{sid}'")
        elif kind in by_kind and ref not in by_kind[kind]:
            # §11-2: the ref resolves, but to an object of a different contract type
            owner = next((k for k, ids in by_kind.items() if ref in ids), "unknown")
            err(f"[REF_KIND] {path}: kind='{kind}' but '{ref}' is defined as a '{owner}' object")

# ---- 5. scenario manifest artifact paths exist -------------------------------

for manifest_path in sorted((ROOT / "scenarios").glob("scenario_*.json")):
    doc = all_docs.get(manifest_path)
    if not doc:
        continue
    for module, rel_path in doc.get("artifacts", {}).items():
        p = ROOT.parent.parent / rel_path
        if not p.exists():
            err(f"[MANIFEST_PATH] {manifest_path}: artifacts.{module} = '{rel_path}' does not exist on disk")

# ---- 6. cheap mechanical invariants -----------------------------------------

for sid, mods in scenario_docs.items():
    readout_doc = mods.get("readout")
    if readout_doc:
        for run in readout_doc.get("readout_runs", []):
            outcome = run.get("outcome")
            failure = run.get("failure")
            if outcome == "SUCCEEDED" and failure is not None:
                err(f"[INVARIANT] {sid}/readout.readout_runs[{run.get('run_id')}]: outcome=SUCCEEDED but failure is not null")
            if outcome in ("PARTIAL", "FAILED") and failure is None:
                err(f"[INVARIANT] {sid}/readout.readout_runs[{run.get('run_id')}]: outcome={outcome} but failure is null")

    common_doc = mods.get("common")
    if common_doc:
        for ex in common_doc.get("job_executions", []):
            status = ex.get("status")
            if status in ("QUEUED", "RUNNING") and ex.get("ended_at") is not None:
                err(f"[INVARIANT] {sid}/common.job_executions[{ex.get('execution_id')}]: status={status} but ended_at is not null")
            if status == "SUCCEEDED" and not ex.get("produced"):
                warn(f"[INVARIANT?] {sid}/common.job_executions[{ex.get('execution_id')}]: status=SUCCEEDED but produced=[] (verify intentional)")

    recording_doc = mods.get("recording")
    span_doc = mods.get("search")
    if recording_doc and span_doc:
        frame_offsets = {}
        for fr in recording_doc.get("frame_refs", []):
            frame_offsets[fr["frame_ref"]] = fr["source_offset_sec"]
        for run_block in span_doc.get("analysis_run_candidate_events", []):
            for cand in run_block.get("candidates", []):
                start_s = cand["span"]["start_ms"] / 1000.0
                end_s = cand["span"]["end_ms"] / 1000.0
                if start_s > end_s:
                    err(f"[INVARIANT] {sid}/search.candidates[{cand['candidate_id']}]: span.start_ms > end_ms")
                thumb = cand.get("thumbnail_ref")
                if thumb and thumb in frame_offsets:
                    off = frame_offsets[thumb]
                    if not (start_s <= off <= end_s):
                        err(
                            f"[INTERVAL_CONSISTENCY] {sid}/search.candidates[{cand['candidate_id']}]: "
                            f"thumbnail_ref '{thumb}' offset {off}s falls outside candidate span [{start_s},{end_s}]s"
                        )

    for run_block in (span_doc or {}).get("analysis_scopes", []):
        for tr in run_block.get("time_ranges", []):
            if tr.get("start") and tr.get("end") and tr["start"] >= tr["end"]:
                err(f"[INVARIANT] {sid}/search.analysis_scopes: time_range start >= end ({tr['start']} / {tr['end']})")

# ---- 7. per-contract required keys ------------------------------------------
#
# "Y(키 항상 존재)" fields count as required even when their value may be null.

REQUIRED_OBJECT_KEYS = {
    # module, array key -> required keys
    ("search", "visual_evidences"): [
        "schema_version", "visual_evidence_id", "run_id", "input_ref", "verification",
        "visual_event_type", "target", "primitives", "temporal_facts", "uncertainties", "legal_status",
    ],
    ("readout", "readout_runs"): [
        "run_id", "operation", "outcome", "failure", "usage_refs", "started_at", "ended_at",
    ],
    ("common", "job_executions"): [
        "execution_id", "job_id", "status", "attempt", "queued_at", "started_at", "ended_at",
        "produced", "failure_kind", "usage_refs",
    ],
    ("common", "usage_records"): [
        "contract", "contract_version", "usage_id", "execution_ref", "run_ref", "run_ref_reason",
        "case_id", "occurred_at", "provider_label",
        "operation", "token_usage", "processed_duration_sec", "latency_ms", "pricing_context", "cost",
    ],
    # 이슈 #39 Required-2/Required-5: CorrectionRecord의 contract owner이자 runtime producer는
    # case다 — case 모듈 fixture에만 존재해야 하고(아래 §8 case-ownership 검사), adr-correction-record.md
    # L20의 8필드 최소 스키마(correction_id·case_id·selection_rev·kind·target_field·previous_value·
    # new_value·corrected_at) + 이 mock pack 공통 fixture 메타(contract·contract_version) + Draft부터
    # 있던 optional supersedes_ref를 갖춰야 한다 (contract-correction-record.md §4).
    ("case", "correction_records"): [
        "contract", "contract_version", "correction_id", "case_id", "selection_rev", "kind",
        "target_field", "previous_value", "new_value", "supersedes_ref", "corrected_at",
    ],
    ("case", "job_records"): [
        "job_id", "case_id", "case_rev", "kind", "scope_ref", "input_fingerprint",
        "force_rerun", "requested_at",
    ],
    ("recording", "span_resolutions"): [
        "timeline_ref", "requested_range", "status", "spans", "missing_ranges", "failure",
    ],
    ("recording", "source_assets"): [
        "contract", "contract_version", "source_asset_ref", "asset_kind", "external_source_ref",
        "media_stream_refs", "byte_size", "availability", "duration_sec",
    ],
    ("recording", "asset_facts"): [
        "asset_ref", "asset_kind", "derived_role", "byte_size", "availability", "checked_at",
        "lineage", "duration_sec", "timeline_ref", "timeline_range",
    ],
    ("evidence", "time_resolutions"): [
        "contract_version", "resolution_ref", "status", "considered", "conflict", "provenance", "post_stamp",
    ],
    ("evidence", "evidence_records"): [
        "contract_version", "record_ref", "case_ref", "selection_rev", "basis", "event", "provenance",
    ],
    ("evidence", "requirement_reports"): [
        "contract_version", "requirement_report_ref", "scope", "basis", "policy_ref", "evaluated_at",
        "overall", "checks",
    ],
    ("evidence", "report_packages"): [
        "contract_version", "package_ref", "evidence_record_ref", "requirement_report_ref", "created_at",
        "report_inputs", "report", "assets", "provenance", "handoff",
    ],
    ("case", "case_views"): [
        "case_id", "case_rev", "stage", "user_reviewed", "manifest_summary", "hints", "progress",
        "candidates", "evidence", "requirements_evidence", "requirements_package", "package",
        "running_jobs", "notices",
    ],
}

ANALYSIS_RUN_KEYS = [
    "run_id", "operation", "input_ref", "implementation", "outcome", "started_at",
    "completed_at", "issues", "usage_refs", "usage_summary", "contract_version",
]
OBSERVATION_KEYS = ["contract_version", "value", "status", "source", "support_refs", "produced_by"]

for sid, mods in scenario_docs.items():
    for (module, array_key), keys in REQUIRED_OBJECT_KEYS.items():
        for i, item in enumerate(mods.get(module, {}).get(array_key, [])):
            for k in keys:
                if k not in item:
                    err(f"[REQUIRED_FIELD] {sid}/{module}.{array_key}[{i}]: missing required key '{k}'")
    for i, block in enumerate(mods.get("search", {}).get("analysis_run_candidate_events", [])):
        run = block.get("analysis_run", {})
        for k in ANALYSIS_RUN_KEYS:
            if k not in run:
                err(f"[REQUIRED_FIELD] {sid}/search.analysis_run_candidate_events[{i}].analysis_run: "
                    f"missing required key '{k}'")
    for key in ("plate_readouts", "overlay_time_readouts"):
        for i, r in enumerate(mods.get("readout", {}).get(key, [])):
            obs = r.get("observation")
            if obs is None:
                err(f"[REQUIRED_FIELD] {sid}/readout.{key}[{i}]: missing 'observation'")
                continue
            for k in OBSERVATION_KEYS:
                if k not in obs:
                    err(f"[REQUIRED_FIELD] {sid}/readout.{key}[{i}].observation: missing required key '{k}'")

# ---- 8. conditional invariants ----------------------------------------------

for sid, mods in scenario_docs.items():
    # VisualEvidence
    for i, ve in enumerate(mods.get("search", {}).get("visual_evidences", [])):
        base = f"{sid}/search.visual_evidences[{i}]"
        if "legal_status" in ve and ve["legal_status"] is not None:
            err(f"[INVARIANT] {base}.legal_status must be null (contract-visual-evidence.md §3)")
        verification, vet = ve.get("verification"), ve.get("visual_event_type")
        if verification == "OBSERVED" and vet is None:
            err(f"[INVARIANT] {base}: verification=OBSERVED requires non-null visual_event_type")
        if verification in ("NOT_OBSERVED", "UNCERTAIN") and vet is not None:
            err(f"[INVARIANT] {base}: verification={verification} requires visual_event_type=null")

    # PlateReadout abstain semantics
    for i, r in enumerate(mods.get("readout", {}).get("plate_readouts", [])):
        base = f"{sid}/readout.plate_readouts[{i}]"
        abstained = r.get("abstained")
        status = (r.get("observation") or {}).get("status")
        if abstained is True:
            if status != "NEEDS_REVIEW":
                err(f"[INVARIANT] {base}: abstained=true requires observation.status=NEEDS_REVIEW (got {status!r})")
            if not r.get("abstain_reason"):
                err(f"[INVARIANT] {base}: abstained=true requires abstain_reason")
        elif abstained is False and r.get("abstain_reason") is not None:
            err(f"[INVARIANT] {base}: abstained=false requires abstain_reason=null")

    # asset availability <-> byte_size, timeline pair rule
    recording_doc = mods.get("recording", {})
    for array_key in ("source_assets", "analysis_sources", "incident_clips", "derived_assets", "asset_facts"):
        for i, a in enumerate(recording_doc.get(array_key, [])):
            base = f"{sid}/recording.{array_key}[{i}]"
            if a.get("availability") == "AVAILABLE" and a.get("byte_size") is None:
                err(f"[INVARIANT] {base}: availability=AVAILABLE requires non-null byte_size")
            if ("timeline_ref" in a) and ("timeline_range" in a):
                if (a["timeline_ref"] is None) != (a["timeline_range"] is None):
                    err(f"[INVARIANT] {base}: timeline_ref and timeline_range must be both null or both set")

    # SpanResolution completeness
    for i, sr in enumerate(recording_doc.get("span_resolutions", [])):
        base = f"{sid}/recording.span_resolutions[{i}]"
        status = sr.get("status")
        if status == "COMPLETE" and (sr.get("missing_ranges") or sr.get("failure") is not None):
            err(f"[INVARIANT] {base}: status=COMPLETE requires missing_ranges=[] and failure=null")
        if status == "FAILED" and sr.get("failure") is None:
            err(f"[INVARIANT] {base}: status=FAILED requires non-null failure")
        if status == "PARTIAL" and not sr.get("missing_ranges"):
            err(f"[INVARIANT] {base}: status=PARTIAL requires non-empty missing_ranges")

    # DeletionReport failure_code
    for i, dr in enumerate(recording_doc.get("deletion_reports", [])):
        for j, item in enumerate(dr.get("items", [])):
            if item.get("result") == "FAILED" and item.get("failure_code") is None:
                err(f"[INVARIANT] {sid}/recording.deletion_reports[{i}].items[{j}]: "
                    f"result=FAILED requires non-null failure_code")

    # TimeResolution resolved presence
    for i, tr in enumerate(mods.get("evidence", {}).get("time_resolutions", [])):
        base = f"{sid}/evidence.time_resolutions[{i}]"
        if tr.get("status") == "UNKNOWN" and tr.get("resolved") is not None:
            err(f"[INVARIANT] {base}: status=UNKNOWN must not carry 'resolved'")
        if tr.get("status") in ("OK", "NEEDS_REVIEW") and tr.get("resolved") is None:
            err(f"[INVARIANT] {base}: status={tr.get('status')} requires 'resolved'")
        comp = (tr.get("resolved") or {}).get("computation") or {}
        if comp.get("mode") == "BASE_PLUS_OFFSET":
            if comp.get("base_input_ref") is None or comp.get("source_offset_ms") is None:
                err(f"[INVARIANT] {base}: BASE_PLUS_OFFSET requires base_input_ref and source_offset_ms")

    # EvidenceValue rules + RequirementReport overall precedence
    def walk_evidence_values(node, path):
        if isinstance(node, dict):
            if "needs_review" in node and "user_corrected" in node and "value" in node:
                if node.get("user_corrected") and node.get("needs_review"):
                    err(f"[INVARIANT] {path}: user_corrected and needs_review cannot both be true")
                if node.get("value") is None and node.get("needs_review"):
                    err(f"[INVARIANT] {path}: value=null cannot have needs_review=true")
            for k, v in node.items():
                walk_evidence_values(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk_evidence_values(v, f"{path}[{i}]")

    for i, rec in enumerate(mods.get("evidence", {}).get("evidence_records", [])):
        walk_evidence_values(rec, f"{sid}/evidence.evidence_records[{i}]")

    for i, rep in enumerate(mods.get("evidence", {}).get("requirement_reports", [])):
        outcomes = [c.get("outcome") for c in rep.get("checks", [])]
        for level in ("BLOCK", "UNKNOWN", "WARN", "PASS"):
            if level in outcomes or (level == "PASS" and outcomes):
                expected = level
                break
        else:
            expected = None
        if expected and rep.get("overall") != expected:
            err(f"[INVARIANT] {sid}/evidence.requirement_reports[{i}]: overall={rep.get('overall')!r} but "
                f"precedence(BLOCK>UNKNOWN>WARN>PASS) over checks gives {expected!r}")

    # ---- 8-1. 이슈 #39 신규 검사 (Required-5) ---------------------------------

    # CorrectionRecord case-ownership: contract owner이자 runtime producer가 모두 case이므로
    # (contract-correction-record.md, Required-2) case가 아닌 모듈 fixture에 correction_records가
    # 있으면 안 된다 — evidence는 ContractRef(provenance.correction_refs)로만 참조한다.
    for module, doc in mods.items():
        if module != "case" and doc.get("correction_records"):
            err(f"[INVARIANT] {sid}/{module}.correction_records: CorrectionRecord는 case fixture에만 "
                f"존재해야 한다(contract owner=runtime producer=case, 이슈 #39 Required-2) — "
                f"{module}에 {len(doc['correction_records'])}건 있음")

    # UsageRecord run_ref / run_ref_reason 결합 규칙 (contract-usage-record.md §8 invariant 13)
    for i, u in enumerate(mods.get("common", {}).get("usage_records", [])):
        base = f"{sid}/common.usage_records[{i}]"
        run_ref, reason = u.get("run_ref"), u.get("run_ref_reason")
        if run_ref is not None and reason is not None:
            err(f"[INVARIANT] {base}: run_ref != null이면 run_ref_reason은 null이어야 한다 "
                f"(got run_ref={run_ref!r}, run_ref_reason={reason!r})")
        if run_ref is None and reason not in RUN_REF_REASON_VALUES:
            err(f"[INVARIANT] {base}: run_ref == null이면 run_ref_reason은 "
                f"{sorted(RUN_REF_REASON_VALUES)} 중 하나여야 한다 (got {reason!r})")

    # TimeResolution invariant 12 (2026-09-11, 이슈 #39 A-1) — computation.mode=USER_OVERRIDE 체인.
    # 역방향(AGREED이면 반드시 USER_OVERRIDE)은 아직 open topic이라 강제하지 않는다.
    for i, tr in enumerate(mods.get("evidence", {}).get("time_resolutions", [])):
        base = f"{sid}/evidence.time_resolutions[{i}]"
        resolved = tr.get("resolved") or {}
        comp = resolved.get("computation") or {}
        if comp.get("mode") == "USER_OVERRIDE":
            if tr.get("status") != "OK":
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires status=OK "
                    f"(got {tr.get('status')!r})")
            if resolved.get("verification") != "AGREED":
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires "
                    f"resolved.verification=AGREED (got {resolved.get('verification')!r})")
            if resolved.get("user_corrected") is not True:
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires "
                    f"resolved.user_corrected=true")
            sel_ref = (tr.get("provenance") or {}).get("selected_input_ref") or {}
            if sel_ref.get("kind") != "correction_record":
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires "
                    f"provenance.selected_input_ref.kind=correction_record (got {sel_ref.get('kind')!r})")
            selected = [c for c in tr.get("considered", []) if c.get("used")]
            if not selected or any(c.get("input_kind") != "USER_INPUT" for c in selected):
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires the used "
                    f"considered[] entry to have input_kind=USER_INPUT")
            elif any(c.get("verification") != "AGREED" for c in selected):
                err(f"[INVARIANT] {base}: computation.mode=USER_OVERRIDE requires the used "
                    f"considered[] entry to have verification=AGREED")

    # EvidenceRecord.situation_response invariants 16~18 (evidence-record/v1.3 §10)
    for i, rec in enumerate(mods.get("evidence", {}).get("evidence_records", [])):
        sit = rec.get("situation_response")
        if sit is None:
            continue
        base = f"{sid}/evidence.evidence_records[{i}].situation_response"
        value = sit.get("value")
        if value in ("CONFIRMED", "CORRECTED") and sit.get("candidate_ref") is None:
            err(f"[INVARIANT] {base}: value={value!r} requires non-null candidate_ref (invariant 16)")
        if value == "CORRECTED":
            refs = (rec.get("provenance") or {}).get("correction_refs", [])
            case_doc_for_scenario = mods.get("case", {})
            corr_kinds = {c.get("correction_id"): c.get("kind")
                          for c in case_doc_for_scenario.get("correction_records", [])}
            if not any(corr_kinds.get(r.get("ref")) == "SITUATION_CHANGE" for r in refs):
                err(f"[INVARIANT] {base}: value=CORRECTED requires a provenance.correction_refs entry "
                    f"resolving to a CorrectionRecord with kind=SITUATION_CHANGE (invariant 17)")

    # CaseView.evidence.review_needed / reason_code 파생 규칙 (contract-job-record-case-view.md B§7)
    for i, cv in enumerate(mods.get("case", {}).get("case_views", [])):
        ev = cv.get("evidence")
        if not ev:
            continue
        base = f"{sid}/case.case_views[{i}].evidence"
        causes = [f for f in SIX_DISPLAY_FIELDS
                  if (ev.get(f) or {}).get("needs_review")
                  or (ev.get(f) or {}).get("info_state") == "INFO_NEEDS_REVIEW"]
        expected_review_needed = len(causes) > 0
        if ev.get("review_needed") != expected_review_needed:
            err(f"[INVARIANT] {base}.review_needed={ev.get('review_needed')!r} but derives to "
                f"{expected_review_needed!r} from six-display OR (causes={causes})")
        if expected_review_needed:
            if len(causes) == 1:
                expected_reason = f"evidence.{causes[0].split('_display')[0]}_needs_review"
                if ev.get("reason_code") != expected_reason:
                    err(f"[INVARIANT] {base}.reason_code={ev.get('reason_code')!r} but exactly one "
                        f"cause ({causes[0]}) implies {expected_reason!r}")
            else:
                if ev.get("reason_code") != "evidence.multiple_fields_need_review":
                    err(f"[INVARIANT] {base}.reason_code={ev.get('reason_code')!r} but {len(causes)} "
                        f"causes ({causes}) imply 'evidence.multiple_fields_need_review'")
        elif ev.get("reason_code") is not None:
            err(f"[INVARIANT] {base}.reason_code={ev.get('reason_code')!r} must be null when "
                f"review_needed=false")

    # correction selection_rev ↔ candidate 선택 context 정합 (이슈 #39 Required-3/contract-correction-record.md
    # §4 「selection_rev는 수정 발생 시점의 candidate 선택 context」) — case가 소유한 CorrectionRecord와
    # 그것을 참조하는 evidence의 EvidenceRecord는 correction 발생 시점 기준 같은 selection_rev를 공유해야
    # 한다. 이후 실제 후보 재선택이 일어나 selection_rev가 다시 올라간 EvidenceRecord가 있다면 그 최신
    # record는 이 correction을 더는 basis로 삼지 않아야 하므로, 이 검사는 「해당 CorrectionRecord를
    # correction_refs로 참조하는 모든 EvidenceRecord」에 대해서만 일치를 요구한다.
    corr_by_id = {c.get("correction_id"): c for c in mods.get("case", {}).get("correction_records", [])}
    for i, rec in enumerate(mods.get("evidence", {}).get("evidence_records", [])):
        refs = (rec.get("provenance") or {}).get("correction_refs", [])
        for r in refs:
            corr = corr_by_id.get(r.get("ref"))
            if corr is not None and corr.get("selection_rev") != rec.get("selection_rev"):
                err(f"[INVARIANT] {sid}/evidence.evidence_records[{i}]: selection_rev="
                    f"{rec.get('selection_rev')!r} but referenced CorrectionRecord "
                    f"'{r.get('ref')}'.selection_rev={corr.get('selection_rev')!r} — selection_rev는 "
                    f"수정 발생 시점의 candidate 선택 context이므로 이 둘은 일치해야 한다")

# ---- 9. plate consensus / masking consistency -------------------------------

for sid, mods in scenario_docs.items():
    for i, r in enumerate(mods.get("readout", {}).get("plate_readouts", [])):
        base = f"{sid}/readout.plate_readouts[{i}]"
        texts = [fr.get("text") for fr in r.get("frame_results", []) if isinstance(fr.get("text"), str)]
        consensus = r.get("consensus") or {}
        declared = consensus.get("disagree_positions")
        if not texts or declared is None:
            continue
        if len({len(t) for t in texts}) != 1:
            warn(f"[CONSENSUS?] {base}: frame_results texts have differing lengths; skipped position check")
            continue
        actual = sorted({idx for idx in range(len(texts[0])) if len({t[idx] for t in texts}) > 1})
        if sorted(declared) != actual:
            err(f"[CONSENSUS] {base}: disagree_positions={sorted(declared)} but frame_results actually "
                f"disagree at {actual} (0-based, per contract-plate-overlay-readout.md §4 example)")
        value = (r.get("observation") or {}).get("value")
        if isinstance(value, str) and len(value) == len(texts[0]):
            masked = sorted(idx for idx, ch in enumerate(value) if ch == "?")
            if masked and masked != actual:
                err(f"[CONSENSUS] {base}: observation.value masks positions {masked} but actual disagreement "
                    f"is at {actual}")

# ---- 10. plain-string refs must resolve too (§11-1) --------------------------
#
# The ContractRef walk above only sees {"kind": ..., "ref": ...} shapes. A large
# share of the pack's references are plain strings, and those were the blind spot.

STRING_REF_FIELDS = {
    "thumbnail_ref", "thumb_ref", "preview_ref", "artifact_ref", "record_id",
    "scope_ref", "execution_ref", "job_id", "source_candidate_ref", "frame_ref",
    "source_asset_ref", "media_stream_ref", "analysis_source_ref",
    "incident_clip_ref", "derived_asset_ref", "remote_copy_ref",
    "timeline_id", "candidate_id", "run_id", "readout_id", "usage_id",
    "case_id", "scope_id", "visual_evidence_id", "execution_id", "package_ref",
}
LIST_REF_FIELDS = {"usage_refs", "media_stream_refs", "time_source_candidates", "evidence_refs"}
# opaque identifiers that intentionally have no object in this pack
OPAQUE_STRING_FIELDS = {
    "crop_ref", "track_ref", "profile_ref", "transform_ref", "template_ref",
    "policy_ref", "provider_object_ref", "impl_id", "model_ref", "pricing_id",
}


def walk_string_refs(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in OPAQUE_STRING_FIELDS:
                continue
            if k in STRING_REF_FIELDS and isinstance(v, str):
                out.append((f"{path}.{k}", v))
            elif k in LIST_REF_FIELDS and isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        out.append((f"{path}.{k}[{i}]", item))
            else:
                walk_string_refs(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_string_refs(v, f"{path}[{i}]", out)


for sid, mods in scenario_docs.items():
    defined = defined_ids_by_scenario[sid]
    found = []
    for module, doc in mods.items():
        walk_string_refs(doc, f"{sid}/{module}", found)
    for path, ref in found:
        if ref not in defined:
            err(f"[DANGLING_STRING_REF] {path}: '{ref}' does not resolve to any ID defined within scenario '{sid}'")

# ---- 11. cross-scenario ID uniqueness (§11-10) -------------------------------

seen_ids = {}
for sid, ids in defined_ids_by_scenario.items():
    for i in ids:
        seen_ids.setdefault(i, []).append(sid)
for i, sids in sorted(seen_ids.items()):
    if len(sids) > 1:
        warn(f"[ID_REUSE] '{i}' is defined in multiple scenarios: {sorted(sids)}")

# ---- 12. manifest self-consistency (§11-3) -----------------------------------

repo_root = ROOT.parent.parent
top_manifest = all_docs.get(ROOT / "manifest.json")
if top_manifest:
    listed = set()
    for entry in top_manifest.get("scenarios", []):
        listed.add(entry.get("scenario_id"))
        rel = entry.get("manifest_ref")
        if rel and not (repo_root / rel).exists():
            err(f"[MANIFEST] manifest.json scenarios[].manifest_ref '{rel}' does not exist")
    for rel in top_manifest.get("eval_fixtures", []):
        if not (repo_root / rel).exists():
            err(f"[MANIFEST] manifest.json eval_fixtures '{rel}' does not exist")
    missing = set(scenario_docs) - listed
    extra = listed - set(scenario_docs)
    if missing:
        err(f"[MANIFEST] scenarios present on disk but absent from manifest.json: {sorted(missing)}")
    if extra:
        err(f"[MANIFEST] scenarios listed in manifest.json but not found on disk: {sorted(extra)}")

for manifest_path in sorted((ROOT / "scenarios").glob("scenario_*.json")):
    doc = all_docs.get(manifest_path)
    if not doc:
        continue
    sid = doc.get("scenario_id")
    defined = defined_ids_by_scenario.get(sid, set())
    for key, value in (doc.get("shared_ids") or {}).items():
        if isinstance(value, str) and value not in defined:
            err(f"[MANIFEST] {manifest_path.name}: shared_ids.{key} = '{value}' is not defined in scenario '{sid}'")
    declared_modules = set(doc.get("artifacts", {}))
    actual_modules = set(scenario_docs.get(sid, {}))
    if declared_modules != actual_modules:
        err(f"[MANIFEST] {manifest_path.name}: artifacts lists {sorted(declared_modules)} "
            f"but scenario actually has {sorted(actual_modules)}")

# ---- 13. eval fixtures (§11-4) ----------------------------------------------

all_defined = set().union(*defined_ids_by_scenario.values()) if defined_ids_by_scenario else set()
for eval_path in sorted((ROOT / "expected").glob("*.json")):
    doc = all_docs.get(eval_path)
    if not doc:
        continue
    name = eval_path.name
    if not doc.get("provisional_non_contract_schema"):
        err(f"[EVAL] {name}: must declare provisional_non_contract_schema=true "
            f"(eval Ground Truth 계약 미확정)")
    targets = doc.get("metric_targets", [])
    if not targets:
        err(f"[EVAL] {name}: metric_targets is empty")
    refs = []
    walk_refs(doc, name, refs)
    for path, kind, ref in refs:
        if kind not in EXEMPT_KINDS and ref not in all_defined:
            err(f"[EVAL] {path}: {{kind:'{kind}', ref:'{ref}'}} does not resolve to any fixture in the pack")
    kind_label = doc.get("kind")
    matches = [t.get("expect_match") for t in targets]
    if kind_label == "ALWAYS_CORRECT" and not all(matches):
        err(f"[EVAL] {name}: kind=ALWAYS_CORRECT but some metric_targets have expect_match=false")
    if kind_label == "DELIBERATELY_WRONG":
        if all(matches):
            err(f"[EVAL] {name}: kind=DELIBERATELY_WRONG but every metric_target expects a match")
        if any("actual_ref" in t for t in targets):
            err(f"[EVAL] {name}: DELIBERATELY_WRONG fixtures must not carry actual_ref — a harness that "
                f"dereferences it gets the correct value and the test passes for the wrong reason")

# ---- 14. derived time values (§11-5) ----------------------------------------

from datetime import datetime, timedelta  # noqa: E402


def parse_dt(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


for sid, mods in scenario_docs.items():
    tsc_values = {
        c.get("candidate_id"): c.get("value")
        for c in mods.get("recording", {}).get("time_source_candidates", [])
    }
    clips = {
        c.get("incident_clip_ref"): c
        for c in mods.get("recording", {}).get("incident_clips", [])
    }

    # BASE_PLUS_OFFSET: resolved.value == base candidate value + source_offset_ms
    for i, tr in enumerate(mods.get("evidence", {}).get("time_resolutions", [])):
        resolved = tr.get("resolved") or {}
        comp = resolved.get("computation") or {}
        if comp.get("mode") != "BASE_PLUS_OFFSET":
            continue
        base_ref = (comp.get("base_input_ref") or {}).get("ref")
        base_value = parse_dt(tsc_values.get(base_ref))
        got = parse_dt(resolved.get("value"))
        offset_ms = comp.get("source_offset_ms")
        if base_value and got and isinstance(offset_ms, int):
            expected = base_value + timedelta(milliseconds=offset_ms)
            if expected != got:
                err(f"[TIME] {sid}/evidence.time_resolutions[{i}]: BASE_PLUS_OFFSET gives "
                    f"{expected.isoformat()} (base {base_ref} + {offset_ms}ms) but resolved.value is "
                    f"{resolved.get('value')}")

    # overlay samples must sit inside the clip they were read from
    for i, r in enumerate(mods.get("readout", {}).get("overlay_time_readouts", [])):
        clip_ref = (r.get("input_ref") or {}).get("incident_clip_ref")
        clip = clips.get(clip_ref)
        if not clip:
            continue
        duration = clip.get("duration_sec")
        for j, s in enumerate(r.get("samples", [])):
            off = s.get("offset_sec")
            if isinstance(off, (int, float)) and isinstance(duration, (int, float)):
                if not (0 <= off <= duration):
                    err(f"[TIME] {sid}/readout.overlay_time_readouts[{i}].samples[{j}]: offset_sec={off} "
                        f"is outside clip '{clip_ref}' [0, {duration}] — clip-relative offset expected "
                        f"(contract-plate-overlay-readout.md §6)")
        declared_count = (r.get("validation") or {}).get("sample_count")
        if isinstance(declared_count, int) and declared_count != len(r.get("samples", [])):
            err(f"[TIME] {sid}/readout.overlay_time_readouts[{i}]: validation.sample_count="
                f"{declared_count} but samples[] has {len(r.get('samples', []))} entries")

    # AssetSpan: source_range length must equal timeline_range length
    def check_spans(spans, where):
        for j, sp in enumerate(spans):
            tl, src = sp.get("timeline_range") or {}, sp.get("source_range") or {}
            if all(k in tl for k in ("start_sec", "end_sec")) and all(k in src for k in ("start_sec", "end_sec")):
                tl_len = tl["end_sec"] - tl["start_sec"]
                src_len = src["end_sec"] - src["start_sec"]
                if abs(tl_len - src_len) > 1e-6:
                    err(f"[TIME] {where}[{j}]: timeline_range length {tl_len}s != source_range length {src_len}s")

    for i, sr in enumerate(mods.get("recording", {}).get("span_resolutions", [])):
        check_spans(sr.get("spans", []), f"{sid}/recording.span_resolutions[{i}].spans")
    for i, clip in enumerate(mods.get("recording", {}).get("incident_clips", [])):
        check_spans((clip.get("source_provenance") or {}).get("asset_spans", []),
                    f"{sid}/recording.incident_clips[{i}].source_provenance.asset_spans")

# ---- report -------------------------------------------------------------

print(f"Scanned {len(all_docs)} JSON files across {len(scenario_docs)} scenarios.\n")

if warnings:
    print(f"WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")
    print()

if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
    print()
    print("VALIDATION FAILED")
    sys.exit(1)
else:
    print("VALIDATION PASSED — no errors found.")
    sys.exit(0)
