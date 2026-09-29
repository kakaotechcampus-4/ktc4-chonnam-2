"""#47 — `evidence.plate_preview_ref`: 번호판 근거 프레임을 CaseView로 내린다.

`core-user-flow.md` §12의 `[번호판 이미지 보기]`·`[확대]`가 보여 줄 프레임이 CaseView에 없었다
(`evidence.preview_ref`는 사건 대표 썸네일이지 번호판 프레임이 아니다 — #47 신유민 정정).
readout `plate-readout/v1.3` §9가 case 행 ①로 「`best_frame.frame_ref`를 CaseView로 통과」를
등재했다.

값은 **현재 번호판 값의 근거 PlateReadout**의 `best_frame.frame_ref`다 — 재판독 뒤에도 첫 판독
프레임이 남던 `preview_ref` 혼동(#47, `plate_reread_001` rev4)을 되풀이하지 않는다.
`crop_ref`는 내리지 않는다(opaque identity, 조회 handle 아님).
"""
from __future__ import annotations

import json
from pathlib import Path

from daesingo.case import jobs, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _load(module: str, scenario: str) -> dict:
    return json.loads((MOCK_ROOT / module / f"scenario_{scenario}.json").read_text(encoding="utf-8"))


def _selected_case(candidate_id: str, thumb_ref: str | None) -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_plate_preview", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [Candidate(candidate_id=candidate_id, at=None, at_provenance=None, observed="", thumb_ref=thumb_ref)]
    )
    case.select_candidate(candidate_id)
    return case


def test_mock_happy_plate_preview_is_best_frame_not_event_thumbnail() -> None:
    adapter = MockFixtureAdapter(MOCK_ROOT, "happy_001")
    case = _selected_case("candidate_h001", "fr_h001_thumb")

    view = service.build_view_from_adapter(case, adapter)

    assert view["evidence"]["plate_preview_ref"] == "fr_h001_plate1"
    # 사건 대표 썸네일은 그대로다 — 두 값은 다른 뜻이다.
    assert view["evidence"]["preview_ref"] == "fr_h001_thumb"


def test_reread_follows_current_value_readout() -> None:
    """재판독(v2)이 현재 값이면 재판독 PlateReadout의 프레임을 쓴다(첫 판독 프레임 아님)."""
    evidence = _load("evidence", "plate_reread_001")["evidence_records"]
    plate_readouts = _load("readout", "plate_reread_001")["plate_readouts"]
    case = _selected_case("candidate_p001", "fr_p001_thumb")

    view = build_case_view(case, evidence_record=evidence[-1], plate_readouts=plate_readouts)

    assert view["evidence"]["plate_preview_ref"] == "fr_p001_plate3"


def test_no_plate_readout_source_means_null() -> None:
    """번호판 값이 PlateReadout에서 오지 않았으면(판독 abstain 등) 가리킬 프레임이 없다."""
    evidence = _load("evidence", "plate_reread_001")["evidence_records"][0]
    assert "vehicle_number" not in evidence  # 첫 판독 abstain
    plate_readouts = _load("readout", "plate_reread_001")["plate_readouts"]
    case = _selected_case("candidate_p001", "fr_p001_thumb")

    view = build_case_view(case, evidence_record=evidence, plate_readouts=plate_readouts)

    assert view["evidence"]["plate_preview_ref"] is None


def test_real_adapter_projects_plate_readout_best_frame() -> None:
    """실제 readout 경로 — case가 받은 PlateReadout의 `best_frame.frame_ref`가 그대로 나온다."""
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = CaseAggregate.intake(case_id="case_plate_preview_real", hints={}, manifest_summary={})
    real = RealAdapter(case_id="case_plate_preview_real", case=case, search_scope=scope, mock_root=MOCK_ROOT)
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:plate-preview-coarse")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    view = service.build_view_from_adapter(case, real)

    readouts = real.get_plate_readouts()
    assert len(readouts) == 1
    assert view["evidence"]["plate_preview_ref"] == readouts[0]["best_frame"]["frame_ref"]
    assert view["evidence"]["plate_preview_ref"] is not None


def test_plate_image_export_kind_is_registered() -> None:
    """#47 Q3 — `PLATE_IMAGE_EXPORT`를 `REPORT_VIDEO_EXPORT`와 같은 급으로 등재한다(계약 A절 §7)."""
    case = _selected_case("candidate_h001", "fr_h001_thumb")

    record = jobs.issue_job(case, "PLATE_IMAGE_EXPORT", input_fingerprint="sha1:plate-image-export")

    assert record["kind"] == "PLATE_IMAGE_EXPORT"
