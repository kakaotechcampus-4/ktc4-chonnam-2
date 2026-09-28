"""Tests for RunDeadline and the deadline-aware retry layer."""

import subprocess
from collections.abc import Callable

import pytest

from daesingo.search.execution import DeadlineExceededError, RunDeadline
from daesingo.search.retry import RetryPolicy, call_with_retry

# ---------------------------------------------------------------------------
# Fake monotonic clock helpers
# ---------------------------------------------------------------------------


def _make_clock(
    start: float = 0.0,
) -> tuple[Callable[[], float], Callable[[float], None]]:
    """Returns (clock_fn, advance_fn). advance_fn moves the clock forward by ms."""
    state = [start]

    def clock() -> float:
        return state[0]

    def advance(ms: float) -> None:
        state[0] += ms / 1000.0

    return clock, advance


# ---------------------------------------------------------------------------
# RunDeadline — basic contract
# ---------------------------------------------------------------------------


def test_run_deadline_elapsed_and_remaining_at_construction() -> None:
    clock, _ = _make_clock(10.0)
    dl = RunDeadline(clock, budget_ms=500)
    assert dl.elapsed_ms() == 0
    assert dl.remaining_ms() == 500
    assert dl.remaining_sec() == pytest.approx(0.5)


def test_run_deadline_tracks_elapsed_time() -> None:
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=1000)
    advance(300)
    assert dl.elapsed_ms() == 300
    assert dl.remaining_ms() == 700
    assert dl.remaining_sec() == pytest.approx(0.7)


def test_run_deadline_remaining_goes_negative_when_exhausted() -> None:
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=200)
    advance(250)
    assert dl.remaining_ms() <= 0
    assert dl.remaining_sec() <= 0.0


def test_run_deadline_check_raises_when_exhausted() -> None:
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=100)
    advance(150)
    with pytest.raises(DeadlineExceededError):
        dl.check()


def test_run_deadline_check_passes_when_budget_remains() -> None:
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=500)
    advance(100)
    dl.check()  # must not raise


def test_run_deadline_check_raises_at_exact_zero() -> None:
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=100)
    advance(100)  # remaining_ms == 0
    with pytest.raises(DeadlineExceededError):
        dl.check()


def test_deadline_exceeded_error_is_exception_subclass() -> None:
    assert issubclass(DeadlineExceededError, Exception)


# ---------------------------------------------------------------------------
# RetryPolicy + deadline — retry sleep never crosses the deadline
# ---------------------------------------------------------------------------


def test_retry_sleep_is_capped_by_remaining_deadline() -> None:
    """If the next backoff would exceed the deadline, we should NOT sleep past it."""
    clock, _ = _make_clock()
    dl = RunDeadline(clock, budget_ms=800)
    sleeps: list[float] = []

    # Budget: 800ms. First attempt fails with rate limit.
    # base_delay=1.0s → 2^0 * 1.0 = 1.0s, but only 800ms remain → must cap at ≤0.8s
    calls = 0

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("429 rate limit")
        return "ok"

    result = call_with_retry(flaky, RetryPolicy(2, 1.0), sleeps.append, deadline=dl)
    assert result == "ok"
    assert len(sleeps) == 1
    assert sleeps[0] <= 0.8 + 1e-9  # must not exceed remaining budget


def test_retry_does_not_retry_past_exhausted_deadline() -> None:
    """When deadline is already exhausted, don't sleep-and-retry; surface DeadlineExceededError."""
    clock, advance = _make_clock()
    dl = RunDeadline(clock, budget_ms=50)
    advance(60)  # deadline already exhausted

    def flaky() -> str:
        raise RuntimeError("429 rate limit")

    with pytest.raises(DeadlineExceededError):
        _ = call_with_retry(flaky, RetryPolicy(3, 0.1), lambda _: None, deadline=dl)


def test_retry_without_deadline_uses_full_backoff() -> None:
    """No deadline → original exponential backoff behaviour preserved."""
    sleeps: list[float] = []
    calls = 0

    def two_rate_limits() -> str:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "done"

    result = call_with_retry(two_rate_limits, RetryPolicy(3, 0.5), sleeps.append)
    assert result == "done"
    assert sleeps == [0.5, 1.0]


# ---------------------------------------------------------------------------
# Retry classification
# ---------------------------------------------------------------------------


def test_rate_limit_http_429_retries() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("HTTP 429 Too Many Requests")
        return "ok"

    assert call_with_retry(op, RetryPolicy(2, 0.0), lambda _: None) == "ok"
    assert calls == 2


def test_rate_limit_resource_exhausted_retries() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("resource_exhausted quota exceeded")
        return "ok"

    assert call_with_retry(op, RetryPolicy(2, 0.0), lambda _: None) == "ok"
    assert calls == 2


def test_server_error_5xx_retries() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("503 Service Unavailable")
        return "ok"

    assert call_with_retry(op, RetryPolicy(2, 0.0), lambda _: None) == "ok"
    assert calls == 2


def test_auth_error_does_not_retry() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("401 Unauthorized")

    with pytest.raises(RuntimeError, match="401"):
        _ = call_with_retry(op, RetryPolicy(3, 0.0), lambda _: None)
    assert calls == 1


def test_validation_error_does_not_retry() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("schema validation failed")

    with pytest.raises(ValueError):
        _ = call_with_retry(op, RetryPolicy(3, 0.0), lambda _: None)
    assert calls == 1


def test_deadline_exceeded_error_does_not_retry() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        raise DeadlineExceededError("budget gone")

    with pytest.raises(DeadlineExceededError):
        _ = call_with_retry(op, RetryPolicy(3, 0.0), lambda _: None)
    assert calls == 1


def test_programmer_assertion_error_is_not_retried() -> None:
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        raise AssertionError("programmer defect")

    with pytest.raises(AssertionError, match="programmer defect"):
        _ = call_with_retry(op, RetryPolicy(3, 0.0), lambda _: None)
    assert calls == 1


def test_payload_or_schema_error_does_not_retry() -> None:
    """A 400 Bad Request (payload/schema issue) must not retry."""
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("400 Bad Request")

    with pytest.raises(RuntimeError, match="400"):
        _ = call_with_retry(op, RetryPolicy(3, 0.0), lambda _: None)
    assert calls == 1


# ---------------------------------------------------------------------------
# Subprocess timeout — terminate AND reap (no zombies)
# ---------------------------------------------------------------------------


def test_timed_out_subprocess_is_terminated_and_reaped() -> None:
    """A child process that exceeds its timeout must be terminated and waited on."""
    proc = subprocess.Popen(
        ["python", "-c", "import time; time.sleep(10)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _ = proc.communicate(timeout=0.1)
    except subprocess.TimeoutExpired:
        proc.terminate()
        _ = proc.wait()  # reap — no zombie

    # After wait(), returncode must be set (not None).
    assert proc.returncode is not None
