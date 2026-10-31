"""Only production Recording analysis preparation may classify unsupported media."""

from dataclasses import replace
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from daesingo.recording import RecordingCapabilityError, RecordingService
from daesingo.common.db.errors import (
    BeforeCommitFailure,
    CommitOutcomeUnknown,
    TransactionBoundaryError,
    TransactionRetryExhausted,
)
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.usage.port import UsagePersistenceError
from daesingo.common.jobs.execution import validated_terminal
from daesingo.worker.search_handlers import search_registry
from tests.worker.test_production_media import setup_media
from tests.recording.test_local_time_sources import make_media as _make_media
from tests.worker.test_search_handlers import context
from tests.worker.test_search_failure_boundary import Policy

make_media = _make_media


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
def test_production_preparation_unsupported_is_failed_without_search(
    make_media, monkeypatch, tmp_path, kind
):
    factory, data, repo, closes, active = setup_media(make_media, monkeypatch, tmp_path)
    ctx = context(kind, object())
    data = replace(data, checkpoint=ctx.checkpoint)
    calls = []

    def reject(self, resolution, profile):
        calls.append("prepare")
        assert not active
        raise RecordingCapabilityError(
            "UNSUPPORTED_MEDIA", "private filename /path locator video content"
        )

    monkeypatch.setattr(
        RecordingService, "prepare_analysis_source_from_resolution", reject
    )
    monkeypatch.setattr(
        "daesingo.search.build_gemini_search_service",
        lambda *a: pytest.fail("Search built"),
    )
    policy = Policy()
    registry = search_registry(
        load=lambda _: data,
        intent_factory=lambda: pytest.fail("hint"),
        service_factory=factory,
        failures=policy,
    )
    terminal = validated_terminal(registry.dispatch(ctx), execution_id=ctx.execution_id)
    assert terminal.status == "FAILED"
    assert terminal.failure_kind == "RECORDING_UNSUPPORTED_MEDIA"
    assert terminal.produced == terminal.objects == ()
    assert calls == ["prepare"] and len(closes) == 1 and not active
    assert policy.seen == []
    assert not any(
        word in terminal.model_dump_json()
        for word in ("private", "filename", "/path", "locator", "content")
    )


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
@pytest.mark.parametrize(
    "code,want",
    [
        ("UNSUPPORTED_MEDIA", "RECORDING_UNSUPPORTED_MEDIA"),
        (
            "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED",
            "RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED",
        ),
        ("FUTURE_CODE", "RUNTIME_HANDLER_ERROR"),
    ],
)
def test_real_recording_preparation_rejection(
    make_media, monkeypatch, tmp_path, kind, code, want
):
    from daesingo.recording.materialization import LocalAnalysisMaterializer

    factory, data, _, closes, active = setup_media(make_media, monkeypatch, tmp_path)
    calls = []

    def reject(*args):
        assert not active
        calls.append("materialize")
        raise RecordingCapabilityError(code, "private")

    monkeypatch.setattr(LocalAnalysisMaterializer, "materialize", reject)
    monkeypatch.setattr(
        "daesingo.search.build_gemini_search_service", lambda *a: pytest.fail("Search")
    )
    result = search_registry(
        load=lambda _: data,
        intent_factory=lambda: None,
        service_factory=factory,
        failures=Policy(),
    ).dispatch(context(kind, object()))
    assert result.status == "FAILED" and result.failure_kind == want
    assert result.produced == result.objects == ()
    assert calls == ["materialize"] and len(closes) == 1 and not active


@pytest.mark.parametrize(
    "phase",
    [
        "load",
        "factory",
        "open",
        "stream",
        "ownership",
        "resolve",
        "observe",
        "checkpoint",
        "search_config",
        "exit",
    ],
)
def test_same_raw_code_outside_preparation_remains_runtime(
    make_media, monkeypatch, tmp_path, phase
):
    factory, data, _, closes, active = setup_media(make_media, monkeypatch, tmp_path)

    def reject(*args, **kwargs):
        raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "private wrong phase")

    def load(_):
        return data

    if phase == "load":
        load = reject
    elif phase == "factory":
        factory = reject
    elif phase == "open":
        monkeypatch.setattr(
            "daesingo.worker.production_media.build_recording_service", reject
        )
    elif phase == "checkpoint":
        data = replace(data, checkpoint=reject)
    elif phase == "search_config":
        monkeypatch.setattr("daesingo.search.build_gemini_search_service", reject)
    elif phase == "exit":
        original = RecordingService.close

        def close(self):
            original(self)
            reject()

        monkeypatch.setattr(RecordingService, "close", close)
        # Cleanup must override a pending mapped preparation error as well.
        monkeypatch.setattr(
            RecordingService, "prepare_analysis_source_from_resolution", reject
        )
    else:
        monkeypatch.setattr(
            RecordingService,
            {
                "stream": "get_media_stream",
                "ownership": "owns_asset",
                "resolve": "resolve_span",
                "observe": "observe_time_sources",
            }[phase],
            reject,
        )
    result = search_registry(
        load=load,
        intent_factory=lambda: None,
        service_factory=factory,
        failures=Policy(),
    ).dispatch(context("COARSE_SEARCH", object()))
    assert result.failure_kind == "RUNTIME_HANDLER_ERROR" and not result.produced
    assert not active


@pytest.mark.parametrize("phase", ["read", "publish", "materialize"])
@pytest.mark.parametrize(
    "error",
    [
        sa.exc.OperationalError("read", {}, Exception("private")),
        BeforeCommitFailure("private"),
        CommitOutcomeUnknown(),
        TransactionBoundaryError("private"),
        TransactionRetryExhausted(3, outcome_unknown=False),
        TransactionRetryExhausted(3, outcome_unknown=True),
        UsagePersistenceError(),
        CancellationRequested(),
    ],
)
def test_nested_preparation_infrastructure_faults_are_not_mapped(
    make_media, monkeypatch, tmp_path, phase, error
):
    from daesingo.recording.materialization import LocalAnalysisMaterializer

    factory, data, _, closes, active = setup_media(make_media, monkeypatch, tmp_path)
    preparing, injected = [], []
    original_prepare = RecordingService.prepare_analysis_source_from_resolution

    def prepare(self, *args, **kwargs):
        preparing.append(True)
        try:
            return original_prepare(self, *args, **kwargs)
        finally:
            preparing.pop()

    monkeypatch.setattr(
        RecordingService, "prepare_analysis_source_from_resolution", prepare
    )

    def reject(*args, **kwargs):
        assert preparing
        injected.append(True)
        raise error

    if phase == "materialize":
        monkeypatch.setattr(LocalAnalysisMaterializer, "materialize", reject)
    else:
        # Actual public prepare invokes these repository reads/publication calls.
        from daesingo.recording import transactional

        method = "get_timeline" if phase == "read" else "add_prepared_media"
        original = getattr(transactional.MySQLRecordingRepository, method)

        def repository_call(*args, **kwargs):
            if preparing:
                reject()
            return original(*args, **kwargs)

        monkeypatch.setattr(
            transactional.MySQLRecordingRepository, method, repository_call
        )
    registry = search_registry(
        load=lambda _: data,
        intent_factory=lambda: None,
        service_factory=factory,
        failures=Policy(),
    )
    if isinstance(error, (UsagePersistenceError, CancellationRequested)):
        with pytest.raises(type(error)):
            registry.dispatch(context("COARSE_SEARCH", object()))
    else:
        assert (
            registry.dispatch(context("COARSE_SEARCH", object())).failure_kind
            == "RUNTIME_HANDLER_ERROR"
        )
    assert injected == [True] and len(closes) == 1 and not active


@pytest.mark.parametrize("phase", ["prepare", "close"])
def test_cancellation_after_preparation_rejection_wins(
    make_media, monkeypatch, tmp_path, phase
):
    factory, data, _, closes, active = setup_media(make_media, monkeypatch, tmp_path)
    ctx = context("COARSE_SEARCH", object())
    data = replace(data, checkpoint=ctx.checkpoint)

    def reject(*args):
        if phase == "prepare":
            ctx.cancel_signal.request()
        raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "private")

    monkeypatch.setattr(
        RecordingService, "prepare_analysis_source_from_resolution", reject
    )
    if phase == "close":
        original = RecordingService.close

        def close(self):
            original(self)
            ctx.cancel_signal.request()

        monkeypatch.setattr(RecordingService, "close", close)
    registry = search_registry(
        load=lambda _: data,
        intent_factory=lambda: None,
        service_factory=factory,
        failures=Policy(),
    )
    with pytest.raises(CancellationRequested):
        registry.dispatch(ctx)
    assert len(closes) == 1 and not active


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_search_or_hint_unsupported_is_not_recording_preparation(kind):
    from tests.worker.test_search_failure_boundary import compose

    policy = Policy()  # Search declines classification; Runtime owns the error.
    ctx = context(kind, object())
    error = RecordingCapabilityError("UNSUPPORTED_MEDIA", "private provider")
    registry, _ = compose(ctx, policy, error=error)
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert policy.seen == [("error", error)]


def test_unmarked_factory_unsupported_is_not_preparation():
    from tests.worker.test_search_handlers import fixtures
    from daesingo.worker.search_handlers import SearchInput

    scope, _, _ = fixtures()

    @contextmanager
    def factory(data):
        raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "private setup")
        yield SimpleNamespace()

    registry = search_registry(
        load=lambda _: SearchInput(scope=scope),
        intent_factory=lambda: None,
        service_factory=factory,
        failures=Policy(),
    )
    assert (
        registry.dispatch(context("COARSE_SEARCH", object())).failure_kind
        == "RUNTIME_HANDLER_ERROR"
    )
