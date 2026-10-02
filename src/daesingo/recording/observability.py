"""실행 범위에 한정된 내부 관찰. 경로/명령/예외 원문은 수집하지 않는다."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import subprocess
from time import perf_counter

from .errors import RecordingCapabilityError


PHASES = ("source_snapshot", "source_probe", "frame_prepare", "encode", "output_probe",
          "output_validate", "bytes_read", "bytes_validate", "source_verify")
_sink = ContextVar("materialization_sink", default=None)
_current = ContextVar("materialization_trace", default=None)


def _code(error):
    if isinstance(error, RecordingCapabilityError):
        return error.code if error.code in {"UNAVAILABLE", "TEMPORARY_FAILURE", "UNSUPPORTED_MEDIA"} else "CAPABILITY_FAILED"
    if isinstance(error, subprocess.TimeoutExpired):
        return "TOOL_TIMEOUT"
    if isinstance(error, OSError):
        return "IO_ERROR"
    if isinstance(error, (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError)):
        return "VALIDATION_FAILED"
    return "EXECUTION_FAILED"


@contextmanager
def capture_materialization():
    traces = []
    token = _sink.set(traces)
    try:
        yield traces
    finally:
        _sink.reset(token)


def observed_materialization(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        sink = _sink.get()
        if sink is None:
            return method(*args, **kwargs)
        trace = {"status": "SUCCESS", "failure": None, "elapsed_sec": None,
                 "phases": [{"name": name, "status": "SKIPPED", "elapsed_sec": None, "failure": None}
                            for name in PHASES]}
        sink.append(trace)
        token = _current.set(trace)
        start = perf_counter()
        try:
            return method(*args, **kwargs)
        except BaseException as error:
            trace["status"] = "FAILED"
            if trace["failure"] is None:
                trace["failure"] = {"phase": "outside_phases", "code": _code(error)}
            raise
        finally:
            trace["elapsed_sec"] = perf_counter() - start
            _current.reset(token)
    return wrapped


@contextmanager
def phase(name):
    trace = _current.get()
    if trace is None:
        yield
        return
    entry = next(p for p in trace["phases"] if p["name"] == name)
    start = perf_counter()
    try:
        yield
    except BaseException as error:
        entry.update(status="FAILED", failure={"code": _code(error)})
        trace["failure"] = {"phase": name, "code": _code(error)}
        raise
    else:
        entry["status"] = "SUCCESS"
    finally:
        entry["elapsed_sec"] = perf_counter() - start
