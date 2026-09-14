"""Case 애그리게잇 — 5-state 상태 기계 + selection_rev 내부 저장.

근거:
  - 상태 기계: `docs/architecture/module-architecture.md` §4-모듈5 ②
  - selection_rev 단일 현재값 저장(별도 이력 테이블 없음):
    `docs/modules/case/decisions/case-selection-revision-persistence.md` (2026-09-13)
  - CaseView에는 절대 selection_rev를 노출하지 않는다(위 결정 그대로) — `view.py` 참고.

⚠️ 역행 전이 구현 범위(2026-09-14 갱신): `module-architecture.md` §4-모듈5 ②는 "`TIME_HINT_EDIT`,
major `TIMELINE_REBASE`, candidate 변경 등에 의해 뒤 단계에서 앞 단계로 돌아갈 수 있다"고만
적어뒀지만, `docs/modules/case/doc-research/부분 재실행 정책 표 초안 v1...md`(연구 메모, 9개
`CorrectionRecord.kind` 각각의 stage 전이/재실행/폐기/보존을 표로 완성해둠)가 이 한 줄을
구체화한다. 그 표 기준으로 실제 구현 가능한 것과 막힌 것을 나눴다:
  - `TIME_HINT_EDIT` — 표 1행 그대로 `SEARCHING`으로 역행(`regress_to_searching()`). case가
    소유한 순수 workflow state라 case 혼자 구현 가능.
  - `OTHER_CANDIDATE`("candidate 변경") — 표 2행을 보면 실제로는 역행이 **아니다**: 뒤 단계
    (`EVIDENCE_REVIEW`)에 "제자리"로 머문다(`reselect_candidate()`). §4-모듈5 ②의 "candidate
    변경"이라는 표현이 역행을 뜻하는 것처럼 읽히지만, 더 구체적인 이 연구 메모가 실제로는
    아니라고 정정한다 — 문서 간 불일치이며 원문(module-architecture.md)을 고치는 건 이 세션
    범위 밖이라 그대로 뒀다(2026-09-14 체크리스트 §11 노트 참고).
  - major `TIMELINE_REBASE` — 표 맨 아래 자체가 "신유민(web)이랑 화면 흐름 확인 안 하면 나
    혼자 추천하기 어려운 지점"이라고 명시한다. 접합부 문제라 이번에도 구현하지 않는다.
  - 나머지 6개 kind(`PLATE_MANUAL_EDIT`/`PLATE_REREAD`/`SPAN_ADJUST`/`REPORT_TYPE_CHANGE`/
    `EVENT_TIME_MANUAL`/`SITUATION_CHANGE`)는 표에서도 stage 전이가 "제자리"라 별도 domain
    메서드가 필요 없다 — `correction.apply_correction()` 하나로 이미 충분하다.
  - 실제 fixture로 검증된 게 아니라 이 연구 메모(초안, `decisions/`로 승격되지 않음)를 근거로
    case가 스스로 설계해 구현한 것이므로, 표시(`[x]`)에도 그 구분을 그대로 남긴다
    (`phase1-completion-checklist.md` §3-B).
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

    def regress_to_searching(self) -> None:
        """`TIME_HINT_EDIT` 역행 전이 — `CANDIDATE_REVIEW`/`EVIDENCE_REVIEW`/`READY` 중 어디서든
        `SEARCHING`으로 되돌아간다(`부분 재실행 정책 표 초안` 1행: "다시 도는 것=1차 탐색,
        폐기되는 것=후보·2차확인·선택·증거, 절대 안 건드리는 것=시간축·원본"). case가 들고
        있는 것 중 "폐기" 대상은 `candidates`뿐이다(2차 확인/증거는 evidence 쪽 데이터라 case가
        아예 갖고 있지 않다 — 애초에 지울 게 없다). `selection_rev`는 건드리지 않는다(과거
        correction_records가 스냅샷해 둔 값과의 정합성을 깨지 않기 위해 — 단조 증가만 유지).

        `case_rev`는 여기서 올리지 않는다 — 이 메서드를 부르는 `correction.edit_time_hint()`가
        `apply_correction()`으로 이미 한 번 올린다(한 사용자 요청 = 한 case_rev 증가, §3-E).
        """
        if self.stage not in ("CANDIDATE_REVIEW", "EVIDENCE_REVIEW", "READY"):
            raise InvalidTransition(f"{self.stage}에서는 SEARCHING으로 역행할 수 없다")
        self.stage = "SEARCHING"
        self.candidates = []

    def reselect_candidate(self, candidate_id: str) -> None:
        """`OTHER_CANDIDATE` — 이미 선택을 마친 뒤(`EVIDENCE_REVIEW`) 사용자가 "다른 후보가
        맞다"고 정정하는 경로. `부분 재실행 정책 표 초안` 2행: stage는 "제자리"(그대로
        `EVIDENCE_REVIEW`)로 머물고, `selected` 플래그만 새 candidate로 옮긴다. 최초 선택
        (`select_candidate()`, `CANDIDATE_REVIEW`→`EVIDENCE_REVIEW` 전이 포함)과는 다른
        메서드다 — 여긴 전이가 없다. `selection_rev`는 새 선택 context를 나타내려고 올린다
        (`case-selection-revision-persistence.md`와 동일 원칙: candidate가 바뀌면 selection_rev도
        바뀐다). `case_rev`는 여기서 올리지 않는다 — `correction.reselect_candidate()`가
        `apply_correction()`으로 이미 올린다."""
        if self.stage != "EVIDENCE_REVIEW":
            raise InvalidTransition(f"{self.stage}에서는 OTHER_CANDIDATE 재선택을 쓸 수 없다(EVIDENCE_REVIEW 전용)")
        match = next((c for c in self.candidates if c.candidate_id == candidate_id), None)
        if match is None:
            raise InvalidTransition(f"알 수 없는 candidate_id: {candidate_id}")
        for c in self.candidates:
            c.selected = c.candidate_id == candidate_id
        self.selection_rev += 1

    def next_job_id(self, kind: str) -> str:
        """case가 발주하는 모든 JobRecord는 **항상 새 job_id**를 받는다.
        같은 job_id + attempt 증가는 자동 인프라 재시도(STALE)뿐이고, 그건 case가 아니라
        common/runtime이 하는 일이다(module-architecture.md §4-모듈5 ④) — 그래서 case
        코드에는 "기존 job_id 재사용" 분기가 아예 존재하지 않는다."""
        return f"job_{self.case_id}_{kind.lower()}_{uuid.uuid4().hex[:8]}"

    def record_job(self, job_record: dict[str, Any]) -> None:
        self.job_records.append(job_record)
