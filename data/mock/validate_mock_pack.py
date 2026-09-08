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

CLOSED_ENUMS = {
    ("readout_runs", "outcome"): {"SUCCEEDED", "PARTIAL", "FAILED"},
    ("readout_runs", "operation"): {"PLATE_READ", "OVERLAY_TIME_READ"},
    ("job_executions", "status"): {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "STALE"},
    ("requirement_reports", "overall"): {"PASS", "WARN", "BLOCK", "UNKNOWN"},
    ("time_resolutions", "status"): {"OK", "NEEDS_REVIEW", "UNKNOWN"},
}

for sid, mods in scenario_docs.items():
    for module, doc in mods.items():
        for (array_key, field), allowed in CLOSED_ENUMS.items():
            if array_key not in doc:
                continue
            for i, item in enumerate(doc[array_key]):
                val = item.get(field)
                if val is not None and val not in allowed:
                    err(f"[ENUM] {sid}/{module}.{array_key}[{i}].{field} = '{val}' not in {sorted(allowed)}")

    # CaseView.stage
    case_doc = mods.get("case")
    if case_doc:
        for i, cv in enumerate(case_doc.get("case_views", [])):
            stage = cv.get("stage")
            allowed = {"INTAKE", "SEARCHING", "CANDIDATE_REVIEW", "EVIDENCE_REVIEW", "READY"}
            if stage not in allowed:
                err(f"[ENUM] {sid}/case.case_views[{i}].stage = '{stage}' not in {sorted(allowed)}")

# ---- 4. build a registry of every opaque ID defined in a scenario, then check refs resolve --

ID_FIELD_CANDIDATES = [
    "source_asset_ref", "media_stream_ref", "frame_ref", "timeline_id", "candidate_id",
    "run_id", "readout_id", "usage_id", "scope_id", "incident_clip_ref", "derived_asset_ref",
    "remote_copy_ref", "analysis_source_ref", "job_id", "execution_id", "case_id",
    "eval_fixture_id", "visual_evidence_id",
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
# - correction_record: contract-correction-record.md is still Draft (not Final) — see
#   docs/mock/04_mock_validation_report.md "Fixture 생성 불가".
# - external_source: raw upload/ingest source metadata; no Final Data Contract in the
#   14-contract set owns ExternalSource's own field schema, so it is referenced by
#   SourceAsset but never materialized as its own mock artifact here.
EXEMPT_KINDS = {"correction_record", "external_source"}

for sid, mods in scenario_docs.items():
    defined = collect_defined_ids(mods)
    refs = []
    for module, doc in mods.items():
        walk_refs(doc, f"{sid}/{module}", refs)
    for path, kind, ref in refs:
        if kind in EXEMPT_KINDS:
            continue
        if ref not in defined:
            err(f"[DANGLING_REF] {path}: {{kind:'{kind}', ref:'{ref}'}} does not resolve to any ID defined within scenario '{sid}'")

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
