#!/usr/bin/env python3
"""Builds docs/mock/03_mock_artifact_templates.md by extracting real objects
out of the actually-generated fixtures under data/mock/, so every JSON
example in that doc is guaranteed to be byte-identical to what's on disk
(never hand-diverged)."""
import json
from pathlib import Path

ROOT = Path("/tmp/repo")
MOCK = ROOT / "data" / "mock"
OUT = ROOT / "docs" / "mock" / "03_mock_artifact_templates.md"


def load(rel):
    return json.loads((MOCK / rel).read_text(encoding="utf-8"))


def block(title, contract, source_note, obj):
    return (
        f"### {title}\n\n"
        f"**Contract**: `{contract}`  \n"
        f"**출처**: {source_note} (실제 파일에서 그대로 발췌)\n\n"
        "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```\n"
    )


sections = []

sections.append("# 03. Mock Artifact Templates\n\n"
                 "아래 모든 JSON 예시는 손으로 다시 쓴 것이 아니라 `data/mock/` 아래 실제로 생성된 fixture 파일에서 "
                 "그대로 발췌했다(`scripts/build_artifact_templates_doc.py`가 기계적으로 추출). 문서와 실제 fixture가 "
                 "갈라질 수 없다.\n")

# recording
rec = load("recording/scenario_happy_001.json")
sections.append("## recording\n")
sections.append(block("SourceAsset (정상)", "source-asset-media-stream/v1",
                       "recording/scenario_happy_001.json → source_assets[0]", rec["source_assets"][0]))
sections.append(block("RecordingTimeline (USABLE)", "recording-timeline/v1",
                       "recording/scenario_happy_001.json → recording_timelines[0]", rec["recording_timelines"][0]))
sections.append(block("IncidentClip", "analysis-source-derived/v1",
                       "recording/scenario_happy_001.json → incident_clips[0]", rec["incident_clips"][0]))
sections.append(block("DeletionReport (PARTIAL)", "analysis-source-derived/v1",
                       "recording/scenario_happy_001.json → deletion_reports[0]", rec["deletion_reports"][0]))
rec_u = load("recording/scenario_unknown_abstain_partial_001.json")
sections.append(block("TimeSourceCandidate ×2 (충돌하는 두 시각 후보)", "recording-timeline/v1",
                       "recording/scenario_unknown_abstain_partial_001.json → time_source_candidates",
                       rec_u["time_source_candidates"]))

# search
se = load("search/scenario_happy_001.json")
sections.append("## search\n")
sections.append(block("AnalysisRun + CandidateEvent (정상, 후보 1건)", "analysis-run-candidate-event/v1.1",
                       "search/scenario_happy_001.json → analysis_run_candidate_events[0]",
                       se["analysis_run_candidate_events"][0]))
sections.append(block("VisualEvidence", "visual-evidence/v1.0",
                       "search/scenario_happy_001.json → visual_evidences[0]", se["visual_evidences"][0]))
se_e = load("search/scenario_empty_001.json")
sections.append(block("AnalysisRun — 결과 없음(candidates=[], outcome=SUCCEEDED)", "analysis-run-candidate-event/v1.1",
                       "search/scenario_empty_001.json → analysis_run_candidate_events[0]",
                       se_e["analysis_run_candidate_events"][0]))

# readout
ro = load("readout/scenario_happy_001.json")
sections.append("## readout\n")
sections.append(block("PlateReadout (정상, abstain 없음)", "plate-readout/v1.2",
                       "readout/scenario_happy_001.json → plate_readouts[0]", ro["plate_readouts"][0]))
sections.append(block("OverlayTimeReadout (정상)", "overlay-time-readout/v1.2",
                       "readout/scenario_happy_001.json → overlay_time_readouts[0]", ro["overlay_time_readouts"][0]))
ro_u = load("readout/scenario_unknown_abstain_partial_001.json")
sections.append(block("PlateReadout — ABSTAIN (target_association=AMBIGUOUS)", "plate-readout/v1.2",
                       "readout/scenario_unknown_abstain_partial_001.json → plate_readouts[0]",
                       ro_u["plate_readouts"][0]))
sections.append(block("ReadoutRun — 완전 실패 (결과 객체 자체가 생성되지 않음)", "readout-run/v1",
                       "readout/scenario_unknown_abstain_partial_001.json → readout_runs[1]",
                       ro_u["readout_runs"][1]))

# evidence
ev = load("evidence/scenario_happy_001.json")
sections.append("## evidence\n")
sections.append(block("TimeResolution (status=OK, 검증된 Overlay)", "time-resolution/v1",
                       "evidence/scenario_happy_001.json → time_resolutions[0]", ev["time_resolutions"][0]))
sections.append(block("EvidenceRecord (모든 값 confirmed)", "evidence-record/v1.2",
                       "evidence/scenario_happy_001.json → evidence_records[0]", ev["evidence_records"][0]))
sections.append(block("RequirementReport (scope=FINAL_PACKAGE, overall=PASS)", "requirement-report/v1",
                       "evidence/scenario_happy_001.json → requirement_reports[1]", ev["requirement_reports"][1]))
sections.append(block("ReportPackage", "report-package/v1",
                       "evidence/scenario_happy_001.json → report_packages[0]", ev["report_packages"][0]))

ev_u = load("evidence/scenario_unknown_abstain_partial_001.json")
sections.append(block("TimeResolution — 값 충돌 보존 (conflict.exists=true, status=NEEDS_REVIEW)", "time-resolution/v1",
                       "evidence/scenario_unknown_abstain_partial_001.json → time_resolutions[0]",
                       ev_u["time_resolutions"][0]))
sections.append(block("EvidenceRecord — vehicle_number 필드 자체 부재(UNKNOWN)", "evidence-record/v1.2",
                       "evidence/scenario_unknown_abstain_partial_001.json → evidence_records[0]",
                       ev_u["evidence_records"][0]))
sections.append(block("EvidenceNeeds — PLATE_REREAD 요청", "evidence-needs/v1",
                       "evidence/scenario_unknown_abstain_partial_001.json → evidence_needs[0]",
                       ev_u["evidence_needs"][0]))
sections.append(block("RequirementReport — overall=UNKNOWN", "requirement-report/v1",
                       "evidence/scenario_unknown_abstain_partial_001.json → requirement_reports[0]",
                       ev_u["requirement_reports"][0]))

ev_r = load("evidence/scenario_correction_rerun_001.json")
sections.append(block("TimeResolution v2 — USER_OVERRIDE, supersedes_ref", "time-resolution/v1",
                       "evidence/scenario_correction_rerun_001.json → time_resolutions[1]",
                       ev_r["time_resolutions"][1]))
sections.append(block("EvidenceRecord v2 — supersede, vehicle_number 값 리셋 없이 그대로 유지", "evidence-record/v1.2",
                       "evidence/scenario_correction_rerun_001.json → evidence_records[1]",
                       ev_r["evidence_records"][1]))

# case
ca = load("case/scenario_happy_001.json")
sections.append("## case\n")
sections.append(block("JobRecord (COARSE_SEARCH)", "job-record/v1",
                       "case/scenario_happy_001.json → job_records[0]", ca["job_records"][0]))
sections.append(block("CaseView (stage=READY)", "case-view/v1.2",
                       "case/scenario_happy_001.json → case_views[0]", ca["case_views"][0]))

ca_u = load("case/scenario_unknown_abstain_partial_001.json")
sections.append(block("JobRecord — 재판독 자동 발주 (kind=PLATE_READ, force_rerun=true)", "job-record/v1",
                       "case/scenario_unknown_abstain_partial_001.json → job_records[3]",
                       ca_u["job_records"][3]))
sections.append(block("CaseView — evidence.plate_display info_state=INFO_UNKNOWN, running_jobs 포함", "case-view/v1.2",
                       "case/scenario_unknown_abstain_partial_001.json → case_views[0]",
                       ca_u["case_views"][0]))

# common
co = load("common/scenario_happy_001.json")
sections.append("## common\n")
sections.append(block("JobExecution (SUCCEEDED)", "job-execution/v1",
                       "common/scenario_happy_001.json → job_executions[0]", co["job_executions"][0]))
sections.append(block("UsageRecord (search 호출)", "usage-record/v1.1",
                       "common/scenario_happy_001.json → usage_records[0]", co["usage_records"][0]))
co_u = load("common/scenario_unknown_abstain_partial_001.json")
sections.append(block("JobExecution — QUEUED (재판독 대기 중, ended_at=null)", "job-execution/v1",
                       "common/scenario_unknown_abstain_partial_001.json → job_executions[3]",
                       co_u["job_executions"][3]))

# expected
sections.append("## expected (Eval Harness, provisional — Final Contract 아님)\n")
ef1 = load("expected/eval_fixture_correct_001.json")
ef2 = load("expected/eval_fixture_wrong_001.json")
sections.append(block("Eval fixture — 항상 정답 (metric 계산 검증용)", "(provisional, non-contract)",
                       "expected/eval_fixture_correct_001.json (전체)", ef1))
sections.append(block("Eval fixture — 의도적 오답 (metric이 오류를 잡아내는지 검증용)", "(provisional, non-contract)",
                       "expected/eval_fixture_wrong_001.json (전체)", ef2))

OUT.write_text("\n".join(sections), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
