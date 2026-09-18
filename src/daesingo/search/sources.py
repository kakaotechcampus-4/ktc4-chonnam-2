from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .runs import ContractRef
from .scope import AnalysisScope


@dataclass(frozen=True, slots=True)
class ResolvedAnalysisSource:
    source_id: str
    path: Path
    duration_sec: float
    timeline_id: str
    timeline_revision: int = 1


class AnalysisSourceResolver(Protocol):
    def resolve(self, scope: AnalysisScope) -> tuple[ResolvedAnalysisSource, ...]: ...

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource: ...


@dataclass(frozen=True, slots=True)
class StaticAnalysisSourceResolver:
    sources_by_scope: dict[str, tuple[ResolvedAnalysisSource, ...]]
    sources_by_ref: dict[str, ResolvedAnalysisSource]

    def resolve(self, scope: AnalysisScope) -> tuple[ResolvedAnalysisSource, ...]:
        try:
            return self.sources_by_scope[scope.scope_id]
        except KeyError as error:
            raise LookupError(
                f"no analysis source for scope {scope.scope_id!r}"
            ) from error

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource:
        try:
            return self.sources_by_ref[input_ref.ref]
        except KeyError as error:
            raise LookupError(
                f"no analysis source for ref {input_ref.ref!r}"
            ) from error
