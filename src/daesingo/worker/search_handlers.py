"""RT-10 public Search invocations; no provider, Recording or Case internals.

Media resources are supplied as an execution-scoped context manager. Omitting
that capability leaves both media kinds unregistered, never fixture-backed.
Usage finalization belongs to the existing Worker post-T1 reconciliation.
"""

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass, field
from typing import Protocol, cast

from pydantic import TypeAdapter
from sqlalchemy.exc import SQLAlchemyError

from daesingo import search
from daesingo.recording import RecordingCapabilityError
from daesingo.common.db.errors import (BeforeCommitFailure, CommitOutcomeUnknown,
    TransactionBoundaryError, TransactionRetryExhausted)
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.produced import ProducedObject
from daesingo.common.usage.port import UsageError
from daesingo.search.runs import RunOutcome
from daesingo.worker.registry import KindRegistry

SEARCH_KINDS = frozenset({"HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"})


class SearchFailures(Protocol):
    """Search-owned public helper surface, not a Runtime taxonomy."""

    def failure_kind_for_run(self, run) -> str | None: ...
    def failure_kind_for_intent(self, result) -> str | None: ...
    def failure_kind_for_error(self, error: BaseException) -> str | None: ...


def _public_failures() -> SearchFailures | None:
    # #403 is an explicit dependency. Do not copy its rules or invoke a provider
    # while the installed Search package lacks its public failure capability.
    names = ("failure_kind_for_run", "failure_kind_for_intent", "failure_kind_for_error")
    return cast(SearchFailures, search) if all(callable(getattr(search, name, None)) for name in names) else None


def _public_call(call, failures: SearchFailures):
    """The try block contains only one Search public capability invocation."""
    try:
        return call()
    except (UsageError, CancellationRequested, SQLAlchemyError, BeforeCommitFailure,
            CommitOutcomeUnknown, TransactionBoundaryError, TransactionRetryExhausted):
        raise
    except Exception as error:
        kind = failures.failure_kind_for_error(error)
        if kind is None:
            raise
        return HandlerResult(status="FAILED", failure_kind=kind)


@dataclass(frozen=True)
class SearchInput:
    description: str | None = None
    prior_hints: Mapping[str, str | None] | None = None
    scope: search.AnalysisScope | None = None
    candidate: search.CandidateEvent | None = None
    case_id: str | None = None
    video_stream_refs: tuple[str, ...] = ()
    # FINE_VERIFY only: Case-fixed per-candidate bound from observation_input (#407 decision (a)).
    max_latency_sec: float | None = None
    checkpoint: Callable[[], None] = field(default=lambda: None, repr=False, compare=False)


def search_registry(
    *, load: Callable[[ExecutionContext], SearchInput],
    intent_factory: Callable[[], search.IntentHintExtractor],
    service_factory: Callable[[SearchInput], AbstractContextManager[search.SearchService]] | None = None,
    failures: SearchFailures | None = None,
) -> KindRegistry:
    """One immutable registry. Factories must release execution resources on exit."""
    failures = failures if failures is not None else _public_failures()
    if failures is None:
        return KindRegistry({})

    def invoke(context: ExecutionContext) -> HandlerResult:
        if context.usage_sink is None:
            raise ValueError("execution UsageSink required")
        context.checkpoint()
        data = load(context)
        context.checkpoint()
        if context.kind == "HINT_EXTRACT":
            extractor = intent_factory()
            context.checkpoint()
            result = _public_call(lambda: extractor.extract(data.description or "", case_id=context.case_id,
                prior_hints=data.prior_hints, usage_sink=context.usage_sink), failures)
            context.checkpoint()
            if isinstance(result, HandlerResult):
                return result
            # SearchLedger usage is not the authoritative Runtime UsageRecord.
            payload = TypeAdapter(type(result)).dump_python(result, mode="json", exclude={"usage"})
            failed = result.status == search.IntentHintStatus.FAILED
            return HandlerResult(status="FAILED" if failed else "SUCCEEDED",
                failure_kind=failures.failure_kind_for_intent(result),
                objects=(ProducedObject(kind="intent_hint_result", payload=payload),))

        if data.scope is None or service_factory is None:
            raise ValueError("Search scope and media capability required")
        with ExitStack() as resources:
            # Recording preparation happens while entering this resource. Catch
            # only the agreed capability failure, never Search/body/exit errors.
            try:
                service = resources.enter_context(service_factory(data))
            except RecordingCapabilityError as error:
                context.checkpoint()
                if error.code != "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED":
                    raise
                return HandlerResult(status="FAILED",
                    failure_kind="RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED")
            context.checkpoint()
            if context.kind == "COARSE_SEARCH":
                result = _public_call(lambda: search.search_candidates(data.scope, service=service,
                    usage_sink=context.usage_sink), failures)
                context.checkpoint()
                if isinstance(result, HandlerResult):
                    return result
                payload = {"outcome": str(result.analysis_run.outcome),
                           "analysis_run": result.analysis_run.model_dump(mode="json"),
                           "candidate_events": [c.model_dump(mode="json") for c in result.candidates]}
            else:
                if data.candidate is None:
                    raise ValueError("fixed candidate required")
                # No fallback to the Coarse scope bound: Case owns the Fine bound.
                if data.max_latency_sec is None:
                    raise ValueError("Case-fixed Fine max_latency_sec required")
                sources = _public_call(lambda: service.resolver.resolve(data.scope), failures)
                context.checkpoint()
                if isinstance(sources, HandlerResult):
                    return sources
                if len(sources) != 1:
                    raise ValueError("exactly one analysis source required")
                event_type = data.candidate.event_type_hint
                if event_type is None:
                    if len(data.scope.target_event_types) != 1:
                        raise ValueError("explicit Fine event type required")
                    event_type = data.scope.target_event_types[0]
                source_ref = sources[0].source_ref
                result = _public_call(lambda: search.verify_visual(source_ref, data.scope.hint,
                    service=service, candidate=data.candidate, event_type=event_type,
                    max_latency_sec=data.max_latency_sec, usage_sink=context.usage_sink), failures)
                context.checkpoint()
                if isinstance(result, HandlerResult):
                    return result
                payload = result.model_dump(mode="json")
        context.checkpoint()
        run = result.analysis_run
        failed = run.outcome == RunOutcome.FAILED
        return HandlerResult(status="FAILED" if failed else "SUCCEEDED",
            failure_kind=failures.failure_kind_for_run(run),
            produced=({"kind": "analysis_run", "ref": run.run_id},),
            objects=(ProducedObject(kind="analysis_run", ref=run.run_id, payload=payload),))

    kinds = SEARCH_KINDS if service_factory is not None else {"HINT_EXTRACT"}
    return KindRegistry({kind: invoke for kind in kinds})
