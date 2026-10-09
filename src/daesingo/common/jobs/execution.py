"""Execution-scoped invocation data, without DB resources or domain state."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from daesingo.common.job_execution import RuntimeContractRef


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    execution_id: str
    job_id: str
    case_id: str
    kind: str
    attempt: int
    trace_id: str
    # Reserved injection points. RT-05/07 own their protocols and behavior.
    cancel_signal: object | None = None
    usage_sink: object | None = None


class HandlerResult(BaseModel):
    """T1 facts only; Runtime never maps a module's failure taxonomy."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["SUCCEEDED", "FAILED"] = "SUCCEEDED"
    produced: tuple[RuntimeContractRef, ...] = ()
    failure_kind: str | None = Field(default=None, min_length=1, max_length=191)

    @model_validator(mode="after")
    def terminal_shape(self):
        if (self.status == "FAILED") != (self.failure_kind is not None):
            raise ValueError("inconsistent handler terminal result")
        if len({(r.kind, r.ref) for r in self.produced}) != len(self.produced):
            raise ValueError("duplicate produced reference")
        return self


def runtime_failure(kind: str) -> HandlerResult:
    return HandlerResult(status="FAILED", failure_kind=kind)
