"""Case 애그리게잇 — 5-state 상태 기계 + selection_rev 내부 저장.

근거:
  - 상태 기계: `docs/architecture/module-architecture.md` §4-모듈5 ②
  - selection_rev 단일 현재값 저장(별도 이력 테이블 없음):
    `docs/modules/case/decisions/case-selection-revision-persistence.md` (2026-09-13)
  - CaseView에는 절대 selection_rev를 노출하지 않는다(위 결정 그대로) — `view.py` 참고.

⚠️ 1차 구현 범위: 전진 전이 + happy path에서 실제로 쓰이는 최소한의 역행 전이만 구현했다.
`TIME_HINT_EDIT`/major `TIMELINE_REBASE` 등 나머지 역행 조건은 §11(1차 완료 제외 범위)에
따라 이번 라운드에는 만들지 않는다 — `docs/modules/case/checklists/phase1-completion-checklist.md`
§3-B 참고.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

STAGES = (
    "INTAKE",
    "SEARCHING",
    "CANDIDATE_REVIEW",
    "EVIDENCE_REVIEW",
    "READY",
)

# 전진 전이만 1차로 구현한다. 역행 전이는 §11 제외 범위.
_FORWARD_EDGES: dict[str, str] = {
    "INTAKE": "SEARCHING",
    "SEARCHING": "CANDIDATE_REVIEW",
    "CANDIDATE_REVIEW": "EVIDENCE_REVIEW",
    "EVIDENCE_REVIEW": "READY",
}


class InvalidTransition(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class Candidate:
    candidate_id: str
    at: str | None
    at_provenance: str | None
    observed: str
    thumb_ref: str | None
    selected: bool = False
    timeline_revision: int = 1
    stale_revision: bool = False
    stale_revision_label_key: str | None = None
    situation_confirmation: str = "NOT_ASKED"


@dataclass
class CaseAggregate:
    """case가 소유하는 내부 상태. `CaseView`는 이 상태 + 다른 모듈 산출물의 projection이다
    (module-architecture.md §4-모듈5 ⑥) — 이 클래스 자체를 밖으로 노출하지 않는다.
    """

    case_id: str
    case_rev: int = 1
    stage: str = "INTAKE"
    user_reviewed: bool = False
    hints: dict[str, Any] = field(default_factory=dict)
    manifest_summary: dict[str, Any] = field(default_factory=dict)

    # selection_rev — 단일 현재값. 이력 테이블 없음(2026-09-13 결정). CaseView 비노출.
    selection_rev: int = 0

    candidates: list[Candidate] = field(default_factory=list)
    job_records: list[dict[str, Any]] = field(default_factory=list)
    correction_records: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def intake(cls, case_id: str, hints: dict[str, Any], manifest_summary: dict[str, Any]) -> "CaseAggregate":
        return cls(case_id=case_id, stage="INTAKE", hints=dict(hints), manifest_summary=dict(manifest_summary))

    def _advance(self, expected_from: str, to: str, *, bump_case_rev: bool = True) -> None:
        if self.stage != expected_from:
            raise InvalidTransition(f"{self.stage} -> {to} (expected from {expected_from})")
        if _FORWARD_EDGES.get(self.stage) != to:
            raise InvalidTransition(f"{self.stage} -> {to} 는 등록된 전진 전이가 아니다")
        self.stage = to
        if bump_case_rev:
            self.case_rev += 1

    def start_search(self) -> None:
        # scenario_happy_001의 case_views[0](stage=SEARCHING)이 case_rev:1 그대로인 것과
        # job_h001_search(COARSE_SEARCH)의 case_rev:1을 근거로, INTAKE→SEARCHING은
        # case_rev를 올리지 않는다 — "요청 시점 케이스 리비전"은 아직 바뀔 내용이 없다.
        self._advance("INTAKE", "SEARCHING", bump_case_rev=False)

    def receive_candidates(self, candidates: list[Candidate]) -> None:
        """빈 배열(candidates=[])은 실패가 아니다 — `scenario_empty_001` 원칙.
        이 구현은 happy path만 다루므로 후보가 있는 경로만 CANDIDATE_REVIEW로 전진시킨다.
        빈 배열 처리(비차단 INFO notice로 재검색 유도)는 §11 제외 범위."""
        self.candidates = list(candidates)
        if self.candidates:
            self._advance("SEARCHING", "CANDIDATE_REVIEW")

    def select_candidate(self, candidate_id: str) -> None:
        """후보 선택은 case 소유(ownership.md §6) — evidence는 참조만 하고 복사해 갖지 않는다.
        selection_rev는 case_rev와 함께 증가하되 서로 다른 카운터로 유지한다(2026-09-13 결정)."""
        match = next((c for c in self.candidates if c.candidate_id == candidate_id), None)
        if match is None:
            raise InvalidTransition(f"알 수 없는 candidate_id: {candidate_id}")
        for c in self.candidates:
            c.selected = c.candidate_id == candidate_id
        self.selection_rev += 1
        self._advance("CANDIDATE_REVIEW", "EVIDENCE_REVIEW")

    def mark_ready(self) -> None:
        self._advance("EVIDENCE_REVIEW", "READY")

    def next_job_id(self, kind: str) -> str:
        """case가 발주하는 모든 JobRecord는 **항상 새 job_id**를 받는다.
        같은 job_id + attempt 증가는 자동 인프라 재시도(STALE)뿐이고, 그건 case가 아니라
        common/runtime이 하는 일이다(module-architecture.md §4-모듈5 ④) — 그래서 case
        코드에는 "기존 job_id 재사용" 분기가 아예 존재하지 않는다."""
        return f"job_{self.case_id}_{kind.lower()}_{uuid.uuid4().hex[:8]}"

    def record_job(self, job_record: dict[str, Any]) -> None:
        self.job_records.append(job_record)
