"""Execution-local AnalysisSource budgets, independent of DB packet settings."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from fractions import Fraction

from .errors import RecordingCapabilityError


def exceeded():
    return RecordingCapabilityError("ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED",
                                    "분석 영상의 지원 범위를 초과했습니다")


@dataclass(frozen=True)
class AnalysisSourceLimits:
    max_bytes: int
    max_duration_ms: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.max_bytes, self.max_duration_ms)):
            raise ValueError("AnalysisSource limits must be positive integers")

    def check_bytes(self, size):
        if size > self.max_bytes:
            raise exceeded()

    def check_range(self, time_range):
        duration = Fraction(str(time_range.end_sec)) - Fraction(str(time_range.start_sec))
        if duration * 1000 > self.max_duration_ms:
            raise exceeded()


_budget = ContextVar("recording_analysis_byte_budget", default=None)
_checkpoint = ContextVar("recording_analysis_checkpoint", default=lambda: None)


@contextmanager
def analysis_source_scope(limits, checkpoint):
    byte_token = _budget.set(limits.max_bytes if limits is not None else None)
    check_token = _checkpoint.set(checkpoint)
    try:
        checkpoint()
        yield
        checkpoint()
    finally:
        _checkpoint.reset(check_token)
        _budget.reset(byte_token)


@contextmanager
def remaining_bytes(used):
    budget = _budget.get()
    token = _budget.set(None if budget is None else budget - used)
    try:
        check_output_size(0)
        yield
    finally:
        _budget.reset(token)


def checkpoint():
    _checkpoint.get()()


def byte_budget():
    return _budget.get()


def check_output_size(size):
    budget = byte_budget()
    if budget is not None and size > budget:
        raise exceeded()


def check_output(path):
    checkpoint()
    check_output_size(path.stat().st_size)


def read_output(path):
    check_output(path)
    budget = byte_budget()
    if budget is None:
        return path.read_bytes()
    with path.open("rb") as stream:
        content = stream.read(budget + 1)
    check_output_size(len(content))
    return content
