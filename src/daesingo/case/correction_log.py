"""`export_learning_log()` — Correction 로그 1단계(평가 재사용) 익명화 export.

`docs/modules/case/decisions/correction-log-reuse.md`: 사용자 correction 데이터 재사용은
1단계(평가 재사용 — `case.export_learning_log()` → 익명화 파일 → `eval`)와 2단계(학습
재사용, 아직 없음 · "전제만") 둘로 나뉜다. 이 모듈은 1단계만 구현한다.

⚠️ 이 결정 문서 자체가 "`case` Owner가 설계할 것"으로 5개 항목(동의 문구·저장 위치/
익명화 수준을 Contract 필드로/보관기간/철회 시 처리/1·2단계 구분 고지문)을 전부
`미결`로 남겨뒀다 — 이 함수는 **동의 게이팅을 하지 않는다**(그 결정이 아직 없으므로
임의로 게이팅 로직을 만들지 않는다). 이 함수가 구현하는 건 딱 하나, 결정문에 "이 3줄보다
약해지지 않는다"고 명시된 익명화 최소 규칙 3개뿐이다:

    · 번호판 문자열 제거 — 틀린 위치와 문자 개수만 남긴다
    · 정확한 좌표 제거 — 오차 반경만 남긴다
    · 원본 영상 참조는 로컬 케이스 ID로만 — 파일 경로·파일명·외부 provider ref를 넣지 않는다

`CorrectionRecord`(`contract-correction-record.md` §6)에는 애초에 파일 경로·provider ref
필드가 없으므로 세 번째 규칙은 "내보내는 필드를 `case_id`로 제한한다"로 자동 충족된다
(추가로 걸러낼 게 없다). 나머지 두 규칙은 `target_field`가 `vehicle_number`/
`location.coord`일 때만 해당하고, 그 외 target_field(occurred_at/event.*/
location.address 등)는 계약이 원래 값 자체를 요구하는 자유 텍스트·ISO8601·enum이라
그대로 내보낸다 — 이 3줄이 요구하지 않는 것까지 임의로 더 가리지 않는다.

⚠️ `error_radius_m` 계산(haversine 거리)과 번호판 diff_positions 계산은 실제 정답지
fixture가 하나도 없다(현재 mock pack에는 `vehicle_number`/`location.coord` target의
CorrectionRecord 예시가 없다) — 계약이 요구하는 "무엇을 남기는가"의 최소 뼈대이지, 정확한
버킷팅·정밀도는 실측 없이 자체 판단으로 정한 placeholder다.
"""
from __future__ import annotations

import math
from typing import Any

from daesingo.case.domain import CaseAggregate

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _anonymize_vehicle_number(previous_value: str | None, new_value: str | None) -> dict[str, Any]:
    prev_len = len(previous_value) if previous_value else 0
    new_len = len(new_value) if new_value else 0
    diff_positions: list[int] = []
    if previous_value is not None and new_value is not None and prev_len == new_len:
        diff_positions = [i for i, (a, b) in enumerate(zip(previous_value, new_value)) if a != b]
    return {
        "previous_value": {"length": prev_len},
        "new_value": {"length": new_len},
        "diff_positions": diff_positions,
    }


def _anonymize_location_coord(previous_value: dict[str, Any] | None, new_value: dict[str, Any] | None) -> dict[str, Any]:
    error_radius_m: float | None = None
    if previous_value is not None and new_value is not None:
        error_radius_m = round(
            _haversine_m(previous_value["lat"], previous_value["lon"], new_value["lat"], new_value["lon"]), 1
        )
    return {"previous_value": None, "new_value": None, "error_radius_m": error_radius_m}


def _anonymize_entry(record: dict[str, Any]) -> dict[str, Any]:
    target_field = record["target_field"]
    if target_field == "vehicle_number":
        values = _anonymize_vehicle_number(record["previous_value"], record["new_value"])
    elif target_field == "location.coord":
        values = _anonymize_location_coord(record["previous_value"], record["new_value"])
    else:
        values = {"previous_value": record["previous_value"], "new_value": record["new_value"]}
    return {
        "correction_id": record["correction_id"],
        "kind": record["kind"],
        "target_field": target_field,
        # §9-5 — correction이 발생한 selection_rev(candidate context)는 보존한다.
        "selection_rev": record["selection_rev"],
        "supersedes_id": record["supersedes_id"],
        "corrected_at": record["corrected_at"],
        **values,
    }


def export_learning_log(case: CaseAggregate) -> list[dict[str, Any]]:
    """`case.correction_records`(append-only)를 1단계(평가 재사용) 익명화 형태로 내보낸다.
    `case_id`는 로컬 케이스 ID 그대로 남긴다(그 자체가 세 번째 최소 규칙이 요구하는 전부다 —
    파일 경로·외부 provider ref는 애초에 `CorrectionRecord`에 없다)."""
    return [
        {"case_id": case.case_id, **_anonymize_entry(record)} for record in case.correction_records
    ]
