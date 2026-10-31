from contextlib import contextmanager

import pytest

from daesingo.recording import RecordingCapabilityError
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.worker.search_handlers import SearchInput, search_registry
from tests.worker.test_search_handlers import context, fixtures
from tests.worker.test_search_failure_boundary import Policy


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
def test_recording_prepare_limit_is_terminal_without_provider_or_receipt(kind):
    scope, _, _ = fixtures()
    ctx = context(kind, object())
    events = []
    @contextmanager
    def media(data):
        try:
            raise RecordingCapabilityError("ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED", "private diagnostic")
            yield
        finally:
            events.append("closed")
    policy = Policy("SEARCH_UNCLASSIFIED")
    registry = search_registry(load=lambda _: SearchInput(scope=scope), intent_factory=lambda: pytest.fail("provider"),
                               service_factory=media, failures=policy)
    result = registry.dispatch(ctx)
    assert result.status == "FAILED"
    assert result.failure_kind == "RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
    assert result.objects == result.produced == ()
    assert policy.seen == [] and events == ["closed"]
    assert "private" not in result.model_dump_json()


def test_cancel_wins_over_recording_limit_at_resource_entry():
    scope, _, _ = fixtures()
    ctx = context("COARSE_SEARCH", object())
    @contextmanager
    def media(data):
        ctx.cancel_signal.request()
        raise RecordingCapabilityError("ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED", "private")
        yield
    registry = search_registry(load=lambda _: SearchInput(scope=scope), intent_factory=lambda: None,
                               service_factory=media, failures=Policy())
    with pytest.raises(CancellationRequested):
        registry.dispatch(ctx)


@pytest.mark.parametrize("phase", ["load", "body", "exit", "other_recording_code"])
def test_only_preparation_entry_and_agreed_code_are_mapped(phase):
    from types import SimpleNamespace
    scope, coarse, _ = fixtures()
    ctx = context("COARSE_SEARCH", object())
    def fail(*args, **kwargs):
        raise RecordingCapabilityError("ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED", "private")
    def load(_):
        if phase == "load":
            fail()
        return SearchInput(scope=scope)
    @contextmanager
    def media(data):
        if phase == "other_recording_code":
            raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "private")
        yield SimpleNamespace(search_candidates=fail if phase == "body" else lambda *a, **k: coarse)
        if phase == "exit":
            fail()
    # Body failures must stay in the Search public-helper boundary; use a
    # policy that declines this Recording exception, so Runtime owns it.
    registry = search_registry(load=load, intent_factory=lambda: None, service_factory=media, failures=Policy())
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
