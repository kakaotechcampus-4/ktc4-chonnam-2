"""Opt-in nested acceptance probe; retain only event names/violation counts.

Capture the real formatter output produced by real test paths. No AST/string
existence proxy, fabricated event submission, private IDs or raw inputs stored.
"""
import json
import inspect
import os
from pathlib import Path
from threading import Lock

import pytest

_events = set()
_violations = 0
_invalid = []
_lock = Lock()
_original = None


def pytest_configure(config):
    from daesingo.common import logging
    from daesingo.common.logging.catalog import EVENTS, validate_event
    global _original
    _events.clear()
    _original = logging._JsonFormatter.format
    def format(self, record):
        global _violations
        output = _original(self, record)
        value = json.loads(output)
        if value['event'] in EVENTS:
            try:
                validate_event(value)
            except ValueError:
                with _lock:
                    _violations += 1
                    _invalid.append({'event': value['event'], 'fields': sorted(value),
                        'producer': [{'file':Path(f.filename).name,'function':f.function,'line':f.lineno}
                            for f in inspect.stack() if 'daesingo' in f.filename]})
            else:
                with _lock:
                    _events.add(value['event'])
        return output
    logging._JsonFormatter.format = format


def pytest_sessionfinish(session, exitstatus):
    path = os.environ['RT12_CATALOG_EVIDENCE']
    Path(path).write_text(json.dumps({'events': sorted(_events), 'violations': _violations,
                                    'invalid':_invalid}), encoding='utf-8')
    if _violations:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_unconfigure(config):
    from daesingo.common import logging
    if _original is not None:
        logging._JsonFormatter.format = _original
