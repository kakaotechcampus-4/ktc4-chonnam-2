"""관찰 job 발주 순서 — 8-6 2단계 · RT-10(b), `docs/modules/case/decisions/incident-clip-observation-input.md`.

선택된 후보 → `FINE_VERIFY` → (`NOT_OBSERVED`가 아니면) `INCIDENT_CLIP_BUILD` → `PLATE_READ` ·
`OVERLAY_TIME_READ`(같은 clip). 각 발주는 입력(후보 · 세대 · span · clip ref)을 case state에 고정하고, `scope_ref`는
그 세대 `COARSE_SEARCH` JobRecord의 것을 싣는다(§4-1). aggregate 수준 함수만 둔다 — load · save와 append된
JobRecord 반환은 호출자(reflection)가 한다.

## 여기 없는 것

- capability 호출 · clip 본체 보관. handler(Runtime)와 recording 몫이다.
- Coarse T2의 rank=1 자동 선택 · 첫 Fine 발주 배선(§4-5). 선택된 case는 CaseView 조립에 adapter가 필요해, composition에
  `StoredObservationAdapter`(`adapter_factory`)를 꽂는 단계와 함께 연다 — 그 전에 열면 API · Worker가
  `AdapterNotAttached`로 멈춘다. `issue_fine_for_selected`가 그때 부를 함수다.
- 다른 후보 선택 뒤 관찰 재사용(§4-6). 후보별 clip 결과 위치와 함께 다음 단계에서 붙인다.
"""
from __future__ import annotations

from typing import Any

from daesingo.case import jobs
from daesingo.case.analysis_start import fingerprint
from daesingo.case.domain import CaseAggregate


def current_generation_job_id(case: CaseAggregate) -> str | None:
    """현재 후보 목록 세대 표식 — `CaseAggregate.current_generation_job_id()`."""
    return case.current_generation_job_id()


def _issue(case: CaseAggregate, kind: str, observation_input: dict[str, Any]) -> dict[str, Any]:
    generation = next(r for r in case.job_records if r["job_id"] == observation_input["generation_job_id"])
    return jobs.issue_job(
        case,
        kind,
        scope_ref=generation["scope_ref"],
        input_fingerprint=fingerprint({"kind": kind, "observation_input": observation_input}),
        observation_input=observation_input,
    )


def issue_fine_for_selected(case: CaseAggregate) -> dict[str, Any] | None:
    """현재 세대에서 선택된 후보의 `FINE_VERIFY`를 발주한다. 선택이 없거나 후보에 span이 없으면(이전 형식) 내지 않는다."""
    selected = next((c for c in case.candidates if c.selected), None)
    generation = current_generation_job_id(case)
    if selected is None or selected.span is None or generation is None:
        return None
    return _issue(
        case,
        "FINE_VERIFY",
        {"candidate_id": selected.candidate_id, "generation_job_id": generation, "span": dict(selected.span)},
    )


def is_current(case: CaseAggregate, observation_input: dict[str, Any]) -> bool:
    """입력의 후보가 현재 선택 후보이고 세대가 현재 세대인가 — 후속 발주 조건(§4-4)."""
    selected = next((c.candidate_id for c in case.candidates if c.selected), None)
    return (
        observation_input["candidate_id"] == selected
        and observation_input["generation_job_id"] == current_generation_job_id(case)
    )


def follow_fine(case: CaseAggregate, fine_job_id: str, visual_evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    """성공한 Fine 결과 뒤 `INCIDENT_CLIP_BUILD`를 발주한다(§4-3). `NOT_OBSERVED` · `VisualEvidence` 없음 · 입력 없이
    발주된 Fine · 현재 선택 · 세대가 아닌 결과면 내지 않는다."""
    source = case.observation_inputs.get(fine_job_id)
    verification = None if visual_evidence is None else visual_evidence.get("verification")
    if source is None or verification is None or verification == "NOT_OBSERVED" or not is_current(case, source):
        return None
    return _issue(case, "INCIDENT_CLIP_BUILD", {**source, "fine_job_id": fine_job_id})


def follow_clip(case: CaseAggregate, clip_job_id: str, incident_clip_ref: str) -> list[dict[str, Any]]:
    """준비된 clip 뒤 `PLATE_READ` · `OVERLAY_TIME_READ`를 같은 `incident_clip_ref`로 함께 발주한다(§4-4)."""
    source = case.observation_inputs.get(clip_job_id)
    if source is None or not is_current(case, source):
        return []
    readout_input = {
        "candidate_id": source["candidate_id"],
        "generation_job_id": source["generation_job_id"],
        "incident_clip_ref": incident_clip_ref,
    }
    return [_issue(case, kind, readout_input) for kind in ("PLATE_READ", "OVERLAY_TIME_READ")]
