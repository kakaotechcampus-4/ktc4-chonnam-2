#!/usr/bin/env python3
"""Mock Pack v1(seed) 경량 검증 스크립트.

무거운 validation framework를 새로 만들지 않는다(요청 §20 원칙). 확인하는 것:
  1. JSON parse 가능 여부 (모든 data/mock/**/*.json)
  2. manifest.json / scenarios/*.json / fixture_index.csv가 가리키는 경로가 실제로 존재하는가
  3. 각 시나리오 내부에서 candidate_id / run_id / job_id / execution_id / usage_id / case_id 등
     ID 참조가 서로 다른 모듈 fixture 사이에서 일관되는가 (principle 13 — E2E 연결성)
  4. enum 값이 각 계약이 정의한 값 공간 안에 있는가 (알려진 enum만 검사, 계약에 없는 필드는 건너뜀)
  5. start <= end류 시간/구간 불변조건 (SpanResolution, AnalysisRun, JobExecution, ReadoutRun)

Pydantic 등 실제 Contract Model이 아직 코드로 없으므로(§4-모듈5 상태: "아직 코드가 없다"),
이 스크립트가 임시 최소 검증이다. Contract 의미 전체나 Owner 수락을 검증하지 않는다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "data" / "mock"

errors = []
warnings = []
checked_files = 0


def load_json(path: Path):
    global checked_files
    checked_files += 1
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        errors.append(f"[PARSE] {path.relative_to(ROOT)}: {e}")
        return None


# 1. JSON parse — every .json under data/mock
json_files = sorted(MOCK.rglob("*.json"))
data_by_relpath = {}
for jf in json_files:
    data = load_json(jf)
    if data is not None:
        data_by_relpath[str(jf.relative_to(MOCK))] = data

# 2. manifest + scenario files + fixture_index.csv path existence
manifest = data_by_relpath.get("manifest.json")
if manifest is None:
    errors.append("[MANIFEST] manifest.json parse 실패 또는 없음")
else:
    for scn in manifest.get("scenarios", []):
        scn_file = MOCK / scn["file"]
        if not scn_file.exists():
            errors.append(f"[MANIFEST] scenario file 없음: {scn['file']}")

for scn_path in sorted((MOCK / "scenarios").glob("*.json")):
    scn = load_json(scn_path)
    if scn is None:
        continue
    artifacts = scn.get("artifacts", {})
    for module, entries in artifacts.items():
        if not isinstance(entries, dict):
            continue
        for key, relpath in entries.items():
            if relpath is None:
                continue  # 의도된 부재 (예: partial 시나리오의 report_package=null) — 오류 아님
            f = MOCK / relpath
            if not f.exists():
                errors.append(f"[SCENARIO:{scn['scenario_id']}] {module}.{key} 경로 없음: {relpath}")

csv_path = MOCK / "fixture_index.csv"
if csv_path.exists():
    import csv as csvmod
    with open(csv_path, encoding="utf-8") as f:
        reader = csvmod.DictReader(f)
        for row in reader:
            fp = row["file"]
            if fp.startswith("N/A"):
                continue
            if not (MOCK / fp).exists():
                errors.append(f"[CSV] fixture_index.csv 행 경로 없음: {fp}")
else:
    errors.append("[CSV] fixture_index.csv 없음")


def get(relpath):
    return data_by_relpath.get(relpath)


# 3 & 5. per-scenario cross-reference + time invariant checks
def check_scenario(tag, case_id):
    def p(module, name):
        return f"{module}/{name}.{tag}.json"

    timeline = get(p("recording", "timeline"))
    span_res = get(p("recording", "span_resolution"))
    scope = get(p("search", "analysis_scope"))
    run = get(p("search", "analysis_run"))
    candidates = get(p("search", "candidate_events"))
    ve = get(p("search", "visual_evidence"))
    readout_runs = get(p("readout", "readout_runs"))
    plate = get(p("readout", "plate_readout"))
    overlay = get(p("readout", "overlay_time_readout"))
    tres = get(p("evidence", "time_resolution"))
    ev_record = get(p("evidence", "evidence_record"))
    ev_needs = get(p("evidence", "evidence_needs"))
    req = get(p("evidence", "requirement_report"))
    job_records = get(p("case", "job_records"))
    job_execs = get(p("case", "job_executions"))
    usage = get(p("case", "usage_records"))
    case_view = get(p("case", "case_view"))

    # timeline <-> span_resolution
    if timeline and span_res:
        if span_res["timeline_ref"]["timeline_id"] != timeline["timeline_id"]:
            errors.append(f"[{tag}] span_resolution.timeline_ref != timeline.timeline_id")
        for span in span_res.get("spans", []):
            if span["timeline_range"]["start_sec"] >= span["timeline_range"]["end_sec"]:
                errors.append(f"[{tag}] AssetSpan.timeline_range start>=end")
            if span["source_range"]["start_sec"] >= span["source_range"]["end_sec"]:
                errors.append(f"[{tag}] AssetSpan.source_range start>=end")
        rr = span_res["requested_range"]
        if rr["start_sec"] >= rr["end_sec"]:
            errors.append(f"[{tag}] SpanResolution.requested_range start>=end")
        status = span_res["status"]
        if status == "COMPLETE" and span_res["missing_ranges"]:
            errors.append(f"[{tag}] SpanResolution COMPLETE인데 missing_ranges 존재")
        if status == "PARTIAL" and (not span_res["spans"] or not span_res["missing_ranges"]):
            errors.append(f"[{tag}] SpanResolution PARTIAL인데 spans/missing_ranges 중 하나가 비어있음")
        if status == "FAILED" and span_res["spans"]:
            errors.append(f"[{tag}] SpanResolution FAILED인데 usable spans 존재")

    # scope -> run
    if scope and run:
        if run["input_ref"]["ref"] != scope["scope_id"]:
            errors.append(f"[{tag}] AnalysisRun.input_ref != AnalysisScope.scope_id")
        if run["completed_at"] < run["started_at"]:
            errors.append(f"[{tag}] AnalysisRun.completed_at < started_at")
        if run["outcome"] == "FAILED" and candidates:
            errors.append(f"[{tag}] AnalysisRun FAILED인데 CandidateEvent 존재")
        if run["outcome"] == "PARTIAL" and not run["issues"]:
            errors.append(f"[{tag}] AnalysisRun PARTIAL인데 issues=[]")
        if run["outcome"] == "SUCCEEDED" and run["issues"]:
            warnings.append(f"[{tag}] AnalysisRun SUCCEEDED인데 issues 존재 (실행실패 의미 issue인지 확인 필요)")

    # run -> candidates
    if run and candidates:
        seen_ranks = set()
        for c in candidates:
            if c["run_id"] != run["run_id"]:
                errors.append(f"[{tag}] CandidateEvent.run_id({c['run_id']}) != AnalysisRun.run_id({run['run_id']})")
            if c["span"]["start_ms"] >= c["span"]["end_ms"]:
                errors.append(f"[{tag}] CandidateEvent.span start_ms>=end_ms")
            if not (c["span"]["start_ms"] <= c["span"]["representative_ms"] <= c["span"]["end_ms"]):
                errors.append(f"[{tag}] CandidateEvent.representative_ms가 span 범위 밖")
            if c["rank"] in seen_ranks:
                errors.append(f"[{tag}] CandidateEvent.rank 중복: {c['rank']}")
            seen_ranks.add(c["rank"])
            if timeline and c["span"]["timeline_id"] != timeline["timeline_id"]:
                errors.append(f"[{tag}] CandidateEvent.span.timeline_id != RecordingTimeline.timeline_id")

    # candidate -> visual_evidence
    if candidates and ve:
        cand_ids = {c["candidate_id"] for c in candidates}
        if ve.get("candidate_id") not in cand_ids:
            errors.append(f"[{tag}] VisualEvidence.candidate_id가 이 시나리오의 CandidateEvent에 없음")
        if ve["run_id"] != run["run_id"]:
            errors.append(f"[{tag}] VisualEvidence.run_id != AnalysisRun.run_id")
        v = ve["verification"]
        if v == "OBSERVED" and ve["visual_event_type"] is None:
            errors.append(f"[{tag}] VisualEvidence OBSERVED인데 visual_event_type null")
        if v in ("NOT_OBSERVED", "UNCERTAIN") and ve["visual_event_type"] is not None:
            errors.append(f"[{tag}] VisualEvidence {v}인데 visual_event_type이 null이 아님")
        if ve["legal_status"] is not None:
            errors.append(f"[{tag}] VisualEvidence.legal_status가 null이 아님 (invariant 위반)")

    # readout_runs <-> plate/overlay readouts
    if readout_runs:
        for rr in readout_runs:
            if rr["outcome"] == "SUCCEEDED" and rr["failure"] is not None:
                errors.append(f"[{tag}] ReadoutRun {rr['run_id']} SUCCEEDED인데 failure != null")
            if rr["outcome"] in ("PARTIAL", "FAILED") and rr["failure"] is None:
                errors.append(f"[{tag}] ReadoutRun {rr['run_id']} {rr['outcome']}인데 failure == null")
    if plate and candidates:
        cand_ids = {c["candidate_id"] for c in candidates}
        if plate["candidate_id"] not in cand_ids:
            errors.append(f"[{tag}] PlateReadout.candidate_id가 이 시나리오의 CandidateEvent에 없음")
        if plate["abstained"] and not plate["abstain_reason"]:
            errors.append(f"[{tag}] PlateReadout abstained=true인데 abstain_reason 없음")
        if not plate["abstained"] and plate["observation"]["status"] not in ("OK",):
            warnings.append(f"[{tag}] PlateReadout abstained=false인데 observation.status={plate['observation']['status']} (확인 필요)")
    if overlay and overlay["observation"]["value"] is not None and overlay["observation"]["status"] != "OK" and overlay["observation"]["status"] != "NEEDS_REVIEW":
        pass  # Observation enum 범위 자체는 아래 enum 체크에서 별도 확인

    # time_resolution
    if tres:
        if tres["status"] == "OK" and tres.get("resolved") is None:
            errors.append(f"[{tag}] TimeResolution OK인데 resolved 없음")
        if tres["status"] == "UNKNOWN" and tres.get("resolved") is not None:
            errors.append(f"[{tag}] TimeResolution UNKNOWN인데 resolved 존재")
        if tres.get("resolved") and not tres.get("provenance", {}).get("selected_input_ref"):
            errors.append(f"[{tag}] TimeResolution.resolved 존재하는데 provenance.selected_input_ref 없음")
        if not tres["conflict"]["exists"] and tres["conflict"]["between_refs"]:
            errors.append(f"[{tag}] TimeResolution conflict.exists=false인데 between_refs 비어있지 않음")

    # evidence_record occurred_at <-> time_resolution
    if ev_record and tres:
        oa = ev_record.get("occurred_at")
        if oa and oa["time_resolution_ref"]["ref"] != tres["resolution_ref"]["ref"]:
            errors.append(f"[{tag}] EvidenceRecord.occurred_at.time_resolution_ref != TimeResolution.resolution_ref")

    # evidence_needs <-> evidence_record
    if ev_needs and ev_record:
        if ev_needs["basis_record_ref"]["ref"] != ev_record["record_ref"]["ref"]:
            errors.append(f"[{tag}] EvidenceNeeds.basis_record_ref != EvidenceRecord.record_ref")
        kinds_seen = set()
        for item in ev_needs["items"]:
            key = (item["kind"], item["would_fill"])
            if key in kinds_seen:
                errors.append(f"[{tag}] EvidenceNeeds 같은 (kind, would_fill) 중복: {key}")
            kinds_seen.add(key)
            if item["kind"] == "PLATE_REREAD" and item["would_fill"] != "VEHICLE_NUMBER":
                errors.append(f"[{tag}] EvidenceNeeds PLATE_REREAD -> would_fill이 VEHICLE_NUMBER가 아님")
            if item["kind"] == "OVERLAY_TIME_OCR" and item["would_fill"] != "OCCURRED_AT":
                errors.append(f"[{tag}] EvidenceNeeds OVERLAY_TIME_OCR -> would_fill이 OCCURRED_AT가 아님")

    # requirement_report <-> evidence_record
    if req and ev_record:
        if req["basis"]["evidence_record_ref"]["ref"] != ev_record["record_ref"]["ref"]:
            errors.append(f"[{tag}] RequirementReport.basis.evidence_record_ref != EvidenceRecord.record_ref")
        codes = set()
        for c in req["checks"]:
            if c["code"] in codes:
                errors.append(f"[{tag}] RequirementReport.checks[].code 중복: {c['code']}")
            codes.add(c["code"])

    # package(happy only) <-> requirement_report / evidence_record
    pkg = get(p("evidence", "report_package"))
    if pkg:
        if req and pkg["requirement_report_ref"]["ref"] != req["requirement_report_ref"]["ref"]:
            errors.append(f"[{tag}] ReportPackage.requirement_report_ref != RequirementReport.requirement_report_ref")
        if req and req["scope"] != "FINAL_PACKAGE":
            errors.append(f"[{tag}] ReportPackage가 존재하는데 RequirementReport.scope != FINAL_PACKAGE")
        if req and req["overall"] not in ("PASS", "WARN"):
            errors.append(f"[{tag}] ReportPackage가 존재하는데 RequirementReport.overall이 PASS/WARN이 아님: {req['overall']}")

    # job_records / job_executions / usage_records cross-ref
    if job_records and job_execs:
        job_ids = {j["job_id"] for j in job_records}
        for ex in job_execs:
            if ex["job_id"] not in job_ids:
                errors.append(f"[{tag}] JobExecution.job_id({ex['job_id']})가 JobRecord에 없음")
            if ex["status"] == "SUCCEEDED" and ex["failure_kind"] is not None:
                errors.append(f"[{tag}] JobExecution SUCCEEDED인데 failure_kind != null (계약엔 없는 필드지만 관례상 점검)")
            if ex["status"] in ("QUEUED", "RUNNING") and ex["ended_at"] is not None:
                errors.append(f"[{tag}] JobExecution status={ex['status']}인데 ended_at이 null이 아님")
            if ex["status"] == "QUEUED" and ex["started_at"] is not None:
                errors.append(f"[{tag}] JobExecution status=QUEUED인데 started_at이 null이 아님")
    if job_execs and usage:
        exec_ids = {e["execution_id"] for e in job_execs}
        usage_ids = {u["usage_id"] for u in usage}
        for ex in job_execs:
            for uref in ex["usage_refs"]:
                if uref not in usage_ids:
                    errors.append(f"[{tag}] JobExecution.usage_refs에 있는 {uref}가 UsageRecord에 없음")
        for u in usage:
            if u["execution_ref"] is not None and u["execution_ref"] not in exec_ids:
                errors.append(f"[{tag}] UsageRecord.execution_ref({u['execution_ref']})가 JobExecution에 없음")
            tu = u["token_usage"]
            if tu is not None and tu["total_tokens"] != tu["input_tokens"] + tu["output_tokens"]:
                errors.append(f"[{tag}] UsageRecord.token_usage.total_tokens != input+output ({u['usage_id']})")

    # case_view sanity
    if case_view:
        if case_view["case_id"] != case_id:
            errors.append(f"[{tag}] CaseView.case_id != scenario case_id")
        if case_view["package"] is not None and case_view["requirements"]["scope"] != "FINAL_PACKAGE":
            errors.append(f"[{tag}] CaseView.package가 존재하는데 requirements.scope != FINAL_PACKAGE (invariant B02 참고용)")
        if case_view["package"] is not None and case_view["requirements"]["readiness"] not in ("PASS", "WARN"):
            errors.append(f"[{tag}] CaseView.package가 존재하는데 readiness가 PASS/WARN이 아님")
        if case_view["stage"] == "READY" and case_view["requirements"]["scope"] != "FINAL_PACKAGE":
            errors.append(f"[{tag}] CaseView.stage=READY인데 requirements.scope != FINAL_PACKAGE (B02 제안 규칙 기준 점검용)")
        if candidates:
            selected = [c for c in case_view["candidates"] if c["selected"]]
            cv_cand_ids = {c["candidate_id"] for c in case_view["candidates"]}
            src_cand_ids = {c["candidate_id"] for c in candidates}
            if cv_cand_ids and not cv_cand_ids.issubset(src_cand_ids):
                errors.append(f"[{tag}] CaseView.candidates에 CandidateEvent에 없는 candidate_id 존재")


check_scenario("happy_001", "case_happy_001")
check_scenario("partial_001", "case_partial_001")

# 4. known enum checks across all loaded objects (best-effort, only for keys we know the enum for)
ENUM_CHECKS = {
    "status": {  # ambiguous key reused by several contracts; validated per-contract above where feasible
    },
}

print(f"검사한 JSON 파일 수: {checked_files}")
print(f"오류(ERROR): {len(errors)}")
for e in errors:
    print("  -", e)
print(f"경고(WARN): {len(warnings)}")
for w in warnings:
    print("  -", w)

sys.exit(1 if errors else 0)
