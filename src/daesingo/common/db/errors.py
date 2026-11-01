"""Transport-independent DB outcomes; HTTP mapping belongs to RT-08."""

from sqlalchemy.exc import DBAPIError, TimeoutError


class BeforeCommitFailure(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"DB dependency failed before commit ({reason})")


class CommitOutcomeUnknown(RuntimeError):
    def __init__(self):
        super().__init__("DB commit outcome unknown; do not automatically repeat the API operation")


class TransactionRetryExhausted(RuntimeError):
    def __init__(self, attempts: int, *, outcome_unknown: bool):
        self.attempts = attempts
        self.outcome_unknown = outcome_unknown
        super().__init__(f"DB transaction attempts exhausted ({attempts}); outcome_unknown={outcome_unknown}")


class TransactionBoundaryError(RuntimeError):
    """The callback tried to end a transaction owned by its caller."""


def db_reason(error: BaseException) -> str | None:
    if isinstance(error, TimeoutError):
        return "pool_timeout"
    if not isinstance(error, DBAPIError):
        return None
    args = getattr(error.orig, "args", ())
    code = args[0] if args else None
    if code == 1205:
        return "lock_wait_timeout"
    if code == 1213:
        return "deadlock"
    if error.connection_invalidated:
        return "disconnect"
    return None
