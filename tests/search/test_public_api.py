from pathlib import Path

import pytest

from daesingo.search import (
    AnalysisScope,
    ContractRef,
    FixtureNotFoundError,
    search_candidates,
    verify_visual,
)
from daesingo.search.fixtures import SearchScenario

MOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "mock" / "search"


def load_scenario(name: str) -> SearchScenario:
    return SearchScenario.model_validate_json(
        (MOCK_DIR / f"scenario_{name}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    ("name", "outcome", "candidate_count"),
    [
        ("happy_001", "SUCCEEDED", 1),
        ("empty_001", "SUCCEEDED", 0),
        ("unknown_abstain_partial_001", "SUCCEEDED", 1),
        ("plate_reread_001", "SUCCEEDED", 1),
        ("correction_rerun_001", "SUCCEEDED", 1),
        ("relative_rebase_001", "SUCCEEDED", 1),
    ],
)
def test_search_candidates_matches_canonical_fixture(
    name: str, outcome: str, candidate_count: int
) -> None:
    # Given
    scenario = load_scenario(name)
    scope = scenario.analysis_scopes[0]
    expected = scenario.candidate_search_result

    # When
    result = search_candidates(scope)

    # Then
    assert result == expected
    assert result.analysis_run.outcome == outcome
    assert len(result.candidates) == candidate_count


@pytest.mark.parametrize(
    ("name", "verification", "event_type"),
    [
        ("happy_001", "OBSERVED", "SOLID_LINE_LANE_CHANGE"),
        ("unknown_abstain_partial_001", "UNCERTAIN", None),
        ("plate_reread_001", "OBSERVED", "SIGNAL"),
        ("correction_rerun_001", "OBSERVED", "MOTORCYCLE_HELMET_NON_USE"),
    ],
)
def test_verify_visual_returns_run_and_evidence(
    name: str, verification: str, event_type: str | None
) -> None:
    # Given
    scenario = load_scenario(name)
    expected_evidence = scenario.visual_evidences[0]

    # When
    result = verify_visual(expected_evidence.input_ref, scenario.analysis_scopes[0].hint)

    # Then
    assert result.analysis_run.operation == "VISUAL_VERIFY"
    assert result.analysis_run.run_id == expected_evidence.run_id
    assert result.visual_evidence == expected_evidence
    assert result.visual_evidence.verification == verification
    assert result.visual_evidence.visual_event_type == event_type


def test_relative_scope_preserves_timeline_revision() -> None:
    # Given
    scenario = load_scenario("relative_rebase_001")

    # When
    result = search_candidates(scenario.analysis_scopes[0])

    # Then
    assert result.candidates[0].span.timeline_revision == 1
    assert result.candidates[0].span.start_ms == 502_000


def test_happy_representative_matches_fine_event_offset() -> None:
    # Given
    scenario = load_scenario("happy_001")

    # When
    coarse = search_candidates(scenario.analysis_scopes[0])
    fine = verify_visual(scenario.visual_evidences[0].input_ref)

    # Then
    span = coarse.candidates[0].span
    event_offset = fine.visual_evidence.temporal_facts[0].at_offset_ms
    assert event_offset is not None
    assert span.representative_ms == span.start_ms + event_offset


def test_unknown_scope_returns_typed_error() -> None:
    # Given
    known = load_scenario("empty_001").analysis_scopes[0]
    unknown = AnalysisScope(
        scope_id="scope_missing",
        time_ranges=known.time_ranges,
        target_event_types=known.target_event_types,
        hint=known.hint,
        budget=known.budget,
        contract_version=known.contract_version,
    )

    # When / Then
    with pytest.raises(FixtureNotFoundError, match="scope_missing"):
        _ = search_candidates(unknown)


def test_unknown_visual_input_returns_typed_error() -> None:
    # Given
    missing = ContractRef(kind="analysis_source", ref="as_missing")

    # When / Then
    with pytest.raises(FixtureNotFoundError, match="as_missing"):
        _ = verify_visual(missing)
