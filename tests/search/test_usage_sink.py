"""UsageSink(#303) — provider HTTP 시도마다 begin → HTTP → finish 1회씩.

가짜 openai 모듈로 GeminiProvider를 돌린다 — 네트워크에 닿지 않는다.
sink 인자는 Runtime `DurableUsageSink`의 검증을 그대로 거친다(DB 쓰기만 생략).
"""

import importlib
import sys
from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from daesingo.common.usage.port import UsagePersistenceError
from daesingo.common.usage.sink import DurableUsageSink
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.intent import IntentHintExtraction, IntentHintExtractor
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import CoarseRequest, GeminiProvider, UsageBinding
from daesingo.search.runs import ContractRef, RunOutcome
from daesingo.search.schemas import CoarseResponse
from daesingo.search.smoke_errors import ProviderPayloadError
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
from tests.search._openai_fake import RawResponseFake
from tests.search._search_service_support import OpenableResolver


class _FakeApiError(Exception):
    def __init__(self, message: str = "", *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeBadRequestError(_FakeApiError):
    pass


class _FakeTimeoutError(_FakeApiError):
    pass


_NO_PARSED = object()


@dataclass
class _Completions(RawResponseFake):
    """시도마다 outcomes를 하나씩 소비한다. 예외면 던지고, 아니면 parsed로 돌려준다."""

    outcomes: list[object]
    calls: int = 0

    def parse(self, **_kwargs: object) -> object:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2)
        parsed = None if outcome is _NO_PARSED else outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
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
    setattr(mod, "LengthFinishReasonError", type("LengthFinishReasonError", (Exception,), {}))  # noqa: B010
    setattr(  # noqa: B010
        mod, "ContentFilterFinishReasonError",
        type("ContentFilterFinishReasonError", (Exception,), {}),
    )
    setattr(mod, "APITimeoutError", _FakeTimeoutError)  # noqa: B010
    original = importlib.import_module
    monkeypatch.setattr(
        "daesingo.search.provider.importlib.import_module",
        lambda name: mod if name == "openai" else original(name),
    )
    monkeypatch.setitem(sys.modules, "openai", mod)
    config = GeminiSearchConfig(max_retries=max_retries, retry_base_sec=0.001)
    return GeminiProvider("k", config)


@dataclass
class _RecordingSink:
    """호출을 기록하고, 인자는 Runtime sink 검증에 그대로 넘긴다."""

    fail_begin: bool = False
    fail_finish: bool = False
    begins: list[dict[str, Any]] = field(default_factory=list)
    finishes: list[dict[str, Any]] = field(default_factory=list)
    runtime: DurableUsageSink = field(
        default_factory=lambda: DurableUsageSink(
            execution_ref="exec-1", case_id="case-1", transaction=lambda _callback: None
        )
    )

    def begin(
        self,
        operation: str,
        provider_label: str,
        pricing_context: Mapping[str, Any],
        *,
        usage_id: str | None = None,
        run_ref: Mapping[str, str] | None = None,
        run_ref_reason: str | None = None,
    ) -> str:
        if self.fail_begin:
            raise UsagePersistenceError()
        issued = self.runtime.begin(
            operation,
            provider_label,
            pricing_context,
            usage_id=usage_id,
            run_ref=run_ref,
            run_ref_reason=run_ref_reason,
        )
        self.begins.append(
            {
                "usage_id": issued,
                "operation": operation,
                "run_ref": run_ref,
                "run_ref_reason": run_ref_reason,
            }
        )
        return issued

    def finish(self, usage_id: str, **observed: Any) -> None:
        if self.fail_finish:
            raise UsagePersistenceError(usage_id=usage_id)
        self.runtime.finish(usage_id, **observed)
        self.finishes.append({"usage_id": usage_id, **observed})

    def finalize(
        self,
        usage_id: str,
        *,
        run_ref: Mapping[str, str] | None,
        run_ref_reason: str | None,
    ) -> None:
        raise AssertionError("Search는 finalize하지 않는다(#303)")


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


def _coarse_request(tmp_path: Path, sink: _RecordingSink) -> CoarseRequest:
    return CoarseRequest(
        _source(),
        (VisualEventType.SIGNAL,),
        media=_media(tmp_path),
        usage=UsageBinding(sink, "CANDIDATE_SEARCH", "run_x", 5.0),
    )


def test_each_http_attempt_gets_one_begin_and_one_finish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rate_limited = _FakeApiError("rate", status_code=429)
    completions = _Completions(
        [rate_limited, rate_limited, CoarseResponse(candidates=())]
    )
    sink = _RecordingSink()
    request = _coarse_request(tmp_path, sink)

    _ = _provider(monkeypatch, completions, max_retries=2).search_coarse(request)

    assert completions.calls == 3
    assert len(sink.begins) == len(sink.finishes) == 3
    assert request.usage is not None
    assert request.usage.issued == [b["usage_id"] for b in sink.begins]
    assert [f["usage_id"] for f in sink.finishes] == request.usage.issued
    assert [f["outcome"] for f in sink.finishes] == ["FAILED", "FAILED", "SUCCEEDED"]
    assert [f["failure_kind"] for f in sink.finishes] == [
        "_FakeApiError",
        "_FakeApiError",
        None,
    ]
    assert [f["token_usage"] for f in sink.finishes] == [
        None,
        None,
        {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
    ]
    assert all(
        b["run_ref"] == {"kind": "analysis_run", "ref": "run_x"}
        and b["run_ref_reason"] is None
        and b["operation"] == "CANDIDATE_SEARCH"
        for b in sink.begins
    )


def test_begin_failure_sends_no_http_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Completions([CoarseResponse(candidates=())])
    sink = _RecordingSink(fail_begin=True)

    with pytest.raises(UsagePersistenceError):
        _ = _provider(monkeypatch, completions, max_retries=2).search_coarse(
            _coarse_request(tmp_path, sink)
        )

    assert completions.calls == 0


def test_finish_failure_does_not_call_provider_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Completions([_FakeApiError("rate", status_code=429)] * 3)
    sink = _RecordingSink(fail_finish=True)

    with pytest.raises(UsagePersistenceError):
        _ = _provider(monkeypatch, completions, max_retries=2).search_coarse(
            _coarse_request(tmp_path, sink)
        )

    assert completions.calls == 1


def test_parse_failure_finishes_failed_with_observed_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sink = _RecordingSink()

    with pytest.raises(Exception, match="no parsed content"):
        _ = _provider(monkeypatch, _Completions([_NO_PARSED])).search_coarse(
            _coarse_request(tmp_path, sink)
        )

    (finish,) = sink.finishes
    assert finish["outcome"] == "FAILED"
    assert finish["failure_kind"] == "ProviderPayloadError"
    assert finish["token_usage"] == {
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
    }


_TOKENS_10_2_12 = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}


def _real_sdk_provider(
    monkeypatch: pytest.MonkeyPatch, content: str, usage: object
) -> tuple[GeminiProvider, list[object]]:
    """실제 OpenAI SDK에 모의 HTTP 200을 물린 provider. 보낸 요청을 함께 돌려준다."""
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx")
    requests: list[object] = []

    def respond(request: object) -> object:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": usage,
            },
        )

    mod = ModuleType("openai")
    setattr(  # noqa: B010
        mod,
        "OpenAI",
        lambda **kw: openai.OpenAI(
            **kw, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        ),
    )
    original = importlib.import_module
    monkeypatch.setattr(
        "daesingo.search.provider.importlib.import_module",
        lambda name: mod if name == "openai" else original(name),
    )
    return GeminiProvider("k", GeminiSearchConfig(max_retries=0)), requests


_USAGE_10_2_12 = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
_STRING_USAGE = {"prompt_tokens": "10", "completion_tokens": "2", "total_tokens": "12"}
_EMPTY_COARSE = '{"candidates": []}'


@pytest.mark.parametrize(
    "content",
    ["not json", '{"candidates": "not-a-list"}'],
    ids=["invalid-json", "schema-violation"],
)
def test_real_sdk_parse_failure_keeps_response_token_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str
) -> None:
    """실제 SDK는 parse() 안에서 JSON · schema 검증 예외를 던진다 — 그래도 usage를 남긴다."""
    provider, requests = _real_sdk_provider(monkeypatch, content, _USAGE_10_2_12)
    sink = _RecordingSink()

    with pytest.raises(ProviderPayloadError):
        _ = provider.search_coarse(_coarse_request(tmp_path, sink))

    assert len(requests) == 1
    assert len(sink.begins) == 1
    (finish,) = sink.finishes
    assert finish["outcome"] == "FAILED"
    assert finish["token_usage"] == _TOKENS_10_2_12


def test_real_sdk_numeric_string_usage_is_normalized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider, requests = _real_sdk_provider(monkeypatch, _EMPTY_COARSE, _STRING_USAGE)
    sink = _RecordingSink()

    result = provider.search_coarse(_coarse_request(tmp_path, sink))

    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 2
    assert len(requests) == 1
    assert len(sink.begins) == 1
    (finish,) = sink.finishes
    assert finish["outcome"] == "SUCCEEDED"
    assert finish["token_usage"] == _TOKENS_10_2_12


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": "abc", "completion_tokens": [1], "total_tokens": None},
        {"prompt_tokens": -1, "completion_tokens": 2.5, "total_tokens": True},
        "weird",
    ],
    ids=["garbage-values", "negative-fraction", "not-an-object"],
)
def test_real_sdk_unexpected_usage_still_finishes_without_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, usage: object
) -> None:
    provider, _requests = _real_sdk_provider(monkeypatch, _EMPTY_COARSE, usage)
    sink = _RecordingSink()

    _ = provider.search_coarse(_coarse_request(tmp_path, sink))

    (finish,) = sink.finishes
    assert finish["outcome"] == "SUCCEEDED"
    assert finish["token_usage"] is None


def test_unpriced_cost_is_none_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sink = _RecordingSink()

    _ = _provider(
        monkeypatch, _Completions([CoarseResponse(candidates=())])
    ).search_coarse(_coarse_request(tmp_path, sink))

    (finish,) = sink.finishes
    assert finish["cost"] == {"amount": None, "currency": "KRW"}


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


def _coarse_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    completions: _Completions | GeminiProvider,
    max_retries: int = 0,
) -> Callable[[_RecordingSink | None], Any]:
    source = _source()
    resolver = StaticAnalysisSourceResolver(
        {"scope-usage-1": (source,)}, {"clip-usage-1": source}
    )
    service = SearchService(
        OpenableResolver(resolver),
        completions
        if isinstance(completions, GeminiProvider)
        else _provider(monkeypatch, completions, max_retries=max_retries),
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
    return lambda sink: service.search_candidates(scope, usage_sink=sink).analysis_run


def test_coarse_run_usage_refs_are_the_issued_usage_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rate_limited = _FakeApiError("rate", status_code=429)
    search = _coarse_service(
        monkeypatch,
        tmp_path,
        _Completions([rate_limited, CoarseResponse(candidates=())]),
        max_retries=1,
    )
    sink = _RecordingSink()

    run = search(sink)

    assert run.outcome is RunOutcome.SUCCEEDED
    assert run.usage_refs == tuple(b["usage_id"] for b in sink.begins)
    assert len(run.usage_refs) == 2
    assert all(
        b["run_ref"] == {"kind": "analysis_run", "ref": run.run_id} for b in sink.begins
    )
    assert all(f["processed_duration_sec"] == 5.0 for f in sink.finishes)


@pytest.mark.parametrize("with_sink", [True, False], ids=["sink", "no-sink"])
def test_real_sdk_string_usage_coarse_run_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, with_sink: bool
) -> None:
    provider, _requests = _real_sdk_provider(monkeypatch, _EMPTY_COARSE, _STRING_USAGE)
    search = _coarse_service(monkeypatch, tmp_path, provider)
    sink = _RecordingSink() if with_sink else None

    run = search(sink)

    assert run.outcome is RunOutcome.SUCCEEDED
    if sink is not None:
        (finish,) = sink.finishes
        assert finish["token_usage"] == _TOKENS_10_2_12
        assert run.usage_refs == (sink.begins[0]["usage_id"],)


def test_failed_coarse_run_still_links_issued_usage_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    search = _coarse_service(
        monkeypatch, tmp_path, _Completions([_FakeApiError("boom", status_code=400)])
    )
    sink = _RecordingSink()

    run = search(sink)

    assert run.outcome is RunOutcome.FAILED
    assert run.usage_refs == (sink.begins[0]["usage_id"],)


def test_usage_error_propagates_instead_of_failed_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Completions([CoarseResponse(candidates=())])
    search = _coarse_service(monkeypatch, tmp_path, completions)

    with pytest.raises(UsagePersistenceError):
        _ = search(_RecordingSink(fail_begin=True))

    assert completions.calls == 0


def _extraction() -> IntentHintExtraction:
    return IntentHintExtraction(
        time_hint="19시",
        vehicle_hint=None,
        situation_hint=None,
        location_hint=None,
        correction_target=None,
        confidence="high",
        reasoning="근거",
    )


def test_intent_call_is_direct_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(monkeypatch, _Completions([_extraction()]))
    sink = _RecordingSink()

    _ = IntentHintExtractor(provider, GeminiSearchConfig()).extract(
        "19시였어요", case_id="c1", usage_sink=sink
    )

    (begin,) = sink.begins
    assert begin["run_ref"] is None
    assert begin["run_ref_reason"] == "DIRECT_NO_RUN"
    assert begin["operation"] == "HINT_EXTRACT"
    (finish,) = sink.finishes
    assert finish["outcome"] == "SUCCEEDED"


def test_intent_usage_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _Completions([_extraction()])
    provider = _provider(monkeypatch, completions)

    with pytest.raises(UsagePersistenceError):
        _ = IntentHintExtractor(provider, GeminiSearchConfig()).extract(
            "19시였어요", case_id="c1", usage_sink=_RecordingSink(fail_begin=True)
        )

    assert completions.calls == 0
