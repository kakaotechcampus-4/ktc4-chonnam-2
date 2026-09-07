"""search fixture stub의 smoke / contract self-check.

무거운 프레임워크 없이(팀 관례 — scripts/validate_mock_pack.py 참고) assert로 확인한다.
실행: `python tests/test_search_stub.py` → 통과 시 마지막에 "PASS" 출력.

검증 대상은 `docs/modules/search/first-integration-checklist.md`의 계약 불변조건과
1차 Merge 완료 기준 5개다.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
SEARCH_MOCK = REPO_ROOT / "data" / "mock" / "search"

from daesingo.search import search_candidates, verify_visual  # noqa: E402

BASELINE_EVENT_TYPES = {
    "SIGNAL",
    "CENTER_LINE_CROSSING",
    "SOLID_LINE_LANE_CHANGE",
    "MOTORCYCLE_HELMET_NON_USE",
}


def _load(name):
    return json.loads((SEARCH_MOCK / name).read_text(encoding="utf-8"))


def _check_input_is_analysis_scope(scope):
    # 기준2: Consumer가 주는 입력이 Canonical AnalysisScope 형식이다.
    assert isinstance(scope["scope_id"], str) and scope["scope_id"]
    assert isinstance(scope["time_ranges"], list) and len(scope["time_ranges"]) >= 1
    assert isinstance(scope["target_event_types"], list) and len(scope["target_event_types"]) >= 1
    assert "hint" in scope and "budget" in scope


RUN_REQUIRED = ("run_id", "operation", "input_ref", "implementation", "outcome",
                "started_at", "completed_at", "issues", "usage_refs",
                "usage_summary", "contract_version")
CAND_REQUIRED = ("candidate_id", "run_id", "span", "rank")


def _check_analysis_run_contract(result):
    run = result["analysis_run"]
    candidates = result["candidates"]
    for k in RUN_REQUIRED:                       # C: AnalysisRun 필수 필드
        assert k in run, f"AnalysisRun에 {k} 없음"
    assert run["operation"] in {"CANDIDATE_SEARCH", "VISUAL_VERIFY"}  # C: operation enum
    assert datetime.fromisoformat(run["completed_at"]) >= datetime.fromisoformat(run["started_at"])
    assert run["contract_version"] == "analysis-run-candidate-event/v1"
    assert run["outcome"] in {"SUCCEEDED", "PARTIAL", "FAILED"}
    tok = run["usage_summary"]["token_usage"]
    if tok is not None:
        assert tok["total_tokens"] == tok["input_tokens"] + tok["output_tokens"]
    # CandidateEvent 불변조건
    ranks = []
    for c in candidates:
        for k in CAND_REQUIRED:                   # C: CandidateEvent 필수 필드
            assert k in c, f"CandidateEvent에 {k} 없음"
        assert c["run_id"] == run["run_id"]       # candidate ↔ run 정합
        s = c["span"]
        assert s["start_ms"] >= 0
        assert s["start_ms"] < s["end_ms"]
        assert s["start_ms"] <= s["representative_ms"] <= s["end_ms"]
        if c.get("event_type_hint") is not None:  # C: hint는 있으면 4종 enum
            assert c["event_type_hint"] in BASELINE_EVENT_TYPES
        ranks.append(c["rank"])
    if ranks:
        assert sorted(ranks) == list(range(1, len(ranks) + 1))  # 1부터 무중복


VE_REQUIRED = ("schema_version", "visual_evidence_id", "run_id", "input_ref",
               "verification", "primitives", "temporal_facts", "uncertainties", "legal_status")


def _check_visual_evidence_contract(ve):
    for k in VE_REQUIRED:                        # C: VisualEvidence 필수 필드
        assert k in ve, f"VisualEvidence에 {k} 없음"
    assert ve["run_id"]
    assert ve["verification"] in {"OBSERVED", "NOT_OBSERVED", "UNCERTAIN"}
    if ve["verification"] == "OBSERVED":
        assert ve["visual_event_type"] in BASELINE_EVENT_TYPES
    else:
        assert ve["visual_event_type"] is None
    assert ve["legal_status"] is None  # 항상 null
    for key in ("primitives", "temporal_facts", "uncertainties"):
        assert isinstance(ve[key], list)
    assert "confidence" not in ve  # top-level global confidence 금지


def test_happy():
    scope = _load("analysis_scope.happy_001.json")
    _check_input_is_analysis_scope(scope)

    result = search_candidates(scope)  # smoke
    assert isinstance(result, dict)
    _check_analysis_run_contract(result)
    assert result["analysis_run"]["outcome"] == "SUCCEEDED"
    assert len(result["candidates"]) >= 1

    ve_expected = _load("visual_evidence.happy_001.json")
    ve = verify_visual(ve_expected["input_ref"])  # smoke + round-trip lookup
    _check_visual_evidence_contract(ve)
    assert ve["visual_event_type"] == "SOLID_LINE_LANE_CHANGE"
    assert ve == ve_expected


def test_partial():
    scope = _load("analysis_scope.partial_001.json")
    _check_input_is_analysis_scope(scope)

    result = search_candidates(scope)
    _check_analysis_run_contract(result)
    assert result["analysis_run"]["outcome"] == "PARTIAL"
    assert len(result["analysis_run"]["issues"]) >= 1  # PARTIAL ⇒ issues ≥ 1

    ve_expected = _load("visual_evidence.partial_001.json")
    ve = verify_visual(ve_expected["input_ref"])
    _check_visual_evidence_contract(ve)
    assert ve["target"]["association_status"] == "AMBIGUOUS"


def test_unknown_input_raises():
    try:
        search_candidates({"scope_id": "scope_does_not_exist",
                           "time_ranges": [{"start": "x", "end": "y"}],
                           "target_event_types": ["SIGNAL"], "hint": {}, "budget": {}})
    except ValueError:
        pass
    else:
        raise AssertionError("없는 scope_id는 ValueError로 조기 실패해야 한다")


if __name__ == "__main__":
    test_happy()
    test_partial()
    test_unknown_input_raises()
    print("PASS")
