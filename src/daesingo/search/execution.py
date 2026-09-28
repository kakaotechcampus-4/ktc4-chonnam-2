from collections.abc import Callable
from typing import final


class DeadlineExceededError(Exception):
    """Raised by RunDeadline.check() when the time budget is exhausted."""


@final
class RunDeadline:
    """Monotonic time budget injected at construction time.

    All downstream units (hash, probe, subprocess, provider) call check()
    before starting work and use remaining_sec() as their per-attempt timeout.
    The clock is injected so tests can control time without sleeping.
    """

    _monotonic: Callable[[], float]
    _budget_ms: int
    _start: float

    def __init__(self, monotonic: Callable[[], float], budget_ms: int) -> None:
        self._monotonic = monotonic
        self._budget_ms = budget_ms
        self._start = monotonic()

    def narrowed_to(self, budget_ms: int) -> "RunDeadline":
        """Return the same deadline bounded by a tighter budget.

        Start instant and clock are preserved, so already elapsed time still
        counts. Narrowing only shortens: a larger budget_ms is ignored.
        """
        narrowed = RunDeadline(self._monotonic, min(self._budget_ms, budget_ms))
        narrowed._start = self._start
        return narrowed

    def elapsed_ms(self) -> int:
        return round((self._monotonic() - self._start) * 1000)

    def remaining_ms(self) -> int:
        return self._budget_ms - self.elapsed_ms()

    def remaining_sec(self) -> float:
        return self.remaining_ms() / 1000.0

    def check(self) -> None:
        """Raise DeadlineExceededError if the budget is exhausted.

        Call this BEFORE starting any unit of work.
        """
        if self.remaining_ms() <= 0:
            raise DeadlineExceededError(
                f"run budget of {self._budget_ms}ms exhausted (elapsed {self.elapsed_ms()}ms)"
            )
