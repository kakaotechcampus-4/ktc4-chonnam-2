"""저장된 관찰 결과로 CaseView 입력을 만든다 — 8-6 2단계, `docs/modules/case/decisions/observation-storage.md`.

지금은 관찰 객체 고르기(§4-4)만 있다. `StoredObservationAdapter`(read port · `ProducedReader` · recording 공개 조회 →
`assemble_evidence_bundle`)는 IncidentClip을 만드는 handler와 그 결과 위치가 정해진 뒤 붙인다(§6, #297 2-(b)).

## 여기 없는 것

- 객체의 뜻 · 모양. `payload`는 각 모듈 계약 객체 그대로이고, 여기서는 `candidate_id`만 본다.
- 실행 상태 · 실패 notice. 객체가 없는 실행(`FAILED`)은 view가 read port로 계산한다(`jobexecution-read-port.md`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from daesingo.case.domain import CaseAggregate


@dataclass(frozen=True)
class StoredObservation:
    """결과 저장소에서 읽은 관찰 객체 하나 — 그것을 만든 job과 kind를 함께 든다."""

    job_id: str
    kind: str
    payload: dict[str, Any]


def select_current_observations(case: CaseAggregate, observations: list[StoredObservation]) -> dict[str, StoredObservation]:
    """kind → CaseView에 쓸 관찰 객체(§4-4). 선택 후보가 없으면 빈 dict다.

    - 현재 후보 목록 세대의 job만 본다: 가장 나중 `REFLECTED` `COARSE_SEARCH`보다 뒤에 append된 JobRecord.
      재탐색 뒤 같은 `candidate_id`가 다시 나와도 이전 세대 관찰은 쓰지 않는다. 실패로 정산된 탐색도 `REFLECTED`지만
      그때는 후보 목록이 비어 있어(`SEARCHING`) 고를 것이 없다.
    - 그 안에서 객체의 `candidate_id`가 선택 후보와 같은 것만, kind마다 가장 나중 job의 것을 쓴다. 같은 세대 안
      A→B→A면 A의 관찰을 다시 쓰고, 이전 후보의 늦은 결과는 투영되지 않는다(6.6순위 조건 2).

    이 case가 발주하지 않은 job의 객체는 배선 오류(`ValueError`)다."""
    order = {r["job_id"]: i for i, r in enumerate(case.job_records)}
    for observation in observations:
        if observation.job_id not in order:
            raise ValueError(f"이 case가 발주하지 않은 job_id의 관찰: {observation.job_id!r}")
    selected = next((c.candidate_id for c in case.candidates if c.selected), None)
    if selected is None:
        return {}
    searches = [
        order[r["job_id"]]
        for r in case.job_records
        if r["kind"] == "COARSE_SEARCH" and case.settled_jobs.get(r["job_id"]) == "REFLECTED"
    ]
    generation_start = max(searches, default=-1)
    current: dict[str, StoredObservation] = {}
    for observation in sorted(observations, key=lambda o: order[o.job_id]):
        if order[observation.job_id] > generation_start and observation.payload.get("candidate_id") == selected:
            current[observation.kind] = observation
    return current
