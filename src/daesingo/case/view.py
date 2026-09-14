"""`CaseView` projection — web의 유일한 read dependency.

case가 이미 갖고 있는 상태(`CaseAggregate`)와 다른 모듈이 만든 Canonical Contract
산출물(어댑터를 통해 읽는다)을 조합해서 `case-view/v1.3` 모양으로 안전하게 내보낸다.
evidence/readout 값을 **복사해서 그대로 소유하지 않는다** — 매번 다시 조립한다
(module-architecture.md §4-모듈5 ⑥). 신고 요건 판정(readiness/checks)이나 번호판 OCR
같은 evidence/readout의 판단 자체는 여기서 재계산하지 않고 그대로 옮겨 담기만 한다.

⚠️ 1차 구현 범위: `scenario_happy_001`(happy path)과 `scenario_unknown_abstain_partial_001`
(WARN Package + 위치 미확보 — 2026-09-14, 이슈 #47/#48 후속으로 §11 제외 범위에서 전체
파리티로 승격) 재현에 필요한 필드를 다룬다. 나머지 5개 시나리오(후보 0개/GPS 없음이 아닌
low confidence/Timestamp conflict 단독/Plate abstain 단독/Timeout·partial result)의 표시
규칙은 `docs/modules/case/checklists/phase1-completion-checklist.md` §11에 따라 아직
다루지 않는다.
"""
from __future__ import annotations

from typing import Any

from daesingo.case.domain import CaseAggregate
from daesingo.case.labels import (
    event_type_label,
    evidence_value_info_state,
    location_representative,
    occurred_at_info_state,
    report_type_label,
)

CONTRACT_VERSION = "case-view/v1.3"

_PROGRESS_STEPS = (
    "file_intake",
    "coarse_search",
    "candidate_review",
    "plate_read",
    "overlay_time_read",
    "evidence_assembly",
    "requirement_check",
    "package_assembly",
)

# report_inputs/report_field_states를 만드는 5개 필드의 정식 순서.
# unconfirmed_fields의 순서는 이 순서를 그대로 따른다(임의로 정렬하지 않는다).
_REPORT_FIELDS = ("safety_report_type", "occurred_at", "location", "vehicle_number", "violation_expression")


def _build_progress(case: CaseAggregate, evidence_record: dict[str, Any] | None, report_package: dict[str, Any] | None) -> list[dict[str, str]]:
    stage = case.stage
    stage_rank = {"INTAKE": 0, "SEARCHING": 1, "CANDIDATE_REVIEW": 2, "EVIDENCE_REVIEW": 3, "READY": 4}[stage]

    def state_for(step_rank: int) -> str:
        if stage_rank > step_rank:
            return "DONE"
        if stage_rank == step_rank:
            return "RUNNING"
        return "PENDING"

    # step_rank: file_intake=0(INTAKE 완료 즉시 DONE), coarse_search=1, candidate_review=2,
    # plate_read/overlay_time_read/evidence_assembly=3(EVIDENCE_REVIEW 진행), requirement_check/
    # package_assembly=3.5(EVIDENCE_REVIEW 안에서도 evidence 이후 단계) — evidence_record/
    # report_package 존재 여부로 더 세분화한다.
    progress = {
        "file_intake": "DONE" if stage_rank >= 0 else "PENDING",
        "coarse_search": state_for(1),
        "candidate_review": state_for(2),
    }
    if stage_rank < 3:
        for step in ("plate_read", "overlay_time_read", "evidence_assembly", "requirement_check", "package_assembly"):
            progress[step] = "PENDING"
    else:
        evidence_done = evidence_record is not None
        package_done = report_package is not None
        for step in ("plate_read", "overlay_time_read", "evidence_assembly"):
            if evidence_done:
                progress[step] = "DONE"
            elif stage_rank == 3:
                progress[step] = "RUNNING"
            else:
                progress[step] = "PENDING"
        for step in ("requirement_check", "package_assembly"):
            if package_done:
                progress[step] = "DONE"
            elif evidence_done and stage_rank == 3:
                progress[step] = "RUNNING"
            else:
                progress[step] = "PENDING"
        if stage_rank == 4:  # READY
            progress = {s: "DONE" for s in _PROGRESS_STEPS}
    return [{"step": s, "state": progress[s]} for s in _PROGRESS_STEPS]


def _build_candidates_view(case: CaseAggregate, evidence_record: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for c in case.candidates:
        at, at_provenance = c.at, c.at_provenance
        situation_confirmation = c.situation_confirmation
        # evidence가 확정되면 occurred_at을 최종 표시값으로 쓴다(1차 구현 단순화 —
        # 정식으로는 TimeResolution이 candidate.at을 직접 채운다. §11 참고).
        if evidence_record is not None and c.selected:
            occurred_at = evidence_record["occurred_at"]
            at = occurred_at["value"]
            at_provenance = occurred_at["source"]["kind"]
            # candidates[].situation_confirmation — B절 §6 필드 정의: EvidenceRecord.situation_response.value가
            # 있으면 그대로 옮기고(CONFIRMED/CORRECTED/USER_UNSURE), 없으면 기존 NOT_ASKED를 유지한다.
            situation_response = evidence_record.get("situation_response")
            if situation_response is not None:
                situation_confirmation = situation_response["value"]
        out.append(
            {
                "candidate_id": c.candidate_id,
                "at": at,
                "at_provenance": at_provenance,
                "observed": c.observed,
                "thumb_ref": c.thumb_ref,
                "selected": c.selected,
                "timeline_revision": c.timeline_revision,
                "stale_revision": c.stale_revision,
                "stale_revision_label_key": c.stale_revision_label_key,
                "situation_confirmation": situation_confirmation,
            }
        )
    return out


def _field_states(evidence_record: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    """B절 §7-(1)/(2)/(3) 파생 규칙 — `report_fields`/`report_field_states`(§10 불변조건 13)와
    `evidence.*_display`가 공유하는 5개 필드(case_type 제외)의 info_state를 여기서 만든다."""
    event = evidence_record["event"]
    occurred_at = evidence_record["occurred_at"]
    vehicle_number = evidence_record["vehicle_number"]
    violation = event["violation_expression"]
    report_type = event["safety_report_type"]
    # ⚠️ location은 EvidenceRecord에 키 자체가 없을 수 있다(예: scenario_unknown_abstain_partial_001의
    # ev_u001 — 위치를 확보하지 못한 사건). 이슈 #48 Q2 조사에서 확인된 실제 결함 — `.get()`으로
    # None-safe하게 처리한다(과거에는 `evidence_record["location"]`이 KeyError를 던졌다).
    location = evidence_record.get("location")
    location_value, location_key = location_representative(location)

    if location_value is None:
        location_info_state = "INFO_UNKNOWN"
    elif location_key == "user_hint":
        # B절 §7-(3) 고정 규칙: 대표값이 user_hint면 info_state는 항상 INFO_NEEDS_REVIEW다
        # (rule (1)의 일반 우선순위를 타지 않는 예외 — user_corrected=true인 fixture에서도
        # INFO_USER_CONFIRMED로 올라가지 않는다. scenario_happy_001로 검증됨).
        location_info_state = "INFO_NEEDS_REVIEW"
    else:
        location_info_state = evidence_value_info_state(
            location_value.get("value"),
            needs_review=location_value.get("needs_review", False),
            user_corrected=location_value.get("user_corrected", False),
            observability=location_value["source"].get("observability"),
        )

    return {
        "vehicle_number": {
            "info_state": evidence_value_info_state(
                vehicle_number["value"],
                needs_review=vehicle_number["needs_review"],
                user_corrected=vehicle_number["user_corrected"],
                observability=vehicle_number["source"].get("observability"),
            ),
            "source_label_key": vehicle_number["source"]["label_key"],
        },
        "occurred_at": {
            "info_state": occurred_at_info_state(occurred_at),
            "source_label_key": occurred_at["source"]["label_key"],
        },
        "location": {
            "info_state": location_info_state,
            "source_label_key": location_value["source"]["label_key"] if location_value is not None else None,
        },
        "violation_expression": {
            "info_state": evidence_value_info_state(
                violation["value"],
                needs_review=violation["needs_review"],
                user_corrected=violation["user_corrected"],
                observability=violation["source"].get("observability"),
            ),
            "source_label_key": violation["source"]["label_key"],
        },
        "safety_report_type": {
            "info_state": evidence_value_info_state(
                report_type["value"],
                needs_review=report_type["needs_review"],
                user_corrected=report_type["user_corrected"],
                observability=report_type["source"].get("observability"),
            ),
            "source_label_key": report_type["source"]["label_key"],
        },
    }


def _build_evidence_view(evidence_record: dict[str, Any], preview_ref: str | None) -> dict[str, Any]:
    event = evidence_record["event"]
    states = _field_states(evidence_record)
    # ⚠️ location 키 자체가 없는 EvidenceRecord가 정상 케이스다(위치 미확보 — 이슈 #48).
    # 아래 location_display 구성도 이에 맞춰 None-safe해야 한다.
    location = evidence_record.get("location")
    location_value, _location_key = location_representative(location)

    case_type = event["visual_event_type"]
    report_type = event["safety_report_type"]
    violation = event["violation_expression"]
    vehicle_number = evidence_record["vehicle_number"]
    occurred_at = evidence_record["occurred_at"]

    case_type_info_state = evidence_value_info_state(
        case_type["value"],
        needs_review=case_type["needs_review"],
        user_corrected=case_type["user_corrected"],
        observability=case_type["source"].get("observability"),
    )
    event_time_needs_review = occurred_at.get("resolution_status") == "NEEDS_REVIEW"
    location_needs_review = location_value.get("needs_review", False) if location_value is not None else False

    # review_needed(object-level) 파생 — B절 §7 "evidence.review_needed 파생 규칙"(2026-09-09,
    # 개정 2026-09-10 이슈 #26 B-web-6): 6개 *_display 각각의 needs_review OR info_state==INFO_NEEDS_REVIEW.
    # reason_code는 원인이 한 필드면 evidence.<field>_needs_review, 둘 이상이면
    # evidence.multiple_fields_need_review(원인이 없으면 null).
    review_fields: dict[str, tuple[bool, str]] = {
        "case_type": (case_type["needs_review"], case_type_info_state),
        "report_type": (report_type["needs_review"], states["safety_report_type"]["info_state"]),
        "violation": (violation["needs_review"], states["violation_expression"]["info_state"]),
        "plate": (vehicle_number["needs_review"], states["vehicle_number"]["info_state"]),
        "event_time": (event_time_needs_review, states["occurred_at"]["info_state"]),
        "location": (location_needs_review, states["location"]["info_state"]),
    }
    triggered = [name for name, (nr, info) in review_fields.items() if nr or info == "INFO_NEEDS_REVIEW"]
    review_needed = bool(triggered)
    if not triggered:
        reason_code = None
    elif len(triggered) == 1:
        reason_code = f"evidence.{triggered[0]}_needs_review"
    else:
        reason_code = "evidence.multiple_fields_need_review"

    return {
        "record_id": evidence_record["record_ref"]["ref"],
        "case_type_display": {
            "code": case_type["value"],
            "label": event_type_label(case_type["value"]),
            "needs_review": case_type["needs_review"],
            "info_state": case_type_info_state,
            "source_label_key": case_type["source"]["label_key"],
        },
        "report_type_display": {
            "code": report_type["value"],
            "label": report_type_label(report_type["value"]),
            "needs_review": report_type["needs_review"],
            "info_state": states["safety_report_type"]["info_state"],
            "source_label_key": report_type["source"]["label_key"],
        },
        "violation_display": {
            "code": None,
            "label": violation["value"],
            "needs_review": violation["needs_review"],
            "info_state": states["violation_expression"]["info_state"],
            "source_label_key": violation["source"]["label_key"],
        },
        "plate_display": {
            "value": vehicle_number["value"],
            "needs_review": vehicle_number["needs_review"],
            "info_state": states["vehicle_number"]["info_state"],
            "source_label_key": vehicle_number["source"]["label_key"],
        },
        "event_time_display": {
            "value": occurred_at["value"],
            # ⚠️ 과거엔 False로 고정돼 있었다 — B절 §7-(2): "event_time_display.needs_review는
            # resolution_status == NEEDS_REVIEW를 그대로 옮긴다."
            "needs_review": event_time_needs_review,
            "info_state": states["occurred_at"]["info_state"],
            "source_label_key": occurred_at["source"]["label_key"],
        },
        "location_display": (
            {
                "value": location_value["value"],
                # ⚠️ 필드 자체의 needs_review는 대표값(location_value)의 원본을 그대로 옮긴다 — "검토 필요"
                # 신호는 info_state(INFO_NEEDS_REVIEW)와 evidence.review_needed(object-level)로 표현된다.
                "needs_review": location_value.get("needs_review", False),
                "info_state": states["location"]["info_state"],
                "source_label_key": location_value["source"]["label_key"],
                # coord/search_keyword는 대표값 후보가 아니라 항상 별도로 내려보낸다(B절 §7-(3)) —
                # 둘 다 optional 키라 location 자체가 있어도 없을 수 있다(.get()으로 방어).
                "coord": (location.get("coord") or {}).get("value") if location else None,
                "search_keyword": (location.get("search_keyword") or {}).get("value") if location else None,
            }
            if location_value is not None
            # ⚠️ 위치 미확보(location 키 없음, 또는 address/place_name/user_hint 전부 없음) — §19
            # 원칙("제품 안에서 완결되지 않는 게 정상")에 따라 실패로 표시하지 않고, "값 자체가
            # 없다"를 그대로 나타낸다. 고칠 수 있는 in-app 액션이 없으므로 needs_review=False.
            else {
                "value": None,
                "needs_review": False,
                "info_state": states["location"]["info_state"],
                "source_label_key": None,
                "coord": None,
                "search_keyword": None,
            }
        ),
        "user_edited": False,
        "preview_ref": preview_ref,
        "review_needed": review_needed,
        "reason_code": reason_code,
    }


def _build_requirements_view(requirement_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if requirement_report is None:
        return None
    return {
        "readiness": requirement_report["overall"],
        "checks": requirement_report["checks"],
    }


def _build_package_view(report_package: dict[str, Any] | None, evidence_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if report_package is None or evidence_record is None:
        return None
    states = _field_states(evidence_record)
    report_inputs = report_package["report_inputs"]
    report_fields = {}
    for field_name in _REPORT_FIELDS:
        value = report_inputs[field_name]
        if field_name == "location":
            # ⚠️ 위치를 확보하지 못한 사건은 report_inputs.location 자체가 null이다
            # (scenario_unknown_abstain_partial_001의 pkg_u001 — 이슈 #48). 예전에는
            # `value["display_text"]`가 TypeError를 던졌다.
            value = value["display_text"] if value is not None else None
        report_fields[field_name] = value
    field_states = {name: states[name] for name in _REPORT_FIELDS}
    unconfirmed = [name for name in _REPORT_FIELDS if field_states[name]["info_state"] != "INFO_SOURCE_VERIFIED"]
    return {
        "package_ref": report_package["package_ref"]["ref"],
        "report_fields": report_fields,
        "report_field_states": field_states,
        "artifact_ref": report_package["assets"]["report_video_ref"]["ref"],
        "capabilities": report_package["handoff"]["supported_actions"],
        "warnings": [],
        "unconfirmed_fields": unconfirmed,
    }


def build_case_view(
    case: CaseAggregate,
    *,
    evidence_record: dict[str, Any] | None = None,
    requirement_report_evidence: dict[str, Any] | None = None,
    requirement_report_package: dict[str, Any] | None = None,
    report_package: dict[str, Any] | None = None,
    running_jobs: list[dict[str, Any]] | None = None,
    notices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = next((c for c in case.candidates if c.selected), None)
    preview_ref = selected.thumb_ref if selected else None

    return {
        "contract": "CaseView",
        "contract_version": CONTRACT_VERSION,
        "case_id": case.case_id,
        "case_rev": case.case_rev,
        "stage": case.stage,
        "user_reviewed": case.user_reviewed,
        "manifest_summary": case.manifest_summary,
        "hints": case.hints,
        "progress": _build_progress(case, evidence_record, report_package),
        "candidates": _build_candidates_view(case, evidence_record),
        "evidence": _build_evidence_view(evidence_record, preview_ref) if evidence_record else None,
        "requirements_evidence": _build_requirements_view(requirement_report_evidence),
        "requirements_package": _build_requirements_view(requirement_report_package),
        "package": _build_package_view(report_package, evidence_record),
        "running_jobs": running_jobs or [],
        "notices": notices or [],
    }
