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
        """빈 배열(candidates=[])은 실패가 아니다 — `scenario_empty_001` 원칙(2026-09-14,
        실제 fixture로 검증: `AnalysisRun.outcome=SUCCEEDED`+`candidates=[]`도 검색 자체는
        성공이므로 `CANDIDATE_REVIEW`로 전진한다). 빈 배열이든 아니든 전진 여부는 같고,
        차이는 이후 단계(선택 가능한 candidate가 없어 evidence 파이프라인이 발주되지 않음)와
        `CaseView.notices[]`(`search.no_candidates`, 비차단 INFO)에서만 갈린다 — notice 자체는
        `build_case_view()` 호출자가 채운다(§11 제외 범위: notice 자동 합성 로직)."""
        self.candidates = list(candidates)
        self._advance("SEARCHING", "CANDIDATE_REVIEW")

    def select_candidate(self, candidate_id: str) -> None:
        """후보 선택은 case 소유(ownership.md §6) — evidence는 참조만 하고 복사해 갖지 않는다.
        selection_rev는 오르지만 case_rev는 오르지 않는다(2026-09-14, `scenario_correction_rerun_001`/
        `scenario_plate_reread_001` fixture로 정정 — 이전엔 이 전이도 case_rev를 올린다고
        잘못 가정했었다). candidate 선택은 "검색 결과를 검토하는" 같은 흐름의 연장이지 그
        자체로 새 요청이 아니라서, case_rev는 다음 실제 요청(재판독 발주·정정 제출 등,
        §3-E)에서 처음 오른다."""
        match = next((c for c in self.candidates if c.candidate_id == candidate_id), None)
        if match is None:
            raise InvalidTransition(f"알 수 없는 candidate_id: {candidate_id}")
        for c in self.candidates:
            c.selected = c.candidate_id == candidate_id
        self.selection_rev += 1
        self._advance("CANDIDATE_REVIEW", "EVIDENCE_REVIEW", bump_case_rev=False)

    def mark_ready(self) -> None:
        self._advance("EVIDENCE_REVIEW", "READY")

    def bump_revision(self) -> None:
        """단계 전이 없이도 `case_rev`가 오르는 경우를 위한 범용 훅.

        `case_rev`는 "요청 시점 케이스 리비전"(§3-E)이지 stage 전이 전용 카운터가 아니다 —
        `scenario_plate_reread_001` fixture로 확인됨: 번호판 재판독으로 `EvidenceRecord`가
        v1→v2로 supersede될 때 stage는 `EVIDENCE_REVIEW`에 그대로 머무는데 `case_rev`는
        3→4로 오른다. `_advance()`와 달리 전이 유효성 검사를 하지 않는 단순 카운터 증가라,
        stage 전이가 아닌 사유로 case_rev를 올려야 하는 지점(증거 supersede 등)에서 직접
        호출한다. `mark_reviewed()`도 내부적으로 이걸 쓴다.
        """
        self.case_rev += 1

    def mark_reviewed(self) -> None:
        """`USER_REVIEWED` 상태 전환 — `CaseView.stage`가 아니라 별도 boolean으로 관리한다
        (`ownership.md` §7-③ 종결 사항). `scenario_happy_001` fixture로 확인됨: rev3(READY,
        `case_rev:3`, `user_reviewed:false`)→rev4(READY, `case_rev:4`, `user_reviewed:true`)로,
        stage는 그대로 READY인데 사용자가 최종 패키지를 확인했다는 새 요청이라 case_rev가
        오른다(이전엔 이 지점을 "package 최초 완성"으로 잘못 추정했었다 — 실제로는 package는
        rev3에서 이미 동일했고 `user_reviewed`만 바뀐다)."""
        self.user_reviewed = True
        self.bump_revision()

    def next_job_id(self, kind: str) -> str:
        """case가 발주하는 모든 JobRecord는 **항상 새 job_id**를 받는다.
        같은 job_id + attempt 증가는 자동 인프라 재시도(STALE)뿐이고, 그건 case가 아니라
        common/runtime이 하는 일이다(module-architecture.md §4-모듈5 ④) — 그래서 case
        코드에는 "기존 job_id 재사용" 분기가 아예 존재하지 않는다."""
        return f"job_{self.case_id}_{kind.lower()}_{uuid.uuid4().hex[:8]}"

    def record_job(self, job_record: dict[str, Any]) -> None:
        self.job_records.append(job_record)
