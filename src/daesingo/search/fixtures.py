from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, assert_never, override

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from ._base import ContractModel
from .runs import (
    AnalysisRun,
    AnalysisRunCandidateEvents,
    CandidateSearchResult,
    ContractRef,
    Operation,
)
from .scope import AnalysisScope, SearchHint
from .visual import VisualEvidence, VisualVerificationResult


class SearchScenario(ContractModel):
    scenario_id: str = Field(min_length=1)
    module: Literal["search"]
    analysis_scopes: tuple[AnalysisScope, ...] = Field(min_length=1)
    analysis_run_candidate_events: tuple[AnalysisRunCandidateEvents, ...] = Field(min_length=1)
    visual_evidences: tuple[VisualEvidence, ...]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        run_ids = {record.analysis_run.run_id for record in self.analysis_run_candidate_events}
        if any(evidence.run_id not in run_ids for evidence in self.visual_evidences):
            raise PydanticCustomError("scenario_visual_run", "VisualEvidence run_id must exist")
        return self

    @property
    def candidate_search_result(self) -> CandidateSearchResult:
        for record in self.analysis_run_candidate_events:
            match record.analysis_run.operation:
                case Operation.CANDIDATE_SEARCH:
                    return CandidateSearchResult(
                        analysis_run=record.analysis_run,
                        candidates=record.candidates,
                    )
                case Operation.VISUAL_VERIFY:
                    continue
                case unreachable:
                    assert_never(unreachable)
        raise MissingScenarioArtifactError(
            scenario_id=self.scenario_id,
            artifact="CANDIDATE_SEARCH",
        )


@dataclass(frozen=True, slots=True)
class FixtureNotFoundError(Exception):
    reference: str

    @override
    def __str__(self) -> str:
        return f"search fixture not found for {self.reference}"


@dataclass(frozen=True, slots=True)
class MissingScenarioArtifactError(Exception):
    scenario_id: str
    artifact: str

    @override
    def __str__(self) -> str:
        return f"{self.scenario_id} has no {self.artifact} artifact"


@dataclass(frozen=True, slots=True)
class FixtureSearchService:
    fixture_dir: Path

    def search_candidates(self, scope: AnalysisScope) -> CandidateSearchResult:
        for scenario in self._scenarios():
            if any(
                candidate_scope.scope_id == scope.scope_id
                for candidate_scope in scenario.analysis_scopes
            ):
                return scenario.candidate_search_result
        raise FixtureNotFoundError(reference=scope.scope_id)

    def verify_visual(
        self,
        input_ref: ContractRef,
        target_hint: SearchHint | None = None,
    ) -> VisualVerificationResult:
        del target_hint
        for scenario in self._scenarios():
            for evidence in scenario.visual_evidences:
                if evidence.input_ref == input_ref:
                    return VisualVerificationResult(
                        analysis_run=self._visual_run(scenario, evidence),
                        visual_evidence=evidence,
                    )
        raise FixtureNotFoundError(reference=input_ref.ref)

    def _scenarios(self) -> tuple[SearchScenario, ...]:
        return tuple(
            SearchScenario.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.fixture_dir.glob("scenario_*.json"))
        )

    @staticmethod
    def _visual_run(scenario: SearchScenario, evidence: VisualEvidence) -> AnalysisRun:
        for record in scenario.analysis_run_candidate_events:
            if record.analysis_run.run_id == evidence.run_id:
                return record.analysis_run
        raise MissingScenarioArtifactError(
            scenario_id=scenario.scenario_id,
            artifact=f"VISUAL_VERIFY run {evidence.run_id}",
        )
