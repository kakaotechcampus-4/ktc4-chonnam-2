import time
from collections.abc import Callable
from dataclasses import dataclass

from .execution import DeadlineExceededError, RunDeadline


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_retries: int
    base_delay_sec: float


def is_rate_limited(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "429" in message or "resource_exhausted" in message or "rate limit" in message
    )


def is_server_error(error: Exception) -> bool:
    message = str(error)
    for code in (
        "500",
        "502",
        "503",
        "504",
        "505",
        "506",
        "507",
        "508",
        "509",
        "510",
        "511",
    ):
        if code in message:
            return True
    return False


def is_transient(error: Exception) -> bool:
    return is_rate_limited(error) or is_server_error(error)


def call_with_retry[T](
    operation: Callable[[], T],
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    *,
    deadline: RunDeadline | None = None,
) -> T:
    for attempt in range(policy.max_retries + 1):
        try:
            return operation()
        except DeadlineExceededError:
            raise
        except Exception as error:
            if not is_transient(error) or attempt == policy.max_retries:
                raise
            # Check deadline before sleeping.
            if deadline is not None:
                deadline.check()
            raw_delay: float = policy.base_delay_sec * (1 << attempt)
            delay: float
            if deadline is not None:
                remaining = deadline.remaining_sec()
                delay = min(raw_delay, remaining)
                if delay <= 0:
                    raise DeadlineExceededError(
                        "run budget exhausted before retry sleep"
                    ) from error
            else:
                delay = raw_delay
            sleep(delay)
    raise AssertionError("retry loop did not terminate")
