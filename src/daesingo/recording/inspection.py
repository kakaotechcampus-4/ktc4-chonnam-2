"""Service 수명 안에서만 source frame inspection을 공유하는 내부 저장소."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy


_active = ContextVar("source_frame_inspections", default=None)


class SourceFrameInspections:
    def __init__(self):
        self._entries = {}
        self._closed = False

    def get(self, key):
        return deepcopy(self._entries.get(key)) if not self._closed else None

    def put(self, key, inspection):
        if not self._closed:
            self._entries[key] = deepcopy(inspection)

    def discard(self, key):
        self._entries.pop(key, None)

    def close(self):
        self._closed = True
        self._entries.clear()


@contextmanager
def source_inspections(cache):
    token = _active.set(cache)
    try:
        yield
    finally:
        _active.reset(token)


def active_inspections():
    return _active.get()
