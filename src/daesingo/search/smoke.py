import time
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from . import search_candidates, verify_visual
from .config import GeminiSearchConfig
from .errors import (
    CandidateSourceMismatchError,
    InvalidCoarseSpanError,
    InvalidFineSpanError,
)
from .execution import RunDeadline
from .media import MediaInput, MediaPreparer, PreparedMedia
from .provider import GeminiProvider, ProviderRuntimeOptions
from .runs import ContractRef
from .scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from .service import SearchService
from .smoke_errors import SmokeProviderError
from .smoke_fixture import SmokeFixtureProvider, SmokeProviderFixture
from .smoke_models import (
    SmokeFailureStage,
    SmokeReport,
    SmokeStatus,
    SmokeUsage,
)
from .smoke_report import SmokeOutcome, SmokeReportBuilder
from .sources import LocalAnalysisSourceResolver, ResolvedAnalysisSource


class _FixtureMediaPreparer:
    """Fake preparer for fixture smoke runs — no ffprobe, declared duration used as-is."""

    def __init__(self, duration_sec: float) -> None:
        self._duration_sec = duration_sec

    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]:
        return self._ctx(self._duration_sec)

    def prepare_fine(
        self,
        media_input: MediaInput,
        fine_start_sec: float,
        fine_end_sec: float,
        deadline: RunDeadline,
    ) -> AbstractContextManager[PreparedMedia]:
        return self._ctx(fine_end_sec - fine_start_sec, fine_start_sec, fine_end_sec)

    @contextmanager
    def _ctx(
        self,
        duration_sec: float,
        origin_start_sec: float = 0.0,
        origin_end_sec: float | None = None,
    ) -> Generator[PreparedMedia]:
        yield PreparedMedia(
            path=Path("fixture-media.mp4"),
            content_type="video/mp4",
            byte_size=0,
            duration_sec=duration_sec,
            origin_start_sec=origin_start_sec,
            origin_end_sec=origin_end_sec if origin_end_sec is not None else duration_sec,
        )


@dataclass(frozen=True, slots=True)
class SmokeRunOptions:
    source: Path
    duration_sec: float
    event_types: tuple[VisualEventType, ...]
    timeout_sec: float
    max_cost_usd: Decimal


def input_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_smoke(
    options: SmokeRunOptions,
    service: SearchService,
    config: GeminiSearchConfig,
) -> SmokeReport:
    source_hash = input_sha256(options.source)
    report_builder = SmokeReportBuilder(config, source_hash, service.ledger)
    scope = AnalysisScope(
        scope_id="smoke",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="smoke", revision=1),
                start_ms=0,
                end_ms=round(options.duration_sec * 1000),
            ),
        ),
        target_event_types=options.event_types,
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(
            max_cost_krw=100_000,
            max_latency_sec=max(1, round(options.timeout_sec)),
        ),
        contract_version="1.1.0",
    )
    try:
        coarse = search_candidates(scope, service=service)
    except (SmokeProviderError, InvalidCoarseSpanError):
        return report_builder.build(
            SmokeOutcome(SmokeStatus.FAILED, SmokeFailureStage.COARSE)
        )
    if not coarse.candidates:
        return report_builder.build(
            SmokeOutcome(SmokeStatus.FAILED, SmokeFailureStage.NO_CANDIDATES)
        )
    selected = max(
        coarse.candidates,
        key=lambda candidate: (candidate.ranking_score, -candidate.rank),
    )
    coarse_usage = report_builder.usage()
    stage = _budget_failure(coarse_usage, options)
    if stage is not None:
        return report_builder.build(
            SmokeOutcome(
                SmokeStatus.FAILED,
                stage,
                coarse.candidates,
                selected,
            )
        )
    event_type = selected.event_type_hint or options.event_types[0]
    try:
        fine = verify_visual(
            ContractRef(kind="analysis_source", ref="smoke"),
            service=service,
            event_type=event_type,
            candidate=selected,
        )
    except (
        SmokeProviderError,
        CandidateSourceMismatchError,
        InvalidFineSpanError,
    ):
        return report_builder.build(
            SmokeOutcome(
                SmokeStatus.FAILED,
                SmokeFailureStage.FINE,
                coarse.candidates,
                selected,
            )
        )
    stage = _budget_failure(report_builder.usage(), options)
    if stage is not None:
        return report_builder.build(
            SmokeOutcome(
                SmokeStatus.FAILED,
                stage,
                coarse.candidates,
                selected,
            )
        )
    return report_builder.build(
        SmokeOutcome(
            SmokeStatus.SUCCEEDED,
            candidates=coarse.candidates,
            selected=selected,
            fine=fine,
        )
    )


def build_smoke_service(
    options: SmokeRunOptions,
    api_key: str | None,
    fixture: SmokeProviderFixture | None,
) -> tuple[SearchService, GeminiSearchConfig]:
    ref = ContractRef(kind="analysis_source", ref="smoke")
    source = ResolvedAnalysisSource(ref, options.duration_sec, "smoke", 1)
    resolver = LocalAnalysisSourceResolver(
        {"smoke": (source,)}, {"smoke": source}, {"smoke": options.source}
    )
    if fixture is not None:
        config = GeminiSearchConfig(
            model=fixture.model,
            max_retries=1,
            input_usd_per_million=0.75,
            output_usd_per_million=3.75,
        )
        return (
            SearchService(
                resolver,
                SmokeFixtureProvider(fixture),
                config,
                _FixtureMediaPreparer(options.duration_sec),
                RunDeadline(time.monotonic, round(options.timeout_sec * 1000)),
            ),
            config,
        )
    if api_key is None:
        raise MissingSmokeApiKeyError
    config = replace(GeminiSearchConfig.from_dotenv(), max_retries=1)
    provider = GeminiProvider(
        api_key,
        config,
        runtime=ProviderRuntimeOptions(request_timeout_sec=options.timeout_sec),
    )
    return (
        SearchService(
            resolver,
            provider,
            config,
            MediaPreparer(config),
            RunDeadline(time.monotonic, round(options.timeout_sec * 1000)),
        ),
        config,
    )


class MissingSmokeApiKeyError(Exception):
    pass


def failed_input_report(model: str = "unavailable") -> SmokeReport:
    return SmokeReport(
        status=SmokeStatus.FAILED,
        failure_stage=SmokeFailureStage.INPUT,
        model=model,
        config_fingerprint=sha256(b"").hexdigest(),
        input_sha256=sha256(b"").hexdigest(),
        coarse_candidates=(),
        selected_candidate=None,
        fine_result=None,
        usage=SmokeUsage(
            latency_ms=0,
            input_tokens=None,
            output_tokens=None,
            thought_tokens=None,
            total_tokens=None,
            cost_usd=None,
        ),
    )


def _budget_failure(
    usage: SmokeUsage, options: SmokeRunOptions
) -> SmokeFailureStage | None:
    if usage.latency_ms > options.timeout_sec * 1000:
        return SmokeFailureStage.TIME_BUDGET
    if usage.cost_usd is None:
        return SmokeFailureStage.BUDGET_UNAVAILABLE
    if usage.cost_usd > options.max_cost_usd:
        return SmokeFailureStage.COST_BUDGET
    return None
