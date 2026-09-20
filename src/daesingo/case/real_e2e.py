"""`scenario_happy_001` 대표 시나리오용 real E2E 파이프라인 — recording → search →
readout → evidence까지 전부 실제 공개 함수를 호출한다(W5/W6, 2026-09-22 월 20:00
회의 데드라인 대응).

기준은 "대표 시나리오 1개가 전체 흐름을 실제로 통과하는가"이지 모든 단계가 PASS
등급을 받는가가 아니다(요청 문서 "이번엔 안 해도 되는 것" — 모든 edge case·완성된
Worker 배선은 이번 범위 밖).

## 알려진 단순화 (정직하게 남김 — W7에서 메운다)

- **`time_source_candidates`**: recording의 `RecordingFixture` pydantic 모델에 이
  필드 자체가 없다(1차 구현 범위 밖) — 공개 함수로 노출된 적이 없으므로 recording의
  raw fixture JSON에서 그대로 읽는다. 이 한 곳만 mock이고 나머지는 전부 real 함수
  호출이다.
- **`situation_response`/`observation_facts`**: case에 이 값을 만드는 로직이 아직
  없어(intake UI 미구현) `None`으로 둔다. 그 결과 `FINAL_PACKAGE` 판정이 PASS/WARN에
  못 미쳐 `build_report_package()`가 `PackageNotReady`를 던질 수 있다 — 이건 실패가
  아니라 "정보가 부족해 아직 패키지를 못 만든다"는 실제 도메인 상태이고, `CaseView`의
  partial 표현이 원래 이런 상태를 위해 있다(`module-architecture.md` §5-12).
- **`gps_observation`**: recording이 GPS 관찰을 내놓는 공개 함수를 아직 노출하지 않아
  `None`으로 둔다. case의 자연어 위치 단서(`hints.location`)는 real 경로에 전달하지만,
  좌표(`location.coord`)는 GPS producer가 연결되기 전까지 비어 있을 수 있다.
- **시나리오 고정**: `scenario_happy_001` 하나로 고정돼 있다. 다른 시나리오로 넓히려면
  recording fixture 선택과 asset_facts 매핑을 다시 설계해야 한다(W7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from daesingo import search as search_module
from daesingo.evidence import (
    assemble_evidence,
    build_report_package,
    calculate_evidence_needs,
    evaluate_requirements,
    resolve_time,
)
from daesingo.evidence.errors import PackageNotReady
from daesingo.readout import api as readout_api
from daesingo.readout import providers as readout_providers
from daesingo.readout.contracts import InputRef
from daesingo.recording import RecordingService, load_recording_fixture

SCENARIO_ID = "scenario_happy_001"


@dataclass
class EvidenceBundle:
    evidence_record: dict[str, Any]
    evidence_needs: dict[str, Any] | None
    requirement_report_evidence: dict[str, Any]
    requirement_report_package: dict[str, Any]
    report_package: dict[str, Any] | None
    package_error: str | None


def build_happy_001_evidence_bundle(
    *,
    case_id: str,
    candidate: search_module.CandidateEvent,
    scope: search_module.AnalysisScope,
    mock_root: Path,
    selection_rev: int = 1,
    location_hint: str | None = None,
) -> EvidenceBundle:
    """recording → `search.verify_visual` → readout → evidence까지 실제 함수로 이어서
    실행한다. 모듈 docstring의 "알려진 단순화" 두 곳만 raw fixture/`None`이고 나머지는
    전부 각 모듈의 공개 함수 호출 결과다.
    """
    fixture = load_recording_fixture(SCENARIO_ID)
    rec_service = RecordingService.from_fixture(fixture, case_id=case_id)

    span_resolution_fixture = fixture.span_resolutions[0]
    resolution = rec_service.resolve_span(
        span_resolution_fixture.timeline_ref.model_dump(mode="json"),
        span_resolution_fixture.requested_range.model_dump(mode="json"),
    )
    analysis_source = rec_service.prepare_analysis_source(
        resolution.spans[0].model_dump(mode="json"),
        fixture.analysis_sources[0].profile_ref,
    )
    incident_clip = rec_service.build_incident_clip(resolution.model_dump(mode="json"))

    visual_result = search_module.verify_visual(
        search_module.ContractRef(kind="analysis_source", ref=analysis_source.analysis_source_ref),
        scope.hint,
    )

    read_request = readout_api.ReadRequest(
        case_id=case_id,
        candidate_id=candidate.candidate_id,
        input_ref=InputRef(
            incident_clip_ref=incident_clip.incident_clip_ref,
            source_profile="readout-native",
            provenance="SOURCE_DERIVED_INCIDENT_CLIP",
        ),
    )
    _plate_run, plate_readout = readout_api.read_plate(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )
    _overlay_run, overlay_readout = readout_api.read_overlay_time(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )

    # 알려진 단순화 1 (모듈 docstring 참고) — recording이 아직 공개 함수로 노출 안 함.
    raw_recording = json.loads(
        (mock_root / "recording" / f"{SCENARIO_ID}.json").read_text(encoding="utf-8")
    )
    time_source_candidates = raw_recording.get("time_source_candidates", [])

    time_resolution = resolve_time(
        time_source_candidates=time_source_candidates,
        overlay_time_readout=overlay_readout.to_dict() if overlay_readout else None,
        candidate_event=candidate.model_dump(mode="json"),
        case_id=case_id,
        selection_rev=selection_rev,
        resolution_id=f"tr_{case_id}_001",
    )

    evidence_record = assemble_evidence(
        case_id=case_id,
        selection_rev=selection_rev,
        candidate_event=candidate.model_dump(mode="json"),
        visual_evidence=visual_result.visual_evidence.model_dump(mode="json"),
        time_resolution=time_resolution,
        plate_readout=plate_readout.to_dict() if plate_readout else None,
        incident_clip=incident_clip.model_dump(mode="json"),
        record_id=f"er_{case_id}_001",
        location_hint=location_hint,
        # 알려진 단순화 2 및 GPS 단순화 (모듈 docstring 참고).
        situation_response=None,
        gps_observation=None,
    )

    evidence_needs = calculate_evidence_needs(
        evidence_record,
        plate_readout.to_dict() if plate_readout else None,
        emit_empty=True,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    requirement_report_evidence = evaluate_requirements(
        evidence_record,
        scope="EVIDENCE",
        report_id=f"rr_{case_id}_evidence",
        evaluated_at=now,
        time_resolution=time_resolution,
    )

    asset_refs = [facts.asset_ref for facts in fixture.asset_facts]
    asset_facts_real = [
        rec_service.lookup_asset_facts(ref).model_dump(mode="json") for ref in asset_refs
    ]
    requirement_report_package = evaluate_requirements(
        evidence_record,
        scope="FINAL_PACKAGE",
        report_id=f"rr_{case_id}_package",
        evaluated_at=now,
        time_resolution=time_resolution,
        asset_facts=asset_facts_real,
        # 알려진 단순화 2와 같은 이유로 None (모듈 docstring 참고).
        observation_facts=None,
    )

    report_package: dict[str, Any] | None = None
    package_error: str | None = None
    try:
        report_package = build_report_package(
            evidence_record,
            requirement_report_package,
            package_id=f"pkg_{case_id}_001",
            created_at=now,
            asset_facts=asset_facts_real,
        )
    except PackageNotReady as exc:
        package_error = str(exc)

    return EvidenceBundle(
        evidence_record=evidence_record,
        evidence_needs=evidence_needs,
        requirement_report_evidence=requirement_report_evidence,
        requirement_report_package=requirement_report_package,
        report_package=report_package,
        package_error=package_error,
    )
