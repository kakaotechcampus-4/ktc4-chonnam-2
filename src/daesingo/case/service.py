"""orchestration 진입점 — `ModuleAdapter`(Mock 또는 Real)로부터 데이터를 가져와 `case`의
도메인 상태(`CaseAggregate`)에 반영하거나 `CaseView`를 조립하는, 재사용 가능한 실행 코드.

## 왜 필요한가

지금까지 "adapter로 데이터 가져오기 → 도메인 메서드 호출 → 결과 반영"은 시나리오별 스모크
테스트(`tests/test_scenario_*_smoke.py`) 안에서 손으로 짜여 있었다 — 테스트가 곧
orchestration 흐름의 유일한 실행 경로였다. 이 모듈은 그 흐름 중 "adapter 값을 그대로
옮기는" 부분만 재사용 가능한 함수로 뽑아낸다. `RealAdapter`가 모듈별로 채워지면, 이
파일이나 `domain.py`/`jobs.py`/`view.py`는 건드리지 않고 호출하는 쪽에서 어댑터
인스턴스만 `MockFixtureAdapter(...)`에서 `RealAdapter(...)`로 바꾸면 된다.

## 여기 없는 것

- **자동 전체 진행(auto-run)은 없다.** 어떤 job을 언제 발주할지, 언제 재시도·정정을
  받아들일지는 여전히 호출자(테스트, 또는 앞으로 만들어질 실제 worker loop)의 책임이다
  — 시나리오마다 분기가 다르기 때문에(happy/unknown-abstain/infra-failure 등) 이 파일이
  임의로 "다음 단계"를 추측하지 않는다.
- evidence 판정 로직, OCR 판단, 업로드 규정 등 다른 모듈의 정책은 여기서 재구현하지
  않는다 — `adapters.py`와 마찬가지로 "옮기기만" 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from daesingo.case.adapters import ModuleAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view


def receive_search_candidates(case: CaseAggregate, adapter: ModuleAdapter) -> list[Candidate]:
    """`adapter.get_candidate_events()`를 읽어 `Candidate`로 변환하고
    `case.receive_candidates()`에 반영한다. 반환값은 호출자가 (예: 로그·검증용으로)
    그대로 참고할 수 있게 넘겨준다 — `case` 상태 반영은 이 함수 안에서 이미 끝나 있다.

    `at`/`at_provenance`는 여기서 채우지 않는다 — 후보 단계의 시각 확정은 readout/evidence
    쪽 책임이라 `search`의 `CandidateEvent`에는 없는 값이다(스모크 테스트와 동일하게 None).
    """
    raw_candidates = adapter.get_candidate_events()
    candidates = [
        Candidate(
            candidate_id=c["candidate_id"],
            at=None,
            at_provenance=None,
            observed=c["summary"],
            thumb_ref=c["thumbnail_ref"],
        )
        for c in raw_candidates
    ]
    case.receive_candidates(candidates)
    return candidates


@dataclass
class AdapterSnapshot:
    """`CaseView` 조립에 필요한, `CaseAggregate`에는 저장되지 않는 downstream 값들의
    한 시점 스냅샷. evidence/requirements/package는 case 상태로 들고 있지 않고 매번
    adapter에서 새로 읽는다 — 다른 모듈이 같은 case에 대해 값을 갱신했으면 다음
    `fetch_case_view_inputs()` 호출에서 그대로 반영돼야 하기 때문이다.
    """

    evidence_record: dict[str, Any] | None
    requirement_report_evidence: dict[str, Any] | None
    requirement_report_package: dict[str, Any] | None
    report_package: dict[str, Any] | None


def fetch_case_view_inputs(adapter: ModuleAdapter) -> AdapterSnapshot:
    """`build_case_view()`가 요구하는 4개 입력을 adapter에서 한 번에 가져온다."""
    return AdapterSnapshot(
        evidence_record=adapter.get_evidence_record(),
        requirement_report_evidence=adapter.get_requirement_report("EVIDENCE"),
        requirement_report_package=adapter.get_requirement_report("FINAL_PACKAGE"),
        report_package=adapter.get_report_package(),
    )


def build_view_from_adapter(case: CaseAggregate, adapter: ModuleAdapter) -> dict[str, Any]:
    """`fetch_case_view_inputs()` + `build_case_view()`를 이어붙인 편의 함수 —
    스모크 테스트에서 매번 반복되던 4줄을 한 호출로 줄인다. `case`(상태)와 `adapter`
    (downstream 스냅샷 소스)만 있으면 `CaseView`를 조립할 수 있다는 것이 이 함수가
    보이는 계약이다.
    """
    snapshot = fetch_case_view_inputs(adapter)
    return build_case_view(
        case,
        evidence_record=snapshot.evidence_record,
        requirement_report_evidence=snapshot.requirement_report_evidence,
        requirement_report_package=snapshot.requirement_report_package,
        report_package=snapshot.report_package,
    )
