"""UsageSink(#303) — provider HTTP 시도마다 begin → HTTP → finish 1회씩.

가짜 openai 모듈로 GeminiProvider를 돌린다 — 네트워크에 닿지 않는다.
"""

import importlib
import sys
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from daesingo.search import (
    InMemoryUsageSink,
    UsageAttempt,
    UsageObservation,
    UsagePersistenceError,
)
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.intent import IntentHintExtraction, IntentHintExtractor
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import CoarseRequest, GeminiProvider
from daesingo.search.runs import ContractRef, RunOutcome
from daesingo.search.schemas import CoarseResponse
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
from daesingo.search.sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver
from tests.search._search_service_support import OpenableResolver


class _FakeApiError(Exception):
    def __init__(self, message: str = "", *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeBadRequestError(_FakeApiError):
    pass


@dataclass
class _Completions:
    """시도마다 outcomes를 하나씩 소비한다. 예외면 던지고, 아니면 parsed로 돌려준다."""

    outcomes: list[object]
    calls: int = 0

    def parse(self, **_kwargs: object) -> object:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=outcome))],
            usage=usage,
        )


def _provider(
    monkeypatch: pytest.MonkeyPatch, completions: _Completions, max_retries: int = 0
) -> GeminiProvider:
    mod = ModuleType("openai")
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    setattr(mod, "OpenAI", lambda **_kw: client)  # noqa: B010
    setattr(mod, "APIError", _FakeApiError)  # noqa: B010
    setattr(mod, "BadRequestError", _FakeBadRequestError)  # noqa: B010
    original = importlib.import_module
    monkeypatch.setattr(
        "daesingo.search.provider.importlib.import_module",
        lambda name: mod if name == "openai" else original(name),
    )
    monkeypatch.setitem(sys.modules, "openai", mod)
    config = GeminiSearchConfig(max_retries=max_retries, retry_base_sec=0.001)
    return GeminiProvider("k", config)


@dataclass
class _FailingSink:
    fail_begin: bool = False
    fail_finish: bool = False
    inner: InMemoryUsageSink = field(default_factory=InMemoryUsageSink)

    def begin(self, attempt: UsageAttempt) -> str:
        if self.fail_begin:
            raise OSError("db down")
        return self.inner.begin(attempt)

    def finish(self, usage_id: str, observed: UsageObservation) -> None:
        if self.fail_finish:
            raise OSError("db down")
        self.inner.finish(usage_id, observed)


def _source() -> ResolvedAnalysisSource:
    return ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="clip-usage-1"),
        5.0,
        "clip-usage-1",
        1,
    )


def _media(tmp_path: Path) -> PreparedMedia:
    path = tmp_path / "clip.mp4"
    _ = path.write_bytes(b"fake-video")
    return PreparedMedia(
        path=path,
        content_type="video/mp4",
        byte_size=10,
        duration_sec=5.0,
        origin_start_sec=0.0,
        origin_end_sec=5.0,
    )


def _coarse_request(tmp_path: Path, sink: object) -> CoarseRequest:
    return CoarseRequest(
        _source(),
        (VisualEventType.SIGNAL,),
        media=_media(tmp_path),
        usage_sink=sink,  # pyright: ignore[reportArgumentType]
        run_ref="run_x",
    )


def test_each_http_attempt_gets_one_begin_and_one_finish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rate_limited = _FakeApiError("rate", status_code=429)
    completions = _Completions(
        [rate_limited, rate_limited, CoarseResponse(candidates=())]
    )
    sink = InMemoryUsageSink()

    result = _provider(monkeypatch, completions, max_retries=2).search_coarse(
        _coarse_request(tmp_path, sink)
    )

    entries = sink.entries()
    assert completions.calls == 3
    assert len(entries) == 3
    assert result.usage_ids == tuple(usage_id for usage_id, _, _ in entries)
    observations = [observed for _, _, observed in entries]
    assert all(observed is not None for observed in observations)
    assert [o.succeeded for o in observations if o] == [False, False, True]
    assert [o.token_usage is None for o in observations if o] == [True, True, False]
    attempt = entries[0][1]
    assert attempt.run_ref == "run_x"
    assert attempt.run_ref_reason is None
    assert attempt.operation == "CANDIDATE_SEARCH"
    assert attempt.provider == "elice"


def test_begin_failure_sends_no_http_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Completions([CoarseResponse(candidates=())])
    sink = _FailingSink(fail_begin=True)

    with pytest.raises(UsagePersistenceError):
        _ = _provider(monkeypatch, completions, max_retries=2).search_coarse(
            _coarse_request(tmp_path, sink)
        )

    assert completions.calls == 0


def test_finish_failure_does_not_call_provider_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Completions([_FakeApiError("rate", status_code=429)] * 3)
    sink = _FailingSink(fail_finish=True)

    with pytest.raises(UsagePersistenceError):
        _ = _provider(monkeypatch, completions, max_retries=2).search_coarse(
            _coarse_request(tmp_path, sink)
        )

    assert completions.calls == 1


def test_unpriced_cost_is_none_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sink = InMemoryUsageSink()

    _ = _provider(
        monkeypatch, _Completions([CoarseResponse(candidates=())])
    ).search_coarse(_coarse_request(tmp_path, sink))

    ((_, _, observed),) = sink.entries()
    assert observed is not None
    assert observed.cost.amount is None
    assert observed.cost.currency == "KRW"


class _TmpMediaPreparer:
    def __init__(self, media: PreparedMedia) -> None:
        self._media = media

    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]:
        _ = media_input, deadline
        return self._yield()

    def prepare_fine(
        self,
        media_input: MediaInput,
        fine_start_sec: float,
        fine_end_sec: float,
        deadline: RunDeadline,
    ) -> AbstractContextManager[PreparedMedia]:
        _ = media_input, fine_start_sec, fine_end_sec, deadline
        return self._yield()

    @contextmanager
    def _yield(self) -> Generator[PreparedMedia]:
        yield self._media


def test_coarse_run_usage_refs_are_the_issued_usage_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _source()
    resolver = StaticAnalysisSourceResolver(
        {"scope-usage-1": (source,)}, {"clip-usage-1": source}
    )
    rate_limited = _FakeApiError("rate", status_code=429)
    completions = _Completions([rate_limited, CoarseResponse(candidates=())])
    service = SearchService(
        OpenableResolver(resolver),
        _provider(monkeypatch, completions, max_retries=1),
        GeminiSearchConfig(),
        _TmpMediaPreparer(_media(tmp_path)),
    )
    scope = AnalysisScope(
        scope_id="scope-usage-1",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="clip-usage-1", revision=1),
                start_ms=0,
                end_ms=5_000,
            ),
        ),
        target_event_types=(VisualEventType.SIGNAL,),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
        contract_version="1.1.0",
    )
    sink = InMemoryUsageSink()

    run = service.search_candidates(scope, usage_sink=sink).analysis_run

    assert run.outcome is RunOutcome.SUCCEEDED
    entries = sink.entries()
    assert len(entries) == 2
    assert run.usage_refs == tuple(usage_id for usage_id, _, _ in entries)
    assert all(attempt.run_ref == run.run_id for _, attempt, _ in entries)
    assert all(attempt.operation == "CANDIDATE_SEARCH" for _, attempt, _ in entries)


def test_intent_call_is_direct_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    extraction = IntentHintExtraction(
        time_hint="19시",
        vehicle_hint=None,
        situation_hint=None,
        location_hint=None,
        correction_target=None,
        confidence="high",
        reasoning="근거",
    )
    provider = _provider(monkeypatch, _Completions([extraction]))
    sink = InMemoryUsageSink()

    _ = IntentHintExtractor(provider, GeminiSearchConfig()).extract(
        "19시였어요", case_id="c1", usage_sink=sink
    )

    ((_, attempt, observed),) = sink.entries()
    assert attempt.run_ref is None
    assert attempt.run_ref_reason == "DIRECT_NO_RUN"
    assert attempt.operation == "HINT_EXTRACT"
    assert observed is not None
    assert observed.succeeded
