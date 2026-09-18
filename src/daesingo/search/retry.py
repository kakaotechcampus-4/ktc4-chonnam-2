import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_retries: int
    base_delay_sec: float


def is_rate_limited(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "429" in message or "resource_exhausted" in message or "rate limit" in message
    )


def call_with_retry[T](
    operation: Callable[[], T],
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(policy.max_retries + 1):
        try:
            return operation()
        except Exception as error:
            if not is_rate_limited(error) or attempt == policy.max_retries:
                raise
            sleep(policy.base_delay_sec * (2**attempt))
    raise AssertionError("retry loop did not terminate")
