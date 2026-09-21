import io
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import CandidateSourceMismatchError
from daesingo.search.execution import DeadlineExceededError, RunDeadline
from daesingo.search.fine import verify_fine
from daesingo.search.ledger import SearchLedger
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import (
    CandidateEvent,
    CandidateId,
    CandidateSpan,
    ContractRef,
    RunId,
)
from daesingo.search.schemas import CoarseResponse, FineResponse, FineTemporalFact
from daesingo.search.scope import AnalysisScope, SearchHint, VisualEventType
from daesingo.search.smoke_errors import ProviderPayloadError
from daesingo.search.sources import ResolvedAnalysisSource
from daesingo.search.usage import ProviderUsage


def _response() -> FineResponse:
    return FineResponse.model_validate(
        {
            "verification": "UNCERTAIN",
            "visual_event_type": None,
            "target": {
                "association_status": "AMBIGUOUS",
                "described_as": None,
                "match_with_hint": None,
                "association_confidence": None,
                "track_ref": None,
                "evidence_refs": [],
            },
            "primitives": [],
            "temporal_facts": [],
            "uncertainties": [],
        }
    )


@dataclass(slots=True)
class _Provider:
    requests: list[FineRequest] = field(default_factory=list)
    response: FineResponse = field(default_factory=_response)
    failure: BaseException | None = None

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        _ = request
        raise NotImplementedError

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return ProviderResult(self.response, ProviderUsage(10, 2, 0, 12), 15)


@dataclass(slots=True)
class _Resolver:
    source: ResolvedAnalysisSource
    resolved_refs: list[ContractRef] = field(default_factory=list)
    opened_refs: list[ContractRef] = field(default_factory=list)

    def resolve(self, scope: AnalysisScope) -> tuple[ResolvedAnalysisSource, ...]:
        _ = scope
        return (self.source,)

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource:
        self.resolved_refs.append(input_ref)
        return self.source

    @contextmanager
    def open_source(self, ref: ContractRef) -> Generator[MediaInput]:
        self.opened_refs.append(ref)
        stream = io.BytesIO(b"original")
        try:
            yield MediaInput(stream, "video/mp4", 8)
        finally:
            stream.close()


@dataclass(slots=True)
class _Clock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def expire(self) -> None:
        self.now = 31.0


@dataclass(slots=True)
class _Preparer:
    prepared: PreparedMedia
    calls: list[tuple[float, float, RunDeadline]] = field(default_factory=list)
    exited: bool = False
    clock_to_expire: _Clock | None = None

    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]:
        _ = media_input, deadline
        raise NotImplementedError

    @contextmanager
    def prepare_fine(
        self,
        media_input: MediaInput,
        start_sec: float,
        end_sec: float,
        deadline: RunDeadline,
    ) -> Generator[PreparedMedia]:
        assert media_input.stream.read() == b"original"
        self.calls.append((start_sec, end_sec, deadline))
        try:
            if self.clock_to_expire is not None:
                self.clock_to_expire.expire()
            yield self.prepared
        finally:
            self.exited = True


def _candidate() -> CandidateEvent:
    return CandidateEvent(
        candidate_id=CandidateId("candidate-fine"),
        run_id=RunId("run-coarse"),
        span=CandidateSpan(
            timeline_id="timeline-fine",
            timeline_revision=2,
            start_ms=2_000,
            end_ms=6_000,
            representative_ms=4_000,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="signal",
        uncertainties=(),
        thumbnail_ref=None,
    )


def test_fine_characterization_preserves_source_ref_and_padded_interval(
    tmp_path: Path,
) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    source = ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2)
    resolver = _Resolver(source)
    provider = _Provider()
    prepared_path = tmp_path / "characterization.mp4"
    prepared_path.write_bytes(b"prepared")
    preparer = _Preparer(PreparedMedia(prepared_path, "video/mp4", 8, 7.0, 0.5, 7.5))

    # When
    result = verify_fine(
        source_ref,
        _candidate(),
        SearchHint(vehicle=None, free_text=None),
        VisualEventType.SIGNAL,
        resolver,
        provider,
        GeminiSearchConfig(fine_padding_sec=1.5),
        SearchLedger(),
        preparer,
        RunDeadline(lambda: 0.0, budget_ms=30_000),
    )

    # Then
    assert (provider.requests[0].start_sec, provider.requests[0].end_sec) == (0.5, 7.5)
    assert result.analysis_run.input_ref == source_ref
    assert result.visual_evidence.input_ref == source_ref


def test_fine_prepares_only_selected_source_and_rebases_transport_offset(
    tmp_path: Path,
) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    source = ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2)
    resolver = _Resolver(source)
    prepared_path = tmp_path / "prepared.mp4"
    prepared_path.write_bytes(b"prepared")
    prepared = PreparedMedia(prepared_path, "video/mp4", 8, 7.0, 0.5, 7.5)
    preparer = _Preparer(prepared)
    response = _response().model_copy(
        update={
            "temporal_facts": (
                FineTemporalFact(at_offset_ms=3_500, fact="EVENT", evidence_refs=()),
                FineTemporalFact(
                    at_offset_ms=None, fact="UNKNOWN_TIME", evidence_refs=()
                ),
            )
        }
    )
    provider = _Provider(response=response)
    ledger = SearchLedger()
    deadline = RunDeadline(lambda: 0.0, budget_ms=30_000)

    # When
    result = verify_fine(
        source_ref,
        _candidate(),
        None,
        VisualEventType.SIGNAL,
        resolver,
        provider,
        GeminiSearchConfig(
            fine_padding_sec=1.5,
            input_usd_per_million=1_000_000,
            output_usd_per_million=2_000_000,
        ),
        ledger,
        preparer,
        deadline,
    )

    # Then
    assert resolver.resolved_refs == [source_ref]
    assert resolver.opened_refs == [source_ref]
    assert preparer.calls == [(0.5, 7.5, deadline)]
    assert len(provider.requests) == 1
    assert provider.requests[0].media is prepared
    assert provider.requests[0].timeout_sec == 30.0
    assert result.analysis_run.input_ref == source_ref
    assert result.visual_evidence.input_ref == source_ref
    assert [fact.at_offset_ms for fact in result.visual_evidence.temporal_facts] == [
        4_000,
        None,
    ]
    record = ledger.records()[0]
    assert record.processed_duration_sec == 10.0
    assert record.prepared_media_bytes == 8
    assert record.prepared_duration_ms == 7_000
    assert str(record.cost_usd) == "14"
    assert preparer.exited


@pytest.mark.parametrize("offset_ms", [-1, 7_001])
def test_fine_rejects_transport_offsets_outside_prepared_clip(
    tmp_path: Path, offset_ms: int
) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    source = ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2)
    resolver = _Resolver(source)
    path = tmp_path / "prepared.mp4"
    path.write_bytes(b"prepared")
    preparer = _Preparer(PreparedMedia(path, "video/mp4", 8, 7.0, 0.5, 7.5))
    response = _response().model_copy(
        update={
            "temporal_facts": (
                FineTemporalFact.model_construct(
                    at_offset_ms=offset_ms, fact="EVENT", evidence_refs=()
                ),
            )
        }
    )
    provider = _Provider(response=response)

    # When / Then
    with pytest.raises(ProviderPayloadError):
        verify_fine(
            source_ref,
            _candidate(),
            None,
            VisualEventType.SIGNAL,
            resolver,
            provider,
            GeminiSearchConfig(fine_padding_sec=1.5),
            SearchLedger(),
            preparer,
            RunDeadline(lambda: 0.0, budget_ms=30_000),
        )
    assert preparer.exited


@pytest.mark.parametrize(
    ("prepared", "offset_ms"),
    [
        (
            PreparedMedia(Path("source-upper.mp4"), "video/mp4", 8, 2.0, 9.0, 10.0),
            1_500,
        ),
        (PreparedMedia(Path("window-link.mp4"), "video/mp4", 8, 7.0, 0.5, 7.5), 500),
        (
            PreparedMedia(
                Path("representative-link.mp4"), "video/mp4", 8, 7.0, 0.5, 7.5
            ),
            2_500,
        ),
    ],
)
def test_fine_rejects_rebased_offsets_incompatible_with_source_or_candidate(
    tmp_path: Path, prepared: PreparedMedia, offset_ms: int
) -> None:
    # Given
    path = tmp_path / prepared.path.name
    path.write_bytes(b"prepared")
    bounded_prepared = PreparedMedia(
        path,
        prepared.content_type,
        prepared.byte_size,
        prepared.duration_sec,
        prepared.origin_start_sec,
        prepared.origin_end_sec,
    )
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    resolver = _Resolver(ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2))
    preparer = _Preparer(bounded_prepared)
    provider = _Provider(
        response=_response().model_copy(
            update={
                "temporal_facts": (
                    FineTemporalFact(
                        at_offset_ms=offset_ms, fact="EVENT", evidence_refs=()
                    ),
                )
            }
        )
    )

    # When / Then
    with pytest.raises(ProviderPayloadError):
        verify_fine(
            source_ref,
            _candidate(),
            None,
            VisualEventType.SIGNAL,
            resolver,
            provider,
            GeminiSearchConfig(fine_padding_sec=1.5),
            SearchLedger(),
            preparer,
            RunDeadline(lambda: 0.0, budget_ms=30_000),
        )
    assert preparer.exited


def test_fine_rejects_resolver_result_for_a_different_source_before_open() -> None:
    # Given
    requested_ref = ContractRef(kind="analysis_source", ref="requested")
    resolver = _Resolver(
        ResolvedAnalysisSource(
            ContractRef(kind="analysis_source", ref="different"),
            10.0,
            "timeline-fine",
            2,
        )
    )
    provider = _Provider()

    # When / Then
    with pytest.raises(CandidateSourceMismatchError):
        verify_fine(
            requested_ref,
            _candidate(),
            None,
            VisualEventType.SIGNAL,
            resolver,
            provider,
            GeminiSearchConfig(),
            SearchLedger(),
            _Preparer(PreparedMedia(Path("unused.mp4"), "video/mp4", 8, 7.0, 0.5, 7.5)),
            RunDeadline(lambda: 0.0, budget_ms=30_000),
        )
    assert resolver.opened_refs == []
    assert provider.requests == []


@pytest.mark.parametrize(
    "failure", [RuntimeError("provider failed"), KeyboardInterrupt()]
)
def test_fine_releases_prepared_media_on_provider_failure(
    tmp_path: Path, failure: BaseException
) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    resolver = _Resolver(ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2))
    path = tmp_path / "prepared.mp4"
    path.write_bytes(b"prepared")
    preparer = _Preparer(PreparedMedia(path, "video/mp4", 8, 7.0, 0.5, 7.5))
    provider = _Provider(failure=failure)

    # When / Then
    with pytest.raises(type(failure)):
        verify_fine(
            source_ref,
            _candidate(),
            None,
            VisualEventType.SIGNAL,
            resolver,
            provider,
            GeminiSearchConfig(fine_padding_sec=1.5),
            SearchLedger(),
            preparer,
            RunDeadline(lambda: 0.0, budget_ms=30_000),
        )
    assert preparer.exited


def test_fine_releases_prepared_media_when_deadline_expires_before_provider(
    tmp_path: Path,
) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    resolver = _Resolver(ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2))
    path = tmp_path / "prepared.mp4"
    path.write_bytes(b"prepared")
    clock = _Clock()
    preparer = _Preparer(
        PreparedMedia(path, "video/mp4", 8, 7.0, 0.5, 7.5),
        clock_to_expire=clock,
    )
    provider = _Provider()

    # When / Then
    with pytest.raises(DeadlineExceededError, match="budget"):
        verify_fine(
            source_ref,
            _candidate(),
            None,
            VisualEventType.SIGNAL,
            resolver,
            provider,
            GeminiSearchConfig(fine_padding_sec=1.5),
            SearchLedger(),
            preparer,
            RunDeadline(clock, budget_ms=30_000),
        )
    assert provider.requests == []
    assert preparer.exited
