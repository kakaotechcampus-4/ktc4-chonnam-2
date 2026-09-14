from pathlib import Path

import pytest
from pydantic import ValidationError

from daesingo.search import AnalysisScope, CandidateSearchResult
from daesingo.search.fixtures import FixtureSearchService, SearchScenario

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_edge_scenario(name: str) -> SearchScenario:
    return SearchScenario.model_validate_json(
        (FIXTURE_DIR / f"scenario_{name}.json").read_text(encoding="utf-8")
    )


def test_partial_result_keeps_usable_candidate_and_issue() -> None:
    # Given
    service = FixtureSearchService(FIXTURE_DIR)
    scenario = load_edge_scenario("partial_not_observed_001")

    # When
    result = service.search_candidates(scenario.analysis_scopes[0])

    # Then
    assert result.analysis_run.outcome == "PARTIAL"
    assert result.analysis_run.issues[0].kind == "PRIMITIVE_FAILURE"
    assert len(result.candidates) == 1


def test_not_observed_is_a_valid_fine_result() -> None:
    # Given
    service = FixtureSearchService(FIXTURE_DIR)
    scenario = load_edge_scenario("partial_not_observed_001")
    expected = scenario.visual_evidences[0]

    # When
    result = service.verify_visual(expected.input_ref)

    # Then
    assert result.analysis_run.outcome == "SUCCEEDED"
    assert result.visual_evidence.verification == "NOT_OBSERVED"
    assert result.visual_evidence.visual_event_type is None


def test_failed_result_has_no_candidates() -> None:
    # Given
    service = FixtureSearchService(FIXTURE_DIR)
    scenario = load_edge_scenario("failed_001")

    # When
    result = service.search_candidates(scenario.analysis_scopes[0])

    # Then
    assert result.analysis_run.outcome == "FAILED"
    assert result.candidates == ()


def test_mixed_scope_coordinate_kinds_are_rejected() -> None:
    # Given
    absolute = load_edge_scenario("partial_not_observed_001").analysis_scopes[0]
    relative = SearchScenario.model_validate_json(
        (
            Path(__file__).resolve().parents[2]
            / "data"
            / "mock"
            / "search"
            / "scenario_relative_rebase_001.json"
        ).read_text(encoding="utf-8")
    ).analysis_scopes[0]

    # When / Then
    with pytest.raises(ValidationError):
        _ = AnalysisScope(
            scope_id="scope_mixed",
            time_ranges=(absolute.time_ranges[0], relative.time_ranges[0]),
            target_event_types=absolute.target_event_types,
            hint=absolute.hint,
            budget=absolute.budget,
            contract_version="1.1.0",
        )


def test_partial_without_issue_is_rejected() -> None:
    # Given
    scenario = load_edge_scenario("partial_not_observed_001")
    run = scenario.candidate_search_result.analysis_run.model_copy(update={"issues": ()})

    # When / Then
    with pytest.raises(ValidationError):
        _ = CandidateSearchResult(
            analysis_run=run, candidates=scenario.candidate_search_result.candidates
        )


def test_observed_event_rule_is_enforced() -> None:
    # Given
    evidence = load_edge_scenario("partial_not_observed_001").visual_evidences[0]
    invalid_json = evidence.model_dump_json().replace(
        '"verification":"NOT_OBSERVED"', '"verification":"OBSERVED"'
    )

    # When / Then
    with pytest.raises(ValidationError):
        _ = type(evidence).model_validate_json(invalid_json)


def test_legacy_absolute_scope_supports_multiple_targets_and_null_hints() -> None:
    # Given
    legacy_scope_json = (
        '{"scope_id":"scope_legacy","time_ranges":['
        '{"start":"2026-08-24T18:00:00+09:00",'
        '"end":"2026-08-24T18:20:00+09:00"}],'
        '"target_event_types":["SIGNAL","CENTER_LINE_CROSSING"],'
        '"hint":{"vehicle":null,"free_text":null},'
        '"budget":{"max_cost_krw":1000,"max_latency_sec":180},'
        '"contract_version":"1.1.0"}'
    )

    # When
    scope = AnalysisScope.model_validate_json(legacy_scope_json)

    # Then
    assert scope.time_ranges[0].kind == "ABSOLUTE"
    assert len(scope.target_event_types) == 2
    assert scope.hint.vehicle is None


def test_producer_contracts_round_trip_through_json() -> None:
    # Given
    scenario = load_edge_scenario("partial_not_observed_001")
    search_result = scenario.candidate_search_result
    visual_evidence = scenario.visual_evidences[0]

    # When
    scope_round_trip = AnalysisScope.model_validate_json(
        scenario.analysis_scopes[0].model_dump_json()
    )
    result_round_trip = CandidateSearchResult.model_validate_json(search_result.model_dump_json())
    evidence_round_trip = type(visual_evidence).model_validate_json(
        visual_evidence.model_dump_json()
    )

    # Then
    assert scope_round_trip == scenario.analysis_scopes[0]
    assert result_round_trip == search_result
    assert evidence_round_trip == visual_evidence
