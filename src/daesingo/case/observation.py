"""관찰 job 발주 순서 — 8-6 2단계 · RT-10(b), `docs/modules/case/decisions/incident-clip-observation-input.md`.

선택된 후보 → `FINE_VERIFY` → (`NOT_OBSERVED`가 아니면) `INCIDENT_CLIP_BUILD` → `PLATE_READ` ·
`OVERLAY_TIME_READ`(같은 clip). 각 발주는 입력(후보 · 세대 · span · clip ref)을 case state에 고정하고, `scope_ref`는
그 세대 `COARSE_SEARCH` JobRecord의 것을 싣는다(§4-1). aggregate 수준 함수만 둔다 — load · save와 append된
JobRecord 반환은 호출자(reflection)가 한다. 첫 Fine은 Coarse T2가 rank=1을 자동 선택한 뒤 `issue_fine_for_selected`로
발주한다(§4-5, `reflection._apply_coarse_search`). 다른 후보를 고르면 그 후보 · 현재 세대에서 첫 빠진 단계부터
발주한다(§4-6, `issue_missing_for_selected`) — 끝난 관찰은 T2 때 남긴 `observation_outcomes`로 알아본다.

## 여기 없는 것

- capability 호출 · clip 본체 보관. handler(Runtime)와 recording 몫이다.
"""
from __future__ import annotations

from typing import Any

from daesingo.case import jobs
from daesingo.case.analysis_start import fingerprint
from daesingo.case.domain import CaseAggregate

# 같은 clip으로 함께 발주하는 판독(§4-4).
_READOUT_KINDS = ("PLATE_READ", "OVERLAY_TIME_READ")

# Fine 후보당 실행 상한(초) — `decisions/timeout-fallback.md` 잠정값 표. Fine 입력에 고정하고 handler가 그대로 쓴다
# (#407 결정 (a)). Coarse scope 상한을 이어받지 않는다.
FINE_MAX_LATENCY_SEC = 70


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
        {"candidate_id": selected.candidate_id, "generation_job_id": generation, "span": dict(selected.span),
         "max_latency_sec": FINE_MAX_LATENCY_SEC},
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
    # Fine 상한은 Fine 입력에만 둔다 — clip은 후보 · 세대 · 구간과 그 Fine만 이어받는다.
    clip_input = {k: v for k, v in source.items() if k != "max_latency_sec"}
    return _issue(case, "INCIDENT_CLIP_BUILD", {**clip_input, "fine_job_id": fine_job_id})


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
    return [_issue(case, kind, readout_input) for kind in _READOUT_KINDS]


def record_outcome(case: CaseAggregate, job_id: str, *, status: str, **values: Any) -> None:
    """관찰 job의 T2 결과를 남긴다(§4-6). 입력 없이 발주된 job(동기 · 데모 경로)은 남기지 않는다."""
    if job_id in case.observation_inputs:
        case.observation_outcomes[job_id] = {**case.observation_outcomes.get(job_id, {}), "status": status, **values}


def issue_missing_for_selected(case: CaseAggregate) -> list[dict[str, Any]]:
    """다른 후보 선택 뒤 그 후보 · 현재 세대의 첫 빠진 관찰 단계를 발주한다(§4-6, `reselect-observation-reuse.md` (b)).

    성공한 단계는 다시 내지 않는다 — Fine이 없으면 Fine, Fine만 있으면 clip, clip까지 있으면 빠진 판독만. 실패한 단계는
    빠진 것으로 본다. Fine이 `NOT_OBSERVED`였으면 아무것도 내지 않는다(§4-3). 그 후보의 job을 아직 기다리면 내지 않는다."""
    selected = next((c.candidate_id for c in case.candidates if c.selected), None)
    generation = current_generation_job_id(case)
    if selected is None or generation is None:
        return []
    mine = [
        r for r in case.job_records
        if (source := case.observation_inputs.get(r["job_id"])) is not None
        and source["candidate_id"] == selected
        and source["generation_job_id"] == generation
    ]
    waiting = {r["job_id"] for r in case.waiting_job_records()}
    if any(r["job_id"] in waiting for r in mine):
        return []

    def succeeded(kind: str, **match: Any) -> tuple[str, dict[str, Any]] | None:
        for r in reversed(mine):
            outcome = case.observation_outcomes.get(r["job_id"])
            source = case.observation_inputs[r["job_id"]]
            if (r["kind"] == kind and outcome is not None and outcome["status"] == "SUCCEEDED"
                    and all(source.get(k) == v for k, v in match.items())):
                return r["job_id"], outcome
        return None

    fine = succeeded("FINE_VERIFY")
    # `VisualEvidence` 없이 끝난 Fine은 Fine 실패다(§4-3) — 빠진 단계로 다시 낸다.
    if fine is None or fine[1].get("verification") is None:
        job = issue_fine_for_selected(case)
        return [] if job is None else [job]
    fine_job_id, fine_outcome = fine
    if fine_outcome["verification"] == "NOT_OBSERVED":
        return []
    clip = succeeded("INCIDENT_CLIP_BUILD", fine_job_id=fine_job_id)
    if clip is None:
        job = follow_fine(case, fine_job_id, {"verification": fine_outcome["verification"]})
        return [] if job is None else [job]
    clip_ref = clip[1]["incident_clip_ref"]
    readout_input = {"candidate_id": selected, "generation_job_id": generation, "incident_clip_ref": clip_ref}
    return [_issue(case, kind, readout_input) for kind in _READOUT_KINDS
            if succeeded(kind, incident_clip_ref=clip_ref) is None]
