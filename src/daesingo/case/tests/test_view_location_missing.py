"""위치를 확보하지 못한 사건(EvidenceRecord에 `location` 키 자체가 없는 경우)에 대한
회귀 테스트 — 이슈 #48 Q2 조사 중 실제 코드를 실행해 발견한 두 개의 결함을 고정한다.

  1. `_field_states()` / `_build_evidence_view()`가 `evidence_record["location"]`을
     무조건 인덱싱해서 `KeyError`를 던지던 결함 — `scenario_unknown_abstain_partial_001`의
     `ev_u001`은 실제로 `location` 키 자체가 없다(위치 미확보는 처음부터 정상 케이스,
     core-user-flow.md §19 참고).
  2. `_build_package_view()`가 `report_inputs["location"]`이 `None`일 때
     `value["display_text"]`로 인덱싱해서 `TypeError`를 던지던 결함 — 같은 시나리오의
     `pkg_u001`은 `report_inputs.location`이 `null`이다.

⚠️ `scenario_unknown_abstain_partial_001`은 `view.py` docstring이 명시한 §11 1차 구현
제외 범위(abstain/WARN/UNKNOWN 표시 규칙)에 속한다. 그래서 `evidence`/`package` 뷰
전체를 fixture와 비교하지 않고, 이번에 고친 location 관련 필드만 좁게 고정한다
(`review_needed`/`reason_code`는 location 이외의 다른 필드까지 종합해야 하는데, 그
종합 로직은 1차 구현 범위 밖이다).
"""
import json
from pathlib import Path

from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.view import _build_evidence_view, _build_package_view, _field_states

MOCK_ROOT = Path(__file__).resolve().parents[4] / "data" / "mock"
SCENARIO_ID = "unknown_abstain_partial_001"


def _adapter() -> MockFixtureAdapter:
    return MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)


def _case_fixture_ready_view() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        fixture = json.load(fh)
    return fixture["case_views"][-1]


def test_field_states_handles_missing_location_key_without_crash():
    evidence_record = _adapter().get_evidence_record()
    assert "location" not in evidence_record  # 전제 확인 — u001 fixture의 실제 모양

    states = _field_states(evidence_record)

    assert states["location"] == {"info_state": "INFO_UNKNOWN", "source_label_key": None}


def test_build_evidence_view_handles_missing_location_without_crash():
    evidence_record = _adapter().get_evidence_record()

    view = _build_evidence_view(evidence_record, preview_ref="fr_u001_plate1")

    assert view["location_display"] == {
        "value": None,
        "needs_review": False,
        "info_state": "INFO_UNKNOWN",
        "source_label_key": None,
        "coord": None,
        "search_keyword": None,
    }
    # fixture 정답지(data/mock/case)의 location_display와도 정확히 일치해야 한다.
    ready = _case_fixture_ready_view()
    assert view["location_display"] == ready["evidence"]["location_display"]


def test_build_package_view_handles_null_report_inputs_location_without_crash():
    adapter = _adapter()
    evidence_record = adapter.get_evidence_record()
    report_package = adapter.get_report_package()
    assert report_package["report_inputs"]["location"] is None  # 전제 확인

    package_view = _build_package_view(report_package, evidence_record)

    assert package_view["report_fields"]["location"] is None
    assert package_view["report_field_states"]["location"] == {
        "info_state": "INFO_UNKNOWN",
        "source_label_key": None,
    }
    # ⚠️ report_fields/unconfirmed_fields 전체, 그리고 report_field_states 중 location 항목만
    # fixture와 비교한다 — safety_report_type 등 다른 필드의 info_state 매핑(AI_ESTIMATED vs
    # NEEDS_REVIEW)은 이번 location 결함 수정과 무관한, §11 범위 밖의 별개 이슈다.
    ready = _case_fixture_ready_view()
    assert package_view["report_fields"] == ready["package"]["report_fields"]
    assert package_view["report_field_states"]["location"] == ready["package"]["report_field_states"]["location"]
    assert package_view["unconfirmed_fields"] == ready["package"]["unconfirmed_fields"]
