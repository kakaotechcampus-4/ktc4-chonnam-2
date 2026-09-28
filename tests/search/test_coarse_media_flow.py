from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import CoarseDurationMismatchError
from daesingo.search.execution import RunDeadline
from daesingo.search.media import (
    FfprobeError,
    MediaInput,
    MediaPreparer,
    MediaTooLargeError,
)
from daesingo.search.provider import (
    CoarseRequest,
    FineRequest,
    ProviderResult,
    SearchProvider,
)
from daesingo.search.runs import (
    CandidateSearchResult,
    ContractRef,
    FailureKind,
    RunOutcome,
)
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.service import SearchService
from daesingo.search.sources import ResolvedAnalysisSource
from daesingo.search.usage import ProviderUsage
from tests.search._coarse_media_support import (
    BaselineProvider,
    ControllableClock,
    ExpiringMediaPreparer,
    capture_temp_dirs,
    make_mp4,
    make_source,
)


class _CountingResolver:
    """Mutable test spy that counts source openings and owns the source stream."""

    source: ResolvedAnalysisSource
    path: Path
    open_calls: int
    opened_refs: list[ContractRef]

    def __init__(self, source: ResolvedAnalysisSource, path: Path) -> None:
        self.source = source
        self.path = path
        self.open_calls = 0
        self.opened_refs = []

    def resolve(self, scope: AnalysisScope) -> tuple[ResolvedAnalysisSource, ...]:
        _ = scope
        return (self.source,)

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource:
        _ = input_ref
        return self.source

    @contextmanager
    def open_source(self, ref: ContractRef) -> Generator[MediaInput]:
        self.open_calls += 1
        self.opened_refs.append(ref)
        with self.path.open("rb") as stream:
            yield MediaInput(stream, "video/mp4", self.path.stat().st_size)


class _ProviderSpy:
    """Mutable provider spy retaining only bounded prepared-media observations."""

    failure: BaseException | None
    requests: list[CoarseRequest]
    prepared_bytes: bytes | None
    prepared_path: Path | None

    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.requests = []
        self.prepared_bytes = None
        self.prepared_path = None

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        self.requests.append(request)
        assert request.media is not None
        self.prepared_path = request.media.path
        self.prepared_bytes = request.media.path.read_bytes()
        if self.failure is not None:
            raise self.failure
        return ProviderResult(
            CoarseResponse.model_validate({"candidates": []}),
            ProviderUsage(10, 2, 1, 13),
            15,
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        _ = request
        raise NotImplementedError


def _service(
    resolver: _CountingResolver,
    provider: SearchProvider,
    config: GeminiSearchConfig,
) -> SearchService:
    return SearchService(
        resolver,
        provider,
        config,
        media_preparer=MediaPreparer(config),
        deadline=RunDeadline(lambda: 10.0, budget_ms=30_000),
    )


def _scope() -> AnalysisScope:
    return AnalysisScope(
        scope_id="scope-coarse-flow",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(
                    timeline_id="timeline-coarse-flow", revision=3
                ),
                start_ms=0,
                end_ms=5_000,
            ),
        ),
        target_event_types=(VisualEventType.SIGNAL,),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
        contract_version="1.1.0",
    )


def test_legacy_candidate_result_schema_is_unchanged(tmp_path: Path) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    service = _service(
        _CountingResolver(make_source(), source_path),
        BaselineProvider(),
        GeminiSearchConfig(),
    )

    # When
    result = service.search_candidates(_scope())

    # Then
    assert isinstance(result, CandidateSearchResult)
    assert set(result.model_dump()) == {"analysis_run", "candidates"}


def test_coarse_uses_one_prepared_proxy_and_records_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    original = make_mp4(source_path)
    resolver = _CountingResolver(make_source(), source_path)
    provider = _ProviderSpy()
    config = GeminiSearchConfig(
        input_usd_per_million=2.0,
        output_usd_per_million=4.0,
    )
    temp_dirs = capture_temp_dirs(monkeypatch)
    service = _service(resolver, provider, config)

    # When
    linked = service.search_candidates_linked(_scope())

    # Then
    assert resolver.open_calls == 1
    assert resolver.opened_refs == [resolver.source.source_ref]
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.source.source_ref is resolver.source.source_ref
    assert request.media is not None
    assert provider.prepared_bytes != original
    assert request.timeout_sec == 30.0
    assert linked.source_ref is resolver.source.source_ref
    record = service.ledger.records()[0]
    assert record.processed_duration_sec == pytest.approx(2.0, abs=0.05)
    assert record.prepared_media_bytes == len(provider.prepared_bytes or b"")
    assert record.prepared_duration_ms == pytest.approx(2000, abs=100)
    assert record.cost_usd == Decimal("0.000032")
    assert provider.prepared_path is not None and not provider.prepared_path.exists()
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_coarse_usage_record_keeps_declared_duration_separate_from_prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path, duration_sec=2.0)
    resolver = _CountingResolver(make_source(duration_sec=2.2), source_path)
    temp_dirs = capture_temp_dirs(monkeypatch)
    service = _service(resolver, _ProviderSpy(), GeminiSearchConfig())

    # When
    _ = service.search_candidates_linked(_scope())

    # Then
    record = service.ledger.records()[0]
    assert record.processed_duration_sec == 2.2
    assert record.prepared_duration_ms == 2000
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_deadline_after_preparation_skips_provider_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    resolver = _CountingResolver(make_source(), source_path)
    provider = _ProviderSpy()
    config = GeminiSearchConfig()
    clock = ControllableClock()
    deadline = RunDeadline(clock, budget_ms=30_000)
    temp_dirs = capture_temp_dirs(monkeypatch)
    service = SearchService(
        resolver,
        provider,
        config,
        media_preparer=ExpiringMediaPreparer(config, clock),
        deadline=deadline,
    )

    # When
    result = service.search_candidates(_scope())

    # Then — provider 호출 직전의 deadline 초과는 taxonomy COST로 기록된다.
    (issue,) = result.analysis_run.issues
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert issue.kind is FailureKind.COST
    assert provider.requests == []
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_duration_mismatch_fails_before_provider_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    resolver = _CountingResolver(make_source(duration_sec=2.251), source_path)
    provider = _ProviderSpy()
    temp_dirs = capture_temp_dirs(monkeypatch)

    # When / Then
    with pytest.raises(CoarseDurationMismatchError):
        _ = _service(resolver, provider, GeminiSearchConfig()).search_candidates(
            _scope()
        )
    assert provider.requests == []
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_provider_failure_cleans_prepared_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider 실패는 FAILED run으로 기록되고 임시 파일은 남지 않는다."""
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    provider = _ProviderSpy(RuntimeError("provider failed"))
    temp_dirs = capture_temp_dirs(monkeypatch)

    # When
    result = _service(
        _CountingResolver(make_source(), source_path),
        provider,
        GeminiSearchConfig(),
    ).search_candidates(_scope())

    # Then
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert provider.prepared_path is not None and not provider.prepared_path.exists()
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_keyboard_interrupt_still_propagates_and_cleans_prepared_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BaseException은 삼키지 않는다 — 취소는 실행 실패가 아니다."""
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    provider = _ProviderSpy(KeyboardInterrupt())
    temp_dirs = capture_temp_dirs(monkeypatch)

    # When / Then
    with pytest.raises(KeyboardInterrupt):
        _ = _service(
            _CountingResolver(make_source(), source_path),
            provider,
            GeminiSearchConfig(),
        ).search_candidates(_scope())
    assert provider.prepared_path is not None and not provider.prepared_path.exists()
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_prepared_oversize_uses_typed_error_without_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = make_mp4(source_path)
    provider = _ProviderSpy()
    temp_dirs = capture_temp_dirs(monkeypatch)
    config = GeminiSearchConfig(max_inline_media_bytes=1)

    # When / Then
    with pytest.raises(MediaTooLargeError):
        _ = _service(
            _CountingResolver(make_source(), source_path), provider, config
        ).search_candidates(_scope())
    assert provider.requests == []
    assert temp_dirs and all(not path.exists() for path in temp_dirs)


def test_malformed_media_fails_without_provider_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    source_path = tmp_path / "source.mp4"
    _ = source_path.write_bytes(b"not-an-mp4")
    provider = _ProviderSpy()
    temp_dirs = capture_temp_dirs(monkeypatch)

    # When / Then
    with pytest.raises(FfprobeError):
        _ = _service(
            _CountingResolver(make_source(), source_path),
            provider,
            GeminiSearchConfig(),
        ).search_candidates(_scope())
    assert provider.requests == []
    assert temp_dirs and all(not path.exists() for path in temp_dirs)
