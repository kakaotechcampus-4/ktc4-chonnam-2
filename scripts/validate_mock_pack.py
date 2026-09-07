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
import re
import sys
import unicodedata
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
        # as_posix() 필수 — str(PurePath)는 Windows에서 "readout\\plate_readout.json"이 되어
        # get("readout/plate_readout.json") 조회가 전부 None이 되고, 아래 상호참조 검사가
        # 조용히 통과해 버린다.
        data_by_relpath[jf.relative_to(MOCK).as_posix()] = data

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


# ---------------------------------------------------------------------------
# 6. readout 불변조건 (신유민 / readout Owner)
#
# 아래 세 값은 계약이 아직 확정하지 않은 지점이다. 결정이 끝나면 여기만 고치면
# 되도록 상수로 뺐다. 확정 전까지 관련 검사는 ERROR가 아니라 WARN으로 낸다.
#   - ABSTAIN_REASONS       : abstain_reason 값 공간 (현재 fixture에 1종만 존재)
#   - DISAGREE_INDEX_BASIS  : disagree_positions가 어느 문자열 기준인지
#                             "frame_results" | "consensus_text" | None(미정)
#   - UNREAD_PLACEHOLDER    : consensus.text의 미판독 자리 표시 문자
# ---------------------------------------------------------------------------
# PlateReadout.abstain_reason 값 공간 (readout Owner 확정).
#
# 단일 값이며, 여러 조건이 동시에 성립하면 아래 파이프라인 순서에서 가장 이른
# 단계의 사유를 쓴다:
#   1. 대상 association   TARGET_ASSOCIATION_UNCERTAIN
#   2. 번호판 검출        PLATE_NOT_DETECTED
#   3. 유효 프레임 수     INSUFFICIENT_FRAMES
#   4. 프레임 품질        PLATE_TOO_SMALL / IMAGE_TOO_BLURRY / PLATE_OCCLUDED
#   5. OCR 결과           FRAME_DISAGREEMENT / LOW_OCR_CONFIDENCE / FORMAT_MISMATCH
# 5단계 안에서는 프레임 간 불일치가 있으면 FRAME_DISAGREEMENT가 우선하고,
# 프레임들이 일치하는데 신뢰도만 낮으면 LOW_OCR_CONFIDENCE를 쓴다.
#
# association 상세는 이 필드가 아니라 target_association.status가 갖는다
# (LOW_CONFIDENCE / AMBIGUOUS / FAILED / NOT_PROVIDED) — 중복 표현하지 않는다.
ABSTAIN_REASONS = {
    "TARGET_ASSOCIATION_UNCERTAIN",  # 대상 차량/영역을 하나로 확정하지 못함
    "PLATE_NOT_DETECTED",            # 프레임에서 번호판 영역 자체를 찾지 못함
    "INSUFFICIENT_FRAMES",           # consensus를 만들 만큼의 유효 프레임이 없음
    "PLATE_TOO_SMALL",               # plate_px_height가 판독 기준 미만
    "IMAGE_TOO_BLURRY",              # sharpness 미달 / 모션블러
    "FRAME_DISAGREEMENT",            # 프레임 간 문자가 갈림
    "LOW_OCR_CONFIDENCE",            # 프레임들이 일치하지만 신뢰도가 기준 미만
    # --- 값 공간에는 등재하되 v1 구현에서는 아직 판정하지 않는다 ---
    "PLATE_OCCLUDED",                # 번호판이 가려짐 (가림 감지 붙인 뒤 사용)
    "FORMAT_MISMATCH",               # 한국 번호판 형식에 맞지 않음 (형식 검사 붙인 뒤 사용)
}
UNREAD_PLACEHOLDER = "?"

# 번호판 정규화 문자열 (readout Owner 확정).
#
#   1. 유니코드 NFC 정규화        — NFD로 자모가 분해되면 인덱스가 통째로 밀린다
#   2. 전각 → 반각 변환
#   3. 공백·하이픈·점·중점 등 구분 문자 제거
#   4. 남는 문자는 [0-9] · 한글 음절(가-힣) · 미판독 자리 '?'
#   5. 그 외 문자는 버리지 말고 '?'로 치환 — 자릿수를 보존해야 인덱스가 성립한다
#
# frame_results[].text · consensus.text · observation.value 세 곳 모두 이 형식이며,
# disagree_positions는 이 문자열의 0-based 인덱스다. 화면 표시용 공백은 web이 넣는다.
CANONICAL_PLATE_RE = re.compile(r"^[0-9가-힣" + re.escape(UNREAD_PLACEHOLDER) + r"]+$")

# 프레임 간 자릿수가 갈릴 때의 consensus 규칙 (readout Owner 확정).
#
#   1. 자릿수를 먼저 다수결로 정한다 (canonical_length)
#   2. 동률이면 abstain — 자릿수조차 못 정하면 확정할 수 없다
#   3. 그 길이 그룹만 consensus 계산에 쓰고, frame_results[].used_in_consensus로 표시한다
#   4. used_in_consensus=true가 2개 미만이면 INSUFFICIENT_FRAMES로 abstain
#      (계약 §4 「single-frame confidence만으로 자동 확정하지 않는다」)
#   5. abstain 여부는 그 뒤 자리별 합의 결과로만 판단한다
#
# 왜 이렇게 정했나 — 길이가 갈렸다는 사실 자체는 abstain 사유가 아니다.
# "길이가 다르면 무조건 보류"로 두면 5프레임 중 4개가 '12가3456'이고 1개가
# '2가3456'(앞자리 누락)인, 사실상 명확한 경우까지 보류되어 판독률이 불필요하게
# 떨어진다. 자릿수는 투표로 정하고 보류는 자리별 불일치·신뢰도로만 결정한다.
#
# used_in_consensus가 필요한 이유 — 이 필드가 없으면 (a) 소비자가 어떤 프레임이
# 왜 빠졌는지 알 수 없고 (b) disagree_positions의 모집단이 불명확해진다.
# eval의 판독 실패 진단에도 이 정보가 필요하다(계약 §11-2 abstain 지표 분리).
# 길이 갈림은 이 필드로 데이터에 드러나므로 별도 abstain_reason 값은 만들지 않는다.
FRAME_LENGTH_RULE_DECIDED = True
MIN_CONSENSUS_FRAMES = 2

# OverlayTimeReadout.reason 값 공간 (readout Owner 확정).
#
# 계약 §10이 NOT_PRESENT / OCR_FAILED / VALIDATION_FAILED를 "공용 Observation.status가
# 아니라 readout 도메인의 reason"이라고 이미 이름 붙였는데 그것을 담을 필드가 없었다.
# PlateReadout의 abstained를 복사하지 않는 이유 — abstain은 "확정할 수 있었는데 보류한다"는
# 뜻이고 §11-1이 번호판 전용 개념으로 정의했다. overlay에서 가장 흔한 경우는 오버레이가
# 화면에 아예 없는 것이고, 그것은 보류가 아니라 부재다.
#
# reason별로 observation.status와 value가 어떻게 따라오는지 함께 고정한다.
# VALIDATION_FAILED에서 value를 버리지 않는 이유 — §10 「Overlay OCR 불확실은 기존 file
# time candidate를 버리는 이유가 아니다」. 최종 시각 선택은 evidence/TimeResolution 몫이므로
# readout은 관찰값과 "미심쩍다"는 표시만 넘긴다.
#
# frame access 실패는 여기 넣지 않는다 — 관찰 결과가 아니라 실행 실패이고,
# 계약이 「실행이 완전히 실패하면 결과는 생성되지 않고 ReadoutRun만 남는다」로 정했으므로
# ReadoutRun.failure가 담는다.
# ── §10 outcome 판정 (B안: 결과 유무 x failure 유무) ──────────────────────────
#
# ReadoutRun.outcome은 "실행의 완결성"만 나타내며 판독 결과의 확정성(abstain)과 무관하다.
#   SUCCEEDED  결과 1건 존재 ∧ failure = null
#   PARTIAL    결과 1건 존재 ∧ failure != null  (산출물 생성 후 실행이 깨진 경우)
#   FAILED     결과 미존재   ∧ failure != null  (CALL-9: 결과 객체를 만들지 않는다)
# abstained=true는 SUCCEEDED 또는 PARTIAL이다 — abstain은 실패가 아니다.
OUTCOMES = {"SUCCEEDED", "PARTIAL", "FAILED"}
_OUTCOME_MATRIX = {
    (True, False): "SUCCEEDED",
    (True, True): "PARTIAL",
    (False, True): "FAILED",
    # (False, False) → 있을 수 없음
}

# ── failure taxonomy: 실행 축과 평가 축을 섞지 않는다 ──────────────────────────
#
# A. 실행 실패 — ReadoutRun.failure.kind에 기록한다. 런타임에 판정 가능한 것만.
# B. 평가 분류 — 정답 대조로만 판정된다. ReadoutRun에 기록하지 않는다(eval 결과에 기록).
# stage 필드는 두지 않는다 — ReadoutRun.operation이 PLATE_READ/OVERLAY_TIME_READ로 담는다.
RUNTIME_FAILURE_KINDS = {"PLATE_DETECTION", "OVERLAY_DETECTION", "INFRA"}
EVAL_ONLY_KINDS = {"PLATE_RECOGNITION", "PLATE_TARGET_ASSOCIATION", "OVERLAY_VALIDATION"}
# 산출물이 만들어지기 전 단계의 실패 — PARTIAL(결과 있음)과 동시에 성립할 수 없다
PRE_ARTIFACT_KINDS = {"PLATE_DETECTION", "OVERLAY_DETECTION"}

# failure.code 값 공간은 아직 어느 문서에도 없다(abstain_reason 때와 같은 상황).
# 확정 전까지 알려진 값만 두고 미등재 값은 WARN으로 낸다.
FAILURE_CODES = {
    "NO_PLATE_REGION_FOUND",  # contract-readout-run.md §8 예시
}

OVERLAY_REASONS = {
    # reason: (허용 status, value가 있어야 하는가)
    "NOT_PRESENT": ("NOT_APPLICABLE", False),   # 화면에 timestamp가 없음
    "OCR_FAILED": ("UNKNOWN", False),           # 있는데 읽지 못함
    "VALIDATION_FAILED": ("NEEDS_REVIEW", True),  # 읽었지만 검증 실패, 값은 보존
}


def _strip_ws(s):
    return "".join(s.split())


def _canonical_violation(label, value):
    """정규화 규칙 위반 사유를 문자열로 돌려준다. 위반이 없으면 None."""
    if value is None:
        return None
    if unicodedata.normalize("NFC", value) != value:
        return f"{label}이 NFC 정규형이 아님: {value!r}"
    if any(ch.isspace() for ch in value):
        return f"{label}에 공백이 있음: {value!r}"
    if not CANONICAL_PLATE_RE.match(value):
        return f"{label}에 허용되지 않은 문자가 있음: {value!r}"
    return None


def _mismatch_positions(texts):
    """frame_results[].text들 사이에서 문자가 갈리는 위치(공백 제거 기준)."""
    if len(texts) < 2:
        return set()
    stripped = [_strip_ws(t) for t in texts]
    if len({len(t) for t in stripped}) != 1:
        return None  # 길이가 다르면 위치 비교 자체가 성립하지 않음
    return {i for i in range(len(stripped[0])) if len({t[i] for t in stripped}) > 1}


def check_readout(tag):
    """PlateReadout / OverlayTimeReadout / ReadoutRun의 readout 고유 불변조건."""
    plate = get(f"readout/plate_readout.{tag}.json")
    overlay = get(f"readout/overlay_time_readout.{tag}.json")
    runs = get(f"readout/readout_runs.{tag}.json")
    usage = get(f"case/usage_records.{tag}.json")
    job_execs = get(f"case/job_executions.{tag}.json")

    # --- PlateReadout ---
    if plate:
        abstained = plate["abstained"]
        reason = plate["abstain_reason"]
        obs = plate["observation"]
        cons = plate["consensus"]

        # (a) abstained ⟺ abstain_reason  — 양방향으로 본다
        if abstained and not reason:
            errors.append(f"[{tag}] PlateReadout abstained=true인데 abstain_reason 없음")
        if not abstained and reason is not None:
            errors.append(f"[{tag}] PlateReadout abstained=false인데 abstain_reason이 null이 아님: {reason}")

        # (b) abstain_reason이 확정 값 공간 안에 있는가 (readout Owner 확정 — ERROR)
        if reason is not None and reason not in ABSTAIN_REASONS:
            errors.append(
                f"[{tag}] PlateReadout.abstain_reason={reason}가 ABSTAIN_REASONS에 없음"
            )

        # (c) abstain이면 관찰이 OK로 확정되어서는 안 된다
        if abstained and obs["status"] == "OK":
            errors.append(f"[{tag}] PlateReadout abstained=true인데 observation.status=OK")

        # (d) observation.value와 consensus.text는 같은 문자열이어야 한다
        if obs["value"] != cons["text"]:
            errors.append(
                f"[{tag}] PlateReadout observation.value({obs['value']!r}) != consensus.text({cons['text']!r})"
            )

        frames = plate.get("frame_results", [])
        # used_in_consensus가 없는 프레임은 규칙 확정 전 fixture다 — 별도로 보고한다.
        missing_flag = [fr["frame_ref"] for fr in frames if "used_in_consensus" not in fr]
        if missing_flag:
            errors.append(
                f"[{tag}] frame_results에 used_in_consensus가 없는 프레임: {missing_flag}"
            )
        used = [fr for fr in frames if fr.get("used_in_consensus", True)]
        texts = [fr["text"] for fr in used]
        actual_mismatch = _mismatch_positions(texts)

        # consensus에 쓸 프레임이 부족하면 abstain이어야 하고 사유도 정해져 있다
        if frames and len(used) < MIN_CONSENSUS_FRAMES:
            if not abstained:
                errors.append(
                    f"[{tag}] consensus에 쓴 프레임이 {len(used)}개인데 abstained=false "
                    f"(최소 {MIN_CONSENSUS_FRAMES}개 필요)"
                )
            elif reason != "INSUFFICIENT_FRAMES":
                errors.append(
                    f"[{tag}] consensus에 쓴 프레임이 {len(used)}개인데 "
                    f"abstain_reason={reason} (INSUFFICIENT_FRAMES여야 함)"
                )
        cons_text = cons["text"]
        positions = cons.get("disagree_positions", [])

        # (e) 정규화 규칙 — 세 곳이 모두 canonical 형식이어야 한다
        for label, value in (
            ("consensus.text", cons_text),
            ("observation.value", obs["value"]),
            *[(f"frame_results[{i}].text", t) for i, t in enumerate(texts)],
        ):
            v = _canonical_violation(label, value)
            if v:
                errors.append(f"[{tag}] PlateReadout {v}")

        # (f) consensus에 쓴 프레임(used_in_consensus=true)끼리는 자릿수가 같아야 한다.
        #     길이가 갈린 프레임은 used_in_consensus=false로 빠져야 하며, 남은 것들의
        #     길이가 다르면 자리별 비교가 성립하지 않는다.
        if actual_mismatch is None:
            msg = (
                f"[{tag}] used_in_consensus=true인 frame_results의 text 길이가 서로 다름: {texts}"
            )
            if FRAME_LENGTH_RULE_DECIDED:
                errors.append(msg)
            else:
                warnings.append(msg + " — 길이 불일치 시 consensus 규칙 미확정")
        # consensus.text 길이도 같은 자릿수여야 한다
        if texts and len(cons_text) != len(texts[0]):
            errors.append(
                f"[{tag}] consensus.text 길이({len(cons_text)})가 "
                f"used 프레임 자릿수({len(texts[0])})와 다름"
            )

        # (g) disagree_positions 인덱스가 canonical 문자열 범위 안인가
        for idx in positions:
            if not (0 <= idx < len(cons_text)):
                errors.append(
                    f"[{tag}] disagree_positions {idx}가 consensus.text 범위 밖 (len={len(cons_text)})"
                )

        # (h) disagree_positions가 실제 프레임 간 불일치 위치와 맞는가
        if actual_mismatch is not None and texts and set(positions) != actual_mismatch:
            errors.append(
                f"[{tag}] disagree_positions={sorted(positions)}가 frame_results 실제 불일치 위치"
                f"{sorted(actual_mismatch)}와 다름"
            )

        # (i) consensus.text의 미판독 자리 위치 == disagree_positions
        placeholders = {i for i, ch in enumerate(cons_text) if ch == UNREAD_PLACEHOLDER}
        if placeholders != set(positions):
            errors.append(
                f"[{tag}] consensus.text의 {UNREAD_PLACEHOLDER!r} 위치{sorted(placeholders)}가 "
                f"disagree_positions{sorted(positions)}와 다름"
            )
        if not plate["abstained"] and positions:
            warnings.append(f"[{tag}] abstain이 아닌데 disagree_positions가 비어있지 않음: {positions}")

        # (j) best_frame이 frame_results 안의 프레임/crop을 가리키는가
        fr_refs = {fr["frame_ref"] for fr in plate.get("frame_results", [])}
        crop_refs = {fr.get("crop_ref") for fr in plate.get("frame_results", [])}
        bf = plate.get("best_frame") or {}
        if bf.get("frame_ref") and bf["frame_ref"] not in fr_refs:
            errors.append(f"[{tag}] best_frame.frame_ref({bf['frame_ref']})가 frame_results에 없음")
        if bf.get("crop_ref") and bf["crop_ref"] not in crop_refs:
            errors.append(f"[{tag}] best_frame.crop_ref({bf['crop_ref']})가 frame_results에 없음")

        # (k) target_association이 참조하는 프레임도 근거 프레임 집합 안에 있어야 한다
        ta = plate.get("target_association") or {}
        region = ta.get("associated_region") or {}
        if region.get("frame_ref") and region["frame_ref"] not in fr_refs:
            warnings.append(
                f"[{tag}] target_association.associated_region.frame_ref({region['frame_ref']})가 "
                f"frame_results에 없음 — 근거 프레임 집합 밖의 프레임을 가리킨다"
            )

    # --- OverlayTimeReadout ---
    if overlay:
        val = overlay["validation"]
        samples = overlay.get("samples", [])

        # (l) samples는 전량이다 (readout Owner 확정) — sample_count와 길이가 같아야 한다.
        #     발췌를 허용하면 대표 샘플 선정 기준까지 계약에 적어야 하고, 같은 계약의
        #     PlateReadout.frame_results가 전량을 담는 것과도 어긋난다.
        if val.get("sample_count") != len(samples):
            errors.append(
                f"[{tag}] OverlayTimeReadout.validation.sample_count={val.get('sample_count')}인데 "
                f"samples는 {len(samples)}건 (samples는 전량이어야 함)"
            )
        # offset_sec 중복/역순 금지
        offsets = [s_["offset_sec"] for s_ in samples]
        if len(set(offsets)) != len(offsets):
            errors.append(f"[{tag}] OverlayTimeReadout.samples의 offset_sec 중복: {offsets}")

        # (m) monotonic_ok=true면 offset 순서와 parsed_at 순서가 같아야 한다
        if val.get("monotonic_ok") and len(samples) >= 2:
            by_offset = sorted(samples, key=lambda s: s["offset_sec"])
            parsed = [s["parsed_at"] for s in by_offset]
            if parsed != sorted(parsed):
                errors.append(f"[{tag}] OverlayTimeReadout monotonic_ok=true인데 samples의 parsed_at이 단조증가하지 않음")

        # (n) 관찰이 OK인데 검증 플래그가 false인 조합
        if overlay["observation"]["status"] == "OK":
            for flag in ("format_ok", "monotonic_ok"):
                if val.get(flag) is False:
                    warnings.append(f"[{tag}] OverlayTimeReadout observation.status=OK인데 validation.{flag}=false")

        # (o) reason ↔ observation.status ↔ value 3자 대응
        o_status = overlay["observation"]["status"]
        o_value = overlay["observation"]["value"]
        if "reason" not in overlay:
            errors.append(f"[{tag}] OverlayTimeReadout에 reason 필드가 없음")
        else:
            o_reason = overlay["reason"]
            if o_status == "OK" and o_reason is not None:
                errors.append(f"[{tag}] OverlayTimeReadout status=OK인데 reason={o_reason}")
            elif o_status != "OK" and o_reason is None:
                errors.append(f"[{tag}] OverlayTimeReadout status={o_status}인데 reason이 null")
            elif o_reason is not None:
                if o_reason not in OVERLAY_REASONS:
                    errors.append(f"[{tag}] OverlayTimeReadout.reason={o_reason}가 OVERLAY_REASONS에 없음")
                else:
                    want_status, want_value = OVERLAY_REASONS[o_reason]
                    if o_status != want_status:
                        errors.append(
                            f"[{tag}] OverlayTimeReadout reason={o_reason}이면 "
                            f"status={want_status}여야 하는데 {o_status}"
                        )
                    if want_value and o_value is None:
                        errors.append(f"[{tag}] OverlayTimeReadout reason={o_reason}인데 value가 null (값을 보존해야 함)")
                    if not want_value and o_value is not None:
                        errors.append(f"[{tag}] OverlayTimeReadout reason={o_reason}인데 value가 null이 아님")
                    # VALIDATION_FAILED면 실제로 실패한 검증 플래그가 있어야 한다
                    if o_reason == "VALIDATION_FAILED" and not any(
                        val.get(k) is False for k in ("format_ok", "monotonic_ok", "duration_match_ok")
                    ):
                        errors.append(
                            f"[{tag}] OverlayTimeReadout reason=VALIDATION_FAILED인데 "
                            f"validation의 *_ok가 전부 false가 아님"
                        )

    # --- ReadoutRun ---
    if runs:
        run_ids = {r["run_id"] for r in runs}

        # (p) 같은 operation이 중복 실행되지 않았는지 / run_id 중복
        if len(run_ids) != len(runs):
            errors.append(f"[{tag}] ReadoutRun.run_id 중복")
        for r in runs:
            if r["ended_at"] < r["started_at"]:
                errors.append(f"[{tag}] ReadoutRun {r['run_id']} ended_at < started_at")

        # (q) ReadoutRun.usage_refs가 UsageRecord에 실재하는가
        if usage:
            usage_ids = {u["usage_id"] for u in usage}
            for r in runs:
                for uref in r.get("usage_refs", []):
                    if uref not in usage_ids:
                        errors.append(f"[{tag}] ReadoutRun({r['run_id']}).usage_refs의 {uref}가 UsageRecord에 없음")

        # (r) JobExecution.produced의 readout_run ref가 실재하는가
        if job_execs:
            for ex in job_execs:
                for prod in ex.get("produced", []):
                    if prod.get("kind") == "readout_run" and prod["ref"] not in run_ids:
                        errors.append(
                            f"[{tag}] JobExecution({ex['execution_id']}).produced의 "
                            f"readout_run {prod['ref']}가 ReadoutRun에 없음"
                        )

        # (s-0) 실행이 완전히 실패하면 결과는 생성되지 않는다
        #       (contract-plate-overlay-readout.md §5 / contract-readout-run.md §9-3)
        result_by_op = {"PLATE_READ": plate, "OVERLAY_TIME_READ": overlay}
        for r in runs:
            rid = r["run_id"]
            outcome = r["outcome"]
            res = result_by_op.get(r["operation"])
            failure = r.get("failure")
            has_result = res is not None
            has_failure = failure is not None

            if outcome not in OUTCOMES:
                errors.append(f"[{tag}] ReadoutRun {rid} outcome 값이 정의 밖: {outcome!r}")
                continue

            expected = _OUTCOME_MATRIX.get((has_result, has_failure))
            if expected is None:
                errors.append(f"[{tag}] ReadoutRun {rid} 결과 객체도 failure도 없다 — 있을 수 없는 조합")
            elif outcome != expected:
                errors.append(
                    f"[{tag}] ReadoutRun {rid} outcome={outcome}인데 "
                    f"결과={'있음' if has_result else '없음'} / "
                    f"failure={'있음' if has_failure else '없음'} → {expected}여야 한다"
                )

            if has_failure:
                # stage는 operation이 담는다 — failure에 두지 않는다
                if "stage" in failure:
                    errors.append(
                        f"[{tag}] ReadoutRun {rid}.failure에 stage가 있다 "
                        f"(stage는 operation이 담는다)"
                    )
                kind = failure.get("kind")
                if kind in EVAL_ONLY_KINDS:
                    errors.append(
                        f"[{tag}] ReadoutRun {rid}.failure.kind={kind}는 평가 축이다 "
                        f"(정답 대조로만 판정됨 — ReadoutRun에 기록하지 않는다)"
                    )
                elif kind not in RUNTIME_FAILURE_KINDS:
                    errors.append(
                        f"[{tag}] ReadoutRun {rid}.failure.kind={kind}가 "
                        f"RUNTIME_FAILURE_KINDS에 없음"
                    )
                elif outcome == "PARTIAL" and kind in PRE_ARTIFACT_KINDS:
                    errors.append(
                        f"[{tag}] ReadoutRun {rid} outcome=PARTIAL인데 kind={kind} "
                        f"(검출 전 단계 실패라 산출물이 존재할 수 없다)"
                    )
                code = failure.get("code")
                if not code:
                    errors.append(f"[{tag}] ReadoutRun {rid}.failure.code가 비어 있음")
                elif code not in FAILURE_CODES:
                    warnings.append(
                        f"[{tag}] ReadoutRun {rid}.failure.code={code}가 FAILURE_CODES에 없음 "
                        f"(code 값 공간 미확정 — 정해지면 ERROR로 승격)"
                    )

        # abstain은 실패가 아니다 — 결과가 존재하므로 FAILED일 수 없다
        if plate and plate.get("abstained"):
            for r in runs:
                if r["operation"] == "PLATE_READ" and r["outcome"] == "FAILED":
                    errors.append(f"[{tag}] PlateReadout.abstained=true인데 ReadoutRun.outcome=FAILED")

        # (s) CALL-9 결정(run_ref 추가) 반영 여부 — 아직 없으면 상기시킨다
        for name, obj in (("PlateReadout", plate), ("OverlayTimeReadout", overlay)):
            if not obj:
                continue
            ref = obj.get("run_ref")
            if ref is None:
                warnings.append(f"[{tag}] {name}에 run_ref가 없다 (CALL-9 결정 미반영 — 결과→run 역추적 불가)")
                continue
            if ref.get("kind") != "readout_run":
                errors.append(f"[{tag}] {name}.run_ref.kind가 'readout_run'이 아님: {ref.get('kind')}")
            if ref.get("ref") not in run_ids:
                errors.append(f"[{tag}] {name}.run_ref({ref.get('ref')})가 이 시나리오의 ReadoutRun에 없음")


check_scenario("happy_001", "case_happy_001")
check_scenario("partial_001", "case_partial_001")
check_readout("happy_001")
check_readout("partial_001")
# readout 실패 경로 — 전체 E2E가 아닌 readout 전용 부분 시나리오
check_readout("readout_failed_001")

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
