"""`AnalysisScope` 조립 — case가 유일한 Producer인 경계 계약(`contract-analysis-scope.md`
§2). search에게 "무엇을·언제 범위에서·얼마의 예산으로 분석할지"만 넘기고, case_id/
selection_rev/파일 참조/location 같은 case 내부 상태는 절대 섞지 않는다(§10-1).

⚠️ 1차 구현 범위: `scope_id`/`time_ranges`/`target_event_types`/`budget`은 이 모듈이
스스로 판단해서 만들어내지 않는다 — case 내부 어디에도 아직 "어떤 시간대를, 어떤
이벤트 유형으로, 얼마의 예산으로 검색할지"를 결정하는 로직이 없다(intake 시점 UI
흐름이 아직 §11 제외 범위). 그래서 이 값들은 호출자가 그대로 공급하고, 이 모듈은
§10 불변조건을 검증해서 "계약을 어기는 요청은 애초에 만들지 않는다"(§9 「입력 검증
실패 → case 측에서 요청 자체를 생성하지 않음」)는 책임만 진다.

`hint.vehicle`/`hint.free_text`는 다르다 — `case.hints`(B절 hints 스키마: time/vehicle/
situation/location)에서 직접 파생한다. 5개 시나리오 fixture 교차 확인(2026-09-14):
`hint.vehicle == case.hints["vehicle"]`, `hint.free_text == case.hints["situation"]`
(sanitize 이전 원문 기준) — `scenario_correction_rerun_001`/`scenario_empty_001`/
`scenario_plate_reread_001`/`scenario_unknown_abstain_partial_001`/
`scenario_relative_rebase_001` 5건 전부 정확히 일치, `scenario_happy_001` 1건만
불일치(`hints.situation`="백색 실선 구간에서 차로변경" vs `free_text`="백색 실선
crossing 가능성") — 이건 case의 파생 규칙 문제가 아니라 search 쪽 fixture 자체의
불일치로 보인다(같은 규칙으로 나머지 5건이 전부 맞아떨어지는데 이 1건만 안 맞음).
case 소유가 아닌 fixture라 여기서 고치지 않는다.
"""
from __future__ import annotations

import re
from typing import Any

CONTRACT_VERSION = "1.1.0"

# §7 — v4 baseline enum, 고정.
_TARGET_EVENT_TYPES = frozenset(
    {"SIGNAL", "CENTER_LINE_CROSSING", "SOLID_LINE_LANE_CHANGE", "MOTORCYCLE_HELMET_NON_USE"}
)

# ⚠️ PII sanitize는 이 시점 fixture 어디에도 실제 PII가 든 free_text가 없어 실제
# 계약 정답지로 검증된 적이 없는 placeholder다(§6 "이름·연락처 등 사용자 PII를
# 포함하지 않도록 case가 sanitize"). 휴대폰번호/이메일 등 뻔한 패턴만 보수적으로
# 가린다 — 정식 PII 탐지는 이 모듈의 책임 범위를 넘는다.
_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),  # 휴대폰번호
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # 이메일
)


def _sanitize_free_text(text: str | None) -> str | None:
    if text is None:
        return None
    sanitized = text
    for pattern in _PII_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def _validate_time_ranges(time_ranges: list[dict[str, Any]]) -> None:
    if not time_ranges:
        raise ValueError("time_ranges는 최소 1개 이상이어야 한다(§10-2)")
    kinds = {r.get("kind", "ABSOLUTE") for r in time_ranges}  # kind 부재는 ABSOLUTE로 해석(§7 하위호환)
    if len(kinds) > 1:
        raise ValueError(f"한 scope 안에서 kind를 섞을 수 없다(§10-2): {kinds}")
    kind = next(iter(kinds))
    if kind == "ABSOLUTE":
        for r in time_ranges:
            if r.get("start") is None or r.get("end") is None:
                raise ValueError("kind=ABSOLUTE range는 start/end가 필수다(§6)")
            if r["start"] > r["end"]:
                raise ValueError(f"ABSOLUTE range는 start <= end여야 한다: {r!r}")
    elif kind == "TIMELINE_RELATIVE":
        refs: set[tuple[str, int]] = set()
        for r in time_ranges:
            timeline_ref = r.get("timeline_ref")
            if timeline_ref is None:
                raise ValueError("kind=TIMELINE_RELATIVE range는 timeline_ref가 필수다(§10-2)")
            if r.get("start_ms") is None or r.get("end_ms") is None:
                raise ValueError("kind=TIMELINE_RELATIVE range는 start_ms/end_ms가 필수다(§6)")
            if r["start_ms"] > r["end_ms"]:
                raise ValueError(f"TIMELINE_RELATIVE range는 start_ms <= end_ms여야 한다: {r!r}")
            refs.add((timeline_ref["timeline_id"], timeline_ref["revision"]))
        if len(refs) > 1:
            raise ValueError(f"TIMELINE_RELATIVE range끼리 timeline_id/revision이 일치해야 한다(§10-2): {refs}")
    else:
        raise ValueError(f"알 수 없는 time_ranges[].kind: {kind!r}(§7 — ABSOLUTE|TIMELINE_RELATIVE만 허용)")


def _validate_target_event_types(target_event_types: list[str]) -> None:
    if not target_event_types:
        raise ValueError("target_event_types는 최소 1개 이상이어야 한다(§10-3)")
    unknown = [t for t in target_event_types if t not in _TARGET_EVENT_TYPES]
    if unknown:
        raise ValueError(f"target_event_types에 v4 baseline enum 밖의 값이 있다(§7): {unknown}")


def _validate_budget(max_cost_krw: float, max_latency_sec: float) -> None:
    if max_cost_krw is None or max_cost_krw <= 0:
        raise ValueError(f"budget.max_cost_krw는 non-null 양수여야 한다(§10-5): {max_cost_krw!r}")
    if max_latency_sec is None or max_latency_sec <= 0:
        raise ValueError(f"budget.max_latency_sec는 non-null 양수여야 한다(§10-5): {max_latency_sec!r}")


def build_analysis_scope(
    case: Any,
    *,
    scope_id: str,
    time_ranges: list[dict[str, Any]],
    target_event_types: list[str],
    max_cost_krw: float,
    max_latency_sec: float,
) -> dict[str, Any]:
    """`case.hints`에서 `hint.vehicle`/`hint.free_text`를 파생하고, 나머지는 호출자가
    공급한 값을 §10 불변조건으로 검증해서 `AnalysisScope` 계약 모양으로 조립한다.
    검증에 실패하면 `ValueError`를 던진다 — §9 "입력 검증 실패 → case 측에서 요청
    자체를 생성하지 않음" 그대로, 이 함수는 잘못된 scope를 반환하지 않는다.
    """
    _validate_time_ranges(time_ranges)
    _validate_target_event_types(target_event_types)
    _validate_budget(max_cost_krw, max_latency_sec)

    return {
        "scope_id": scope_id,
        "time_ranges": time_ranges,
        "target_event_types": target_event_types,
        "hint": {
            "vehicle": case.hints.get("vehicle"),
            "free_text": _sanitize_free_text(case.hints.get("situation")),
        },
        "budget": {
            "max_cost_krw": max_cost_krw,
            "max_latency_sec": max_latency_sec,
        },
        "contract_version": CONTRACT_VERSION,
    }
