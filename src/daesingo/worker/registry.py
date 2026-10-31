"""The Worker composition root owns one immutable kind registration snapshot.

RD-09a: register invocations, not process-global mutable RecordingService state.
RT-10 invocations create a service per execution and close it in finally; durable
repositories may be shared. No service lifecycle implementation belongs here.
"""

from collections.abc import Callable, Mapping
import logging
from types import MappingProxyType

from daesingo.common.jobs.execution import ExecutionContext, HandlerResult, runtime_failure
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.logging import log_event_best_effort, safe_correlation, safe_error_type
from daesingo.common.usage.port import UsageError

Handler = Callable[[ExecutionContext], HandlerResult]


class KindRegistry:
    def __init__(self, handlers: Mapping[str, Handler]):
        self._handlers = MappingProxyType(dict(handlers))

    def merged(self, other: "KindRegistry") -> "KindRegistry":
        if self._handlers.keys() & other._handlers.keys():
            raise ValueError("duplicate kind registration")
        return KindRegistry({**self._handlers, **other._handlers})

    def dispatch(self, context: ExecutionContext, *, logger: logging.Logger | None = None) -> HandlerResult:
        handler = self._handlers.get(context.kind)
        if handler is None:
            return runtime_failure("RUNTIME_UNREGISTERED_KIND")
        try:
            result = handler(context)
            if not isinstance(result, HandlerResult):
                return runtime_failure("RUNTIME_INVALID_RESULT")
            # Revalidate even a model constructed/copied without validation.
            return HandlerResult.model_validate(result.model_dump())
        except (CancellationRequested, UsageError):
            raise
        except Exception as error:
            if logger is not None:
                log_event_best_effort(logger, "runtime.execution.failed", level=logging.ERROR, status="FAILED",
                    **safe_correlation(trace_id=context.trace_id, case_id=context.case_id,
                        job_id=context.job_id, execution_id=context.execution_id), **safe_error_type(error))
            return runtime_failure("RUNTIME_HANDLER_ERROR")
