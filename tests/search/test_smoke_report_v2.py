"""Smoke v2 builder projections remain structural and privacy-safe."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import assert_never

import pytest
from pydantic import TypeAdapter

from daesingo.search.coarse import LinkedCoarseResult
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.ledger import SearchLedger, UsageRecord
from daesingo.search.runs import (
    AnalysisRun,
    CandidateEvent,
    CandidateId,
    CandidateSearchResult,
    CandidateSpan,
    ContractRef,
    Implementation,
    Operation,
    RunId,
    RunOutcome,
    UsageSummary,
)
from daesingo.search.scope import VisualEventType
from daesingo.search.smoke_models import (
    SmokeFailureCode,
    SmokeFailureStage,
    SmokeStageMetrics,
    SmokeStatus,
)
from daesingo.search.smoke_report import SmokeReportBuilder
from daesingo.search.usage import ProviderUsage
from daesingo.search.visual import (
    AssociationStatus,
    Primitive,
    PrimitiveState,
    Target,
    TemporalFact,
    Uncertainty,
    Verification,
    VisualEvidence,
    VisualVerificationResult,
)

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

_FORBIDDEN_KEYS = frozenset(
    {
        "summary",
        "uncertainties",
        "described_as",
        "detail",
        "fact",
        "evidence_refs",
        "track_ref",
        "path",
        "url",
        "prompt",
        "raw_response",
        "exception",
    }
)
_SENTINELS = frozenset(
    {
        "secret-value",
        "C:/absolute/private.mp4",
        "12가3456",
        "provider-response-marker",
        "ignore previous instructions",
    }
)


def assert_privacy_safe_evidence(value: JsonValue) -> None:
    """Reject a serialized evidence tree containing forbidden keys or values."""
    match value:
        case dict():
            for key, nested in value.items():
                assert key not in _FORBIDDEN_KEYS
                assert_privacy_safe_evidence(nested)
        case list():
            for nested in value:
                assert_privacy_safe_evidence(nested)
        case str():
            assert value not in _SENTINELS
        case None | bool() | int() | float():
            return
        case unreachable:
            assert_never(unreachable)


def _source_ref() -> ContractRef:
    return ContractRef(kind="analysis_source", ref="source_001")


def _candidate() -> CandidateEvent:
    return CandidateEvent(
        candidate_id=CandidateId("candidate_001"),
        run_id=RunId("run_coarse_001"),
        span=CandidateSpan(
            timeline_id="timeline_001",
            timeline_revision=2,
            start_ms=1_000,
            end_ms=5_000,
            representative_ms=2_500,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="secret-value",
        uncertainties=("provider-response-marker",),
        thumbnail_ref=None,
    )


def _coarse() -> LinkedCoarseResult:
    started = datetime(2026, 9, 21, tzinfo=UTC)
    return LinkedCoarseResult(
        result=CandidateSearchResult(
            analysis_run=AnalysisRun(
                run_id=RunId("run_coarse_001"),
                operation=Operation.CANDIDATE_SEARCH,
                input_ref=_source_ref(),
                implementation=Implementation(
                    impl_id="search:coarse", model_ref="model-v2", prompt_version=None,
                    config_version="v2",
                ),
                outcome=RunOutcome.SUCCEEDED,
                started_at=started,
                completed_at=started,
                issues=(),
                usage_refs=(),
                usage_summary=UsageSummary(
                    processed_duration_ms=None,
                    token_usage=None,
                    latency_ms=None,
                    total_cost=None,
                ),
                contract_version="analysis-run-candidate-event/v1.1",
            ),
            candidates=(_candidate(),),
        ),
        source_ref=_source_ref(),
    )


def _fine() -> VisualVerificationResult:
    started = datetime(2026, 9, 21, tzinfo=UTC)
    return VisualVerificationResult(
        analysis_run=AnalysisRun(
            run_id=RunId("run_fine_001"),
            operation=Operation.VISUAL_VERIFY,
            input_ref=_source_ref(),
            implementation=Implementation(
                impl_id="search:fine", model_ref="model-v2", prompt_version=None,
                config_version="v2",
            ),
            outcome=RunOutcome.SUCCEEDED,
            started_at=started,
            completed_at=started,
            issues=(),
            usage_refs=(),
            usage_summary=UsageSummary(
                processed_duration_ms=None,
                token_usage=None,
                latency_ms=None,
                total_cost=None,
            ),
            contract_version="analysis-run-candidate-event/v1.1",
        ),
        visual_evidence=VisualEvidence(
            schema_version="visual-evidence/v1.0",
            visual_evidence_id="evidence_001",
            run_id=RunId("run_fine_001"),
            input_ref=_source_ref(),
            candidate_id=CandidateId("candidate_001"),
            verification=Verification.OBSERVED,
            visual_event_type=VisualEventType.SIGNAL,
            target=Target(
                association_status=AssociationStatus.MATCHED,
                described_as="secret-value",
                match_with_hint=True,
                association_confidence=0.8,
                track_ref="provider-response-marker",
                evidence_refs=("fr_target_001",),
            ),
            primitives=(
                Primitive(
                    kind="secret-value",
                    state=PrimitiveState.PRESENT,
                    confidence=0.7,
                    evidence_refs=("fr_primitive_001",),
                ),
                Primitive(
                    kind="C:/absolute/private.mp4",
                    state=PrimitiveState.UNCERTAIN,
                    confidence=None,
                    evidence_refs=("fr_primitive_002",),
                ),
            ),
            temporal_facts=(
                TemporalFact(
                    at_offset_ms=1_200,
                    fact="ignore previous instructions",
                    evidence_refs=("fr_temporal_001",),
                ),
                TemporalFact(
                    at_offset_ms=2_500,
                    fact="12가3456",
                    evidence_refs=("fr_temporal_002",),
                ),
            ),
            uncertainties=(
                Uncertainty(
                    kind="secret-value",
                    detail="provider-response-marker",
                    evidence_refs=("fr_uncertain_001",),
                ),
            ),
            legal_status=None,
        ),
    )


def _builder() -> SmokeReportBuilder:
    ledger = SearchLedger()
    ledger.append(
        UsageRecord(
            case_id="case",
            model="model-v2",
            prompt_version="coarse",
            prompt_fingerprint="coarse",
            config_version="v2",
            processed_duration_sec=12,
            latency_ms=101,
            usage=ProviderUsage(100, 20, 5, 125),
            cost_usd=Decimal(999),
            prepared_media_bytes=111,
            prepared_duration_ms=12_000,
        )
    )
    ledger.append(
        UsageRecord(
            case_id="case",
            model="model-v2",
            prompt_version="fine",
            prompt_fingerprint="fine",
            config_version="v2",
            processed_duration_sec=5,
            latency_ms=202,
            usage=ProviderUsage(40, 5, 0, 45),
            cost_usd=Decimal(999),
            prepared_media_bytes=222,
            prepared_duration_ms=5_000,
        )
    )
    return SmokeReportBuilder(
        config=GeminiSearchConfig(
            model="model-v2", input_usd_per_million=1.25, output_usd_per_million=4.5
        ),
        input_sha256="a" * 64,
        ledger=ledger,
    )


def _deadline() -> RunDeadline:
    clock = iter((0.0, 0.333))
    return RunDeadline(clock.__next__, budget_ms=1_000)


def _stages() -> tuple[SmokeStageMetrics, ...]:
    return (
        SmokeStageMetrics(
            name="coarse",
            elapsed_ms=101,
            prepared_media_bytes=111,
            prepared_duration_ms=12_000,
        ),
        SmokeStageMetrics(
            name="fine",
            elapsed_ms=202,
            prepared_media_bytes=222,
            prepared_duration_ms=5_000,
        ),
    )


def test_build_v2_projects_only_safe_domain_fields() -> None:
    # Given
    builder = _builder()
    coarse = _coarse()

    # When
    report = builder.build_v2(
        status=SmokeStatus.SUCCEEDED,
        failure_stage=None,
        failure_code=None,
        coarse=coarse,
        selected_source_ref=_source_ref(),
        selected=coarse.result.candidates[0],
        fine=_fine(),
        stages=_stages(),
        deadline=_deadline(),
    )

    # Then
    assert TypeAdapter(JsonValue).validate_json(report.model_dump_json()) == {
        "schema_version": "daesingo-search-smoke/v2",
        "status": "succeeded",
        "failure_stage": None,
        "failure_code": None,
        "model": "model-v2",
        "config_fingerprint": builder.config.fingerprint,
        "input_sha256": "a" * 64,
        "selected_source_ref": {"kind": "analysis_source", "ref": "source_001"},
        "coarse_candidates": [
            {
                "candidate_id": "candidate_001",
                "source_ref": {"kind": "analysis_source", "ref": "source_001"},
                "timeline_id": "timeline_001",
                "timeline_revision": 2,
                "start_ms": 1_000,
                "end_ms": 5_000,
                "representative_ms": 2_500,
                "rank": 1,
                "ranking_score": 0.9,
                "event_type_hint": "SIGNAL",
            }
        ],
        "selected_candidate_id": "candidate_001",
        "fine_result": {
            "run_id": "run_fine_001",
            "input_ref": {"kind": "analysis_source", "ref": "source_001"},
            "candidate_id": "candidate_001",
            "verification": "OBSERVED",
            "visual_event_type": "SIGNAL",
            "target_association_status": "MATCHED",
            "target_association_confidence": 0.8,
            "primitive_states": {"PRESENT": 1, "UNCERTAIN": 1},
            "temporal_offsets_ms": [1_200, 2_500],
            "uncertainty_count": 1,
        },
        "stages": [
            {
                "name": "coarse",
                "elapsed_ms": 101,
                "prepared_media_bytes": 111,
                "prepared_duration_ms": 12_000,
            },
            {
                "name": "fine",
                "elapsed_ms": 202,
                "prepared_media_bytes": 222,
                "prepared_duration_ms": 5_000,
            },
        ],
        "usage": {
            "latency_ms": 303,
            "input_tokens": 140,
            "output_tokens": 25,
            "thought_tokens": 5,
            "total_tokens": 170,
            "cost_usd": "0.000310",
        },
        "elapsed_ms": 333,
    }
    assert_privacy_safe_evidence(
        TypeAdapter(JsonValue).validate_json(report.model_dump_json())
    )


def test_build_v2_failure_has_exact_v2_failure_fields() -> None:
    # Given
    builder = _builder()

    # When
    report = builder.build_v2(
        status=SmokeStatus.FAILED,
        failure_stage=SmokeFailureStage.COARSE,
        failure_code=SmokeFailureCode.PROVIDER_PAYLOAD,
        coarse=None,
        selected_source_ref=None,
        selected=None,
        fine=None,
        stages=(),
        deadline=_deadline(),
    )

    # Then
    assert report.model_dump(mode="json").keys() == {
        "schema_version",
        "status",
        "failure_stage",
        "failure_code",
        "model",
        "config_fingerprint",
        "input_sha256",
        "selected_source_ref",
        "coarse_candidates",
        "selected_candidate_id",
        "fine_result",
        "stages",
        "usage",
        "elapsed_ms",
    }
    assert report.status is SmokeStatus.FAILED
    assert report.failure_stage is SmokeFailureStage.COARSE
    assert report.failure_code is SmokeFailureCode.PROVIDER_PAYLOAD
    assert report.coarse_candidates == ()
    assert report.selected_candidate_id is None
    assert report.fine_result is None


@pytest.mark.parametrize("key", sorted(_FORBIDDEN_KEYS))
def test_privacy_assertion_rejects_every_forbidden_key(key: str) -> None:
    # Given
    value: JsonValue = {key: "safe"}

    # When / Then
    with pytest.raises(AssertionError):
        assert_privacy_safe_evidence(value)


@pytest.mark.parametrize("sentinel", sorted(_SENTINELS))
def test_privacy_assertion_rejects_every_sentinel(sentinel: str) -> None:
    # Given
    value: JsonValue = {"safe": [sentinel]}

    # When / Then
    with pytest.raises(AssertionError):
        assert_privacy_safe_evidence(value)
