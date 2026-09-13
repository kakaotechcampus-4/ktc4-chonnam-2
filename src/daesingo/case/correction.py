"""CorrectionRecord 생성 — case가 소유(Producer)하는 사용자 정정 기록.

`selection_rev`는 "수정 횟수 카운터가 아니라 그 수정이 일어난 candidate 선택 context"다
(`contract-correction-record.md` §4, 이슈 #39 Required-3에서 실제로 이 버그가 났던
지점 — `docs/mock/02_mock_scenario_catalog.md`의 `scenario_correction_rerun_001` v4 노트
참고). 그래서 여기서는 correction 시점의 `case.selection_rev`를 그대로 스냅샷하고,
correction 자체는 selection_rev를 절대 증가시키지 않는다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from daesingo.case.domain import CaseAggregate

CONTRACT_VERSION = "correction-record/v1.1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def apply_correction(
    case: CaseAggregate,
    *,
    kind: str,
    target_field: str,
    previous_value: Any,
    new_value: Any,
) -> dict[str, Any]:
    # 같은 target_field의 최신(=supersede 체인의 head) correction을 찾는다 — 순환 방지를 위해
    # "가장 최근에 추가된 것"만 후보로 삼는다(같은 target_field에 여러 개가 있어도 head는 하나).
    previous = next(
        (c for c in reversed(case.correction_records) if c["target_field"] == target_field),
        None,
    )
    record: dict[str, Any] = {
        "contract": "CorrectionRecord",
        "contract_version": CONTRACT_VERSION,
        "correction_id": f"corr_{case.case_id}_{uuid.uuid4().hex[:8]}",
        "case_id": case.case_id,
        "selection_rev": case.selection_rev,  # 스냅샷 — 이 호출로 증가시키지 않는다
        "supersedes_id": previous["correction_id"] if previous else None,
        "kind": kind,
        "target_field": target_field,
        "previous_value": previous_value,
        "new_value": new_value,
        "corrected_at": _now(),
    }
    case.correction_records.append(record)
    return record
