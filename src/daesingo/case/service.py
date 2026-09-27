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
from daesingo.case.store import CaseStore
from daesingo.case.view import build_case_view


def receive_search_candidates(case: CaseAggregate, adapter: ModuleAdapter) -> list[Candidate]:
    """`adapter.get_candidate_events()`를 읽어 `Candidate`로 변환하고
    `case.receive_candidates()`에 반영한다. 반환값은 호출자가 (예: 로그·검증용으로)
    그대로 참고할 수 있게 넘겨준다 — `case` 상태 반영은 이 함수 안에서 이미 끝나 있다.

    `at`는 여기서 채우지 않는다 — 절대시각 확정은 readout/evidence 쪽 책임이라 `search`의
    `CandidateEvent`에는 없는 값이다. `at_provenance`는 `at is None`인 이 상태를 위해 이미
    등록된 case 소유 enum 값(`recording.timeline_relative_only`,
    `docs/modules/case/decisions/candidate-at-provenance-label-key.md`)을 쓴다 — `None`을
    두면 계약(`caseView.ts`/contract 문서 §7)이 기대하는 non-null과 어긋난다(이슈 #104).
    """
    raw_candidates = adapter.get_candidate_events()
    candidates = [
        Candidate(
            candidate_id=c["candidate_id"],
            at=None,
            at_provenance="recording.timeline_relative_only",
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


def build_view_from_adapter(
    case: CaseAggregate,
    adapter: ModuleAdapter,
    *,
    running_jobs: list[dict[str, Any]] | None = None,
    notices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`fetch_case_view_inputs()` + `build_case_view()`를 이어붙인 편의 함수 —
    스모크 테스트에서 매번 반복되던 4줄을 한 호출로 줄인다. `case`(상태)와 `adapter`
    (downstream 스냅샷 소스)만 있으면 `CaseView`를 조립할 수 있다는 것이 이 함수가
    보이는 계약이다.

    `running_jobs`/`notices`는 adapter가 아니라 호출자가 직접 안다(어떤 job을 방금
    발주했는지는 이 함수가 추측하지 않는다 — 모듈 docstring 「여기 없는 것」과 동일한
    이유). 그대로 `build_case_view()`에 전달만 한다.
    """
    snapshot = fetch_case_view_inputs(adapter)
    return build_case_view(
        case,
        evidence_record=snapshot.evidence_record,
        requirement_report_evidence=snapshot.requirement_report_evidence,
        requirement_report_package=snapshot.requirement_report_package,
        report_package=snapshot.report_package,
        running_jobs=running_jobs,
        notices=notices,
    )


def get_view(
    case_id: str,
    *,
    store: CaseStore,
    running_jobs: list[dict[str, Any]] | None = None,
    notices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`web → case.get_view() → CaseView`(`module-architecture.md` §5-1 ⑪, §6 모듈6
    ③)의 실제 진입점. 지금까지 스모크 테스트 안에만 있던 "case_id로 저장된 case를
    찾아서 CaseView를 조립한다"는 마지막 연결을 뽑아냈다.

    `store`를 명시적으로 받는다 — 프로세스 전체가 공유하는 숨은 전역 상태를 두지
    않는다. 여러 요청에 걸쳐 같은 store를 재사용하는 것(예: FastAPI app state)은
    호출자의 책임이다 — 그 배선 자체는 W5/W6 요청 문서가 이번 범위 밖으로 뺀
    "완성된 FastAPI/Worker 배선"에 해당한다.
    """
    case = store.get_case(case_id)
    adapter = store.get_adapter(case_id)
    return build_view_from_adapter(case, adapter, running_jobs=running_jobs, notices=notices)
