"""#167 — `READY`는 FINAL `PASS`/`WARN` + ReportPackage가 실제로 있을 때만.

real E2E 경로(`scripts/dump_real_video_caseview.py`)가 evidence·Package를 만들기 **전에**
`case.mark_ready()`를 불러서, Package가 막힌 결과와 `NOT_ASSEMBLED`(evidence 없음)까지
`stage=READY`로 나왔다. CaseView 계약: `READY` = `PACKAGE_READY` 파생 gate 성립 시점
(#171 C 결정). Package 전 결과의 화면은 #168·#171이 정하고, case는 앞 단계에 머문다.
"""
from __future__ import annotations

from typing import Any

import pytest

from daesingo.case import service
from daesingo.case.domain import Candidate, CaseAggregate


class _SnapshotAdapter:
    """`fetch_case_view_inputs()`가 읽는 4개 getter만 가진 스냅샷."""

    def __init__(
        self,
        *,
        evidence_record: dict[str, Any] | None,
        final_readiness: str | None,
        report_package: dict[str, Any] | None,
    ) -> None:
        self._evidence_record = evidence_record
        self._final = None if final_readiness is None else {"readiness": final_readiness, "checks": []}
        self._package = report_package

    def get_evidence_record(self) -> dict[str, Any] | None:
        return self._evidence_record

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None:
        return self._final if scope == "FINAL_PACKAGE" else None

    def get_report_package(self) -> dict[str, Any] | None:
        return self._package


_EVIDENCE = {"record_ref": {"kind": "evidence_record", "ref": "er_test_001"}}
_PACKAGE = {"package_ref": {"kind": "report_package", "ref": "pkg_test_001"}}


def _case_in_evidence_review() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_ready_gate", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [
            Candidate(
                candidate_id="cand_ready_gate",
                at=None,
                at_provenance="recording.timeline_relative_only",
                observed="테스트 후보",
                thumb_ref=None,
            )
        ]
    )
    case.select_candidate("cand_ready_gate")
    return case


@pytest.mark.parametrize("readiness", ["PASS", "WARN"])
def test_ready_when_final_passes_and_package_exists(readiness: str) -> None:
    case = _case_in_evidence_review()
    adapter = _SnapshotAdapter(evidence_record=_EVIDENCE, final_readiness=readiness, report_package=_PACKAGE)

    assert service.mark_ready_if_package_ready(case, adapter) is True
    assert case.stage == "READY"


def test_package_blocked_observed_result_stays_in_evidence_review() -> None:
    """Positive + Package blocked(예: 상황 응답 전 D2-c) — evidence는 있고 Package는 없다."""
    case = _case_in_evidence_review()
    rev = case.case_rev
    adapter = _SnapshotAdapter(evidence_record=_EVIDENCE, final_readiness="UNKNOWN", report_package=None)

    assert service.mark_ready_if_package_ready(case, adapter) is False
    assert case.stage == "EVIDENCE_REVIEW"
    assert case.case_rev == rev


def test_not_assembled_result_stays_in_evidence_review() -> None:
    """NOT_OBSERVED → NOT_ASSEMBLED — evidence·요건·Package 전부 없다."""
    case = _case_in_evidence_review()
    adapter = _SnapshotAdapter(evidence_record=None, final_readiness=None, report_package=None)

    assert service.mark_ready_if_package_ready(case, adapter) is False
    assert case.stage == "EVIDENCE_REVIEW"


def test_package_without_passing_final_report_is_not_ready() -> None:
    """ReportPackage는 ready-only라 FINAL이 PASS/WARN이 아니면 원래 생기지 않는다 — 어긋난
    스냅샷이 오더라도 READY로 올리지 않는다."""
    case = _case_in_evidence_review()
    adapter = _SnapshotAdapter(evidence_record=_EVIDENCE, final_readiness="FAIL", report_package=_PACKAGE)

    assert service.mark_ready_if_package_ready(case, adapter) is False
    assert case.stage == "EVIDENCE_REVIEW"
