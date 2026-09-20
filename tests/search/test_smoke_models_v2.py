"""TDD tests for daesingo-search-smoke/v2 sanitized evidence DTOs.

Privacy contract: serialized output must never carry free-text fields,
paths, URLs, prompt content, exception strings, or plate-like content.
"""

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from daesingo.search.runs import ContractRef
from daesingo.search.scope import VisualEventType
from daesingo.search.smoke_models import (
    SmokeCandidateProjection,
    SmokeFailureCode,
    SmokeFailureStage,
    SmokeFineProjection,
    SmokeStageMetrics,
    SmokeStatus,
    SmokeUsage,
)
from daesingo.search.smoke_models import (
    SmokeReportV2 as SmokeReport,
)
from daesingo.search.visual import AssociationStatus, PrimitiveState, Verification

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _source_ref() -> ContractRef:
    return ContractRef(kind="recording-segment", ref="seg_001")


def _candidate(
    candidate_id: str = "cand_001", rank: int = 1
) -> SmokeCandidateProjection:
    return SmokeCandidateProjection(
        candidate_id=candidate_id,
        source_ref=_source_ref(),
        timeline_id="tl_abc",
        timeline_revision=1,
        start_ms=0,
        end_ms=5000,
        representative_ms=2500,
        rank=rank,
        ranking_score=0.87,
        event_type_hint=VisualEventType.SIGNAL,
    )


def _fine() -> SmokeFineProjection:
    return SmokeFineProjection(
        run_id="run_fine_001",
        input_ref=ContractRef(kind="recording-segment", ref="seg_001"),
        candidate_id="cand_001",
        verification=Verification.OBSERVED,
        visual_event_type=VisualEventType.SIGNAL,
        target_association_status=AssociationStatus.MATCHED,
        target_association_confidence=0.92,
        primitive_states={"traffic_signal_red": PrimitiveState.PRESENT},
        temporal_offsets_ms=(1200, 3400),
        uncertainty_count=0,
    )


def _stage(name: str = "coarse") -> SmokeStageMetrics:
    return SmokeStageMetrics(
        name=name,
        elapsed_ms=120,
        prepared_media_bytes=None,
        prepared_duration_ms=None,
    )


def _usage() -> SmokeUsage:
    return SmokeUsage(
        latency_ms=200,
        input_tokens=100,
        output_tokens=20,
        thought_tokens=5,
        total_tokens=125,
        cost_usd=Decimal("0.00010"),
    )


def _report_data() -> dict[str, object]:
    return {
        "status": SmokeStatus.SUCCEEDED,
        "failure_stage": None,
        "failure_code": None,
        "model": "gemini-2.0-flash",
        "config_fingerprint": "a" * 64,
        "input_sha256": "b" * 64,
        "selected_source_ref": _source_ref(),
        "coarse_candidates": (_candidate(),),
        "selected_candidate_id": "cand_001",
        "fine_result": _fine(),
        "stages": (_stage("coarse"), _stage("fine")),
        "usage": _usage(),
        "elapsed_ms": 350,
    }


def _report(**overrides: object) -> SmokeReport:
    data = _report_data()
    data.update(overrides)
    return SmokeReport.model_validate(data)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_schema_version_is_v2() -> None:
    r = _report()
    assert r.schema_version == "daesingo-search-smoke/v2"


# ---------------------------------------------------------------------------
# extra="forbid" — rejects unknown fields on every model
# ---------------------------------------------------------------------------


def test_smoke_report_rejects_extra_fields() -> None:
    data = _report_data()
    data["injected_extra_field"] = "should_fail"
    with pytest.raises(ValidationError):
        _ = SmokeReport.model_validate(data)


def test_candidate_projection_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _ = SmokeCandidateProjection.model_validate(
            {
                "candidate_id": "c",
                "source_ref": {"kind": "k", "ref": "r"},
                "timeline_id": "tl",
                "timeline_revision": 1,
                "start_ms": 0,
                "end_ms": 1000,
                "representative_ms": 500,
                "rank": 1,
                "ranking_score": 0.5,
                "event_type_hint": None,
                "summary": "should not exist",
            }
        )


def test_fine_projection_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _ = SmokeFineProjection.model_validate(
            {
                "run_id": "r",
                "input_ref": {"kind": "k", "ref": "r"},
                "candidate_id": "c",
                "verification": "OBSERVED",
                "visual_event_type": "SIGNAL",
                "target_association_status": "MATCHED",
                "target_association_confidence": 0.9,
                "primitive_states": {},
                "temporal_offsets_ms": [],
                "uncertainty_count": 0,
                "described_as": "leaked text",
            }
        )


def test_stage_metrics_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _ = SmokeStageMetrics.model_validate(
            {
                "name": "coarse",
                "elapsed_ms": 100,
                "prepared_media_bytes": None,
                "prepared_duration_ms": None,
                "path": "/secret/path",
            }
        )


# ---------------------------------------------------------------------------
# Frozen — immutable after construction
# ---------------------------------------------------------------------------


def test_smoke_report_is_frozen() -> None:
    r = _report()
    with pytest.raises(ValidationError):
        r.model = "new-model"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Round-trip: serialize → parse is exact
# ---------------------------------------------------------------------------


def test_round_trip_serialize_parse() -> None:
    original = _report()
    serialized = original.model_dump(mode="json")
    restored = SmokeReport.model_validate(serialized)
    assert original == restored


# ---------------------------------------------------------------------------
# Privacy: serialized JSON contains none of the forbidden sentinel strings
# ---------------------------------------------------------------------------

FORBIDDEN_KEYS = {
    "summary",
    "uncertainties",
    "described_as",
    "detail",
    "fact",
    "evidence_refs",
    "track_ref",
    "path",
    "base_url",
}

SECRET_SENTINELS = [
    "SECRET_PLATE_12가3456",
    "raw_provider_response_text",
    "/var/secret/path",
    "https://internal.example.com",
    "prompt_template_content",
]


def test_serialized_output_contains_no_forbidden_keys() -> None:
    r = _report()
    raw = json.dumps(r.model_dump(mode="json"))
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in raw, f"forbidden key in output: {key}"


def test_serialized_output_contains_no_secret_sentinels() -> None:
    r = _report()
    raw = json.dumps(r.model_dump(mode="json"))
    for sentinel in SECRET_SENTINELS:
        assert sentinel not in raw, f"sentinel leaked: {sentinel}"


# ---------------------------------------------------------------------------
# failure_code closed enum — rejects unknown values
# ---------------------------------------------------------------------------

ALL_VALID_CODES = [
    "MEDIA_NOT_FOUND",
    "MEDIA_UNREADABLE",
    "MEDIA_UNSUPPORTED",
    "SOURCE_MAPPING_INVALID",
    "SOURCE_SIZE_MISMATCH",
    "MEDIA_TOO_LARGE",
    "DURATION_MISMATCH",
    "CANDIDATE_SOURCE_LINK_INVALID",
    "DEADLINE_EXCEEDED",
    "PROVIDER_AUTH",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_PAYLOAD",
    "BUDGET_UNAVAILABLE",
    "COST_EXCEEDED",
    "NO_CANDIDATES",
]


@pytest.mark.parametrize("code", ALL_VALID_CODES)
def test_failure_code_accepts_all_valid_values(code: str) -> None:
    r = _report(
        status=SmokeStatus.FAILED,
        failure_stage=SmokeFailureStage.COARSE,
        failure_code=SmokeFailureCode(code),
        selected_candidate_id=None,
        fine_result=None,
    )
    assert r.failure_code == SmokeFailureCode(code)


def test_failure_code_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        _ = _report(failure_code="NOT_A_REAL_CODE")


def test_failure_code_enum_has_exactly_15_members() -> None:
    assert len(SmokeFailureCode) == 15


# ---------------------------------------------------------------------------
# ContractRef reuse — source_ref and input_ref use the shared type
# ---------------------------------------------------------------------------


def test_source_ref_is_contract_ref_type() -> None:
    r = _report()
    assert isinstance(r.selected_source_ref, ContractRef)


def test_candidate_source_ref_is_contract_ref_type() -> None:
    cand = _candidate()
    assert isinstance(cand.source_ref, ContractRef)


def test_fine_input_ref_is_contract_ref_type() -> None:
    fine = _fine()
    assert isinstance(fine.input_ref, ContractRef)


# ---------------------------------------------------------------------------
# Structural privacy: projection types have no forbidden fields at class level
# ---------------------------------------------------------------------------


def test_candidate_projection_has_no_summary_field() -> None:
    assert "summary" not in SmokeCandidateProjection.model_fields


def test_candidate_projection_has_no_uncertainties_field() -> None:
    assert "uncertainties" not in SmokeCandidateProjection.model_fields


def test_fine_projection_has_no_described_as_field() -> None:
    assert "described_as" not in SmokeFineProjection.model_fields


def test_fine_projection_has_no_track_ref_field() -> None:
    assert "track_ref" not in SmokeFineProjection.model_fields


def test_fine_projection_has_no_evidence_refs_field() -> None:
    assert "evidence_refs" not in SmokeFineProjection.model_fields


def test_fine_projection_has_no_detail_field() -> None:
    assert "detail" not in SmokeFineProjection.model_fields


def test_fine_projection_has_no_fact_field() -> None:
    assert "fact" not in SmokeFineProjection.model_fields


# ---------------------------------------------------------------------------
# Optional / nullable fields behave correctly
# ---------------------------------------------------------------------------


def test_failure_fields_are_none_on_success() -> None:
    r = _report()
    assert r.failure_stage is None
    assert r.failure_code is None


def test_fine_result_is_none_on_no_candidates_failure() -> None:
    r = _report(
        status=SmokeStatus.FAILED,
        failure_stage=SmokeFailureStage.NO_CANDIDATES,
        failure_code=SmokeFailureCode.NO_CANDIDATES,
        selected_candidate_id=None,
        fine_result=None,
        coarse_candidates=(),
    )
    assert r.fine_result is None
    assert r.selected_candidate_id is None


def test_stage_metrics_optional_media_fields() -> None:
    s = SmokeStageMetrics(
        name="coarse",
        elapsed_ms=50,
        prepared_media_bytes=204800,
        prepared_duration_ms=5000,
    )
    assert s.prepared_media_bytes == 204800
    assert s.prepared_duration_ms == 5000


def test_candidate_event_type_hint_can_be_none() -> None:
    cand = SmokeCandidateProjection(
        candidate_id="cand_x",
        source_ref=_source_ref(),
        timeline_id="tl_x",
        timeline_revision=2,
        start_ms=100,
        end_ms=800,
        representative_ms=400,
        rank=1,
        ranking_score=0.5,
        event_type_hint=None,
    )
    assert cand.event_type_hint is None
