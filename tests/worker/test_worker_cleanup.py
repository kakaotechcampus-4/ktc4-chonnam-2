"""Worker cleanup is independent of DB sweeps, and unwinds on every exit."""
from importlib import import_module
from io import StringIO
from pathlib import Path
from threading import Event
from types import MappingProxyType

import pytest
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.logging import configure_logging
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry


def test_worker_scans_temp_only_before_first_claim_and_joins_on_exit(tmp_path):
    media, temp = tmp_path/'media', tmp_path/'temp'
    temp.mkdir()
    work = temp/'recording-analysis-abandon_'
    work.mkdir()
    path = work/'partial'
    path.write_bytes(b'abc')
    import os
    for p in (path, work):
        os.utime(p, (1, 1))
    media.mkdir()
    published = media/'source'
    published.mkdir()
    (published/'upload-publish_').write_bytes(b'keep')
    config = RuntimeConfig.from_mapping('worker', {
        'DAESINGO_RUNTIME_DB_URL': 'mysql+pymysql://test@127.0.0.1:1/test_cleanup',
        'DAESINGO_RUNTIME_MEDIA_ROOT': str(media), 'DAESINGO_RUNTIME_WORKER_TEMP_ROOT': str(temp)})
    startup = Startup(config, MappingProxyType({}), configure_logging('worker', stream=StringIO()))
    stop = Event()
    worker = compose_worker(engine=object(), startup=startup, registry=KindRegistry({}), stop=stop)
    worker.sweeper = None  # This test never creates a DB resource.
    def claim():
        assert not path.exists(), 'Worker startup temp cleanup missing'
        stop.set()
    worker.claim = claim
    worker.run()
    assert not worker.cleanup.thread.is_alive()
    assert (published/'upload-publish_').read_bytes() == b'keep'


@pytest.mark.parametrize('stage', ['startup', 'claim'])
def test_worker_failure_still_joins_cleanup_and_preserves_primary_error(tmp_path, stage):
    from daesingo.common.jobs.worker_loop import WorkerLoop
    from daesingo.common.config import WorkerSettings
    module = import_module('daesingo.common.storage.cleanup')
    assert hasattr(module, 'CleanupService'), 'cleanup lifecycle missing'
    cleaner = module.CleanupService(scanners=[], interval_sec=3600, emit=lambda *a: None)
    def fail():
        raise RuntimeError('primary')
    worker = WorkerLoop(claim=fail, dispatch=lambda c: HandlerResult(), record=lambda *a: True,
        settings=WorkerSettings(), stop=Event(), logger=configure_logging('worker', stream=StringIO()))
    worker.cleanup = cleaner
    if stage == 'startup':
        worker.sweeper = type('FailingSweep', (), {'start': staticmethod(fail),
                                                 'stop_and_join': staticmethod(lambda: None)})()
    with pytest.raises(RuntimeError, match='primary'):
        worker.run()
    assert cleaner.thread is not None, 'Worker did not start cleanup lifecycle'
    assert not cleaner.thread.is_alive()
