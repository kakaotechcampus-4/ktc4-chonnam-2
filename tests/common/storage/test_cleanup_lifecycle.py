"""Deterministic cadence and clean unwinding; no one-hour wall-clock waits."""
from importlib import import_module
from io import StringIO
import json
from threading import Event, Thread

import pytest
from daesingo.common.logging import bind_context, configure_logging
from test_cleanup import aged, scanner


def service(**kwargs):
    module = import_module('daesingo.common.storage.cleanup')
    assert hasattr(module, 'CleanupService'), 'startup/periodic cleanup lifecycle missing'
    return module.CleanupService(**kwargs)


def test_startup_once_periodic_cadence_and_shutdown_join(tmp_path):
    aged(tmp_path/'upload-first___')
    cleaner = scanner(tmp_path)
    waiting, tick, observed = Event(), Event(), Event()
    intervals, results = [], []
    def wait(seconds):
        intervals.append(seconds)
        waiting.set()
        assert tick.wait(5)
        tick.clear()
        return False
    def emit(kind, result):
        results.append((kind, result.count, result.bytes))
        if len(results) == 2:
            observed.set()
    owner = service(scanners=[cleaner], interval_sec=3600, emit=emit, wait=wait)
    try:
        owner.start()
        owner.start()
        assert waiting.wait(5)
        assert results == [('staging', 1, 3)]
        aged(tmp_path/'upload-second__', data=b'12345')
        tick.set()
        assert observed.wait(5)
    finally:
        owner.stop.set()
        tick.set()
        owner.stop_and_join()
    assert not owner.thread.is_alive()
    assert results == [('staging', 1, 3), ('staging', 1, 5)]
    assert intervals and all(value == 3600 for value in intervals)
    owner.stop_and_join()


def test_default_wait_is_interrupted_by_stop(tmp_path):
    owner = service(scanners=[scanner(tmp_path)], interval_sec=3600, emit=lambda *a: None)
    owner.start()
    owner.stop_and_join()
    assert not owner.thread.is_alive()


def test_startup_failure_does_not_leave_thread(tmp_path):
    cleaner = scanner(tmp_path)
    def fatal():
        raise KeyboardInterrupt()
    cleaner.scan = fatal
    owner = service(scanners=[cleaner], interval_sec=3600, emit=lambda *a: None)
    with pytest.raises(KeyboardInterrupt):
        owner.start()
    owner.stop_and_join()
    assert owner.thread is None


def test_stop_waits_for_owned_scan_and_prevents_new_pass(tmp_path, monkeypatch):
    module = import_module('daesingo.common.storage.cleanup')
    cleaner = scanner(tmp_path)
    entered, release, stopped = Event(), Event(), Event()
    tick = Event()
    def wait(seconds):
        assert tick.wait(5)
        return False
    owner = service(scanners=[cleaner], interval_sec=3600, emit=lambda *a: None, wait=wait)
    owner.start()
    aged(tmp_path/'upload-old_____')
    original = module._delete_file
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(module, '_delete_file', blocked)
    closer = Thread(target=lambda: (owner.stop_and_join(), stopped.set()))
    try:
        tick.set()
        assert entered.wait(5)
        closer.start()
        assert not stopped.is_set()
    finally:
        release.set()
        owner.stop.set()
        tick.set()
        if closer.ident is not None:
            closer.join(5)
        owner.stop_and_join()
    assert stopped.is_set() and not owner.thread.is_alive()


@pytest.mark.parametrize('mode', ['success', 'partial', 'zero'])
def test_cleanup_catalog_schema_has_counts_and_no_inherited_private_context(tmp_path, monkeypatch, mode):
    module = import_module('daesingo.common.storage.cleanup')
    assert hasattr(module, 'cleanup_emitter'), 'cleanup event catalog missing'
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    cleaner = scanner(tmp_path)
    if mode != 'zero':
        aged(tmp_path/'upload-private_')
    if mode == 'partial':
        aged(tmp_path/'upload-denied__')
        original = module._delete_file
        def fail(parent, name, *args):
            if name.endswith('denied__'):
                raise PermissionError('PRIVATE /absolute/path password=secret')
            return original(parent, name, *args)
        monkeypatch.setattr(module, '_delete_file', fail)
    with bind_context(case_id='case_PRIVATE', trace_id='tr_PRIVATE', module='api'):
        owner = service(scanners=[cleaner], interval_sec=3600, emit=module.cleanup_emitter(logger))
        owner.start()
        owner.stop_and_join()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert {e['event'] for e in events} == {'storage.cleanup.staging.count',
        'storage.cleanup.staging.bytes', 'storage.cleanup.staging.failed_count'}
    values = {e['event']: e['count'] for e in events}
    assert values['storage.cleanup.staging.count'] == (0 if mode == 'zero' else 1)
    assert values['storage.cleanup.staging.bytes'] == (0 if mode == 'zero' else 3)
    assert values['storage.cleanup.staging.failed_count'] == (1 if mode == 'partial' else 0)
    assert all(set(e) == {'timestamp', 'level', 'service', 'event', 'count'} for e in events)
    assert not any(word in output.getvalue() for word in ('PRIVATE', 'password', str(tmp_path), 'case_id'))


def test_sink_failure_does_not_break_scan_or_lifecycle(tmp_path):
    module = import_module('daesingo.common.storage.cleanup')
    assert hasattr(module, 'cleanup_emitter'), 'cleanup event catalog missing'
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    def fail(record):
        raise RuntimeError('PRIVATE')
    logger.addFilter(fail)
    try:
        path = aged(tmp_path/'upload-old_____')
        owner = service(scanners=[scanner(tmp_path)], interval_sec=3600,
                        emit=module.cleanup_emitter(logger))
        owner.start()
        owner.stop_and_join()
        assert not path.exists() and not owner.thread.is_alive()
    finally:
        logger.removeFilter(fail)
    assert output.getvalue() == ''


@pytest.mark.parametrize('service_name', ['api', 'worker'])
@pytest.mark.parametrize('nested', [False, True])
def test_publish_root_cannot_be_injected_as_temp_scan_target(tmp_path, service_name, nested):
    from daesingo.common.config import RuntimeConfig
    module = import_module('daesingo.common.storage.cleanup')
    publish = tmp_path/'source'
    publish.mkdir()
    temp = publish/'nested' if nested else publish
    config = RuntimeConfig.from_mapping(service_name, {
        'DAESINGO_RUNTIME_DB_URL': 'mysql+pymysql://test@127.0.0.1:1/test_cleanup',
        'DAESINGO_RUNTIME_MEDIA_ROOT': str(tmp_path),
        'DAESINGO_RUNTIME_'+service_name.upper()+'_TEMP_ROOT': str(temp)})
    with pytest.raises(ValueError, match='publish'):
        module.configured_cleanup(config, configure_logging(service_name, stream=StringIO()))
    assert list(publish.iterdir()) == []
