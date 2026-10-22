"""RT-12(a) P2: metadata faults must not starve unrelated aged cleanup."""
from io import StringIO
import json
import os
from types import SimpleNamespace

import pytest

from daesingo.common.logging import bind_context, configure_logging
from daesingo.common.storage import _filesystem as fs
from daesingo.common.storage.cleanup import cleanup_emitter
from test_cleanup import NOW, aged, scanner


@pytest.mark.parametrize('position', [0, 1, 2], ids=['first', 'middle', 'last'])
@pytest.mark.parametrize('error', [PermissionError, OSError, FileNotFoundError])
@pytest.mark.parametrize('nested', [False, True], ids=['root', 'nested'])
def test_one_metadata_fault_does_not_stop_other_deletions(tmp_path, monkeypatch, position, error, nested):
    directory = tmp_path/'recording-analysis-abcdefgh' if nested else tmp_path
    first = aged(directory/'upload-aaaaaaa1', data=b'ab')
    other = aged(directory/'unrelated', data=b'PRIVATE')
    last = aged(directory/'upload-aaaaaaa2', data=b'cde')
    if nested:
        os.utime(directory, (NOW-4000, NOW-4000))
    # Deterministic enumeration order across NTFS and native POSIX. Actual
    # DirEntry objects and all deletion/handle operations remain real.
    order = [first.name, last.name]
    order.insert(position, other.name)
    original_scandir = fs.os.scandir
    class Ordered:
        def __init__(self, path):
            with original_scandir(path) as entries:
                values = list(entries)
            self.values = iter(sorted(values, key=lambda entry:
                                     order.index(entry.name) if entry.name in order else -1))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def __iter__(self):
            return self
        def __next__(self):
            return next(self.values)
    monkeypatch.setattr(fs.os, 'scandir', Ordered)
    original_stat = fs.Pinned.lstat
    failed_stats = []
    def metadata(parent, name):
        if parent.path == directory and name == other.name:
            failed_stats.append(name)
            if error is FileNotFoundError:
                other.unlink(missing_ok=True)
            raise error('PRIVATE /outside/path case_secret password=secret')
        return original_stat(parent, name)
    monkeypatch.setattr(fs.Pinned, 'lstat', metadata)
    cleaner = scanner(tmp_path, kind='temp' if nested else 'staging')
    result = cleaner.scan()
    assert not first.exists() and not last.exists(), f'normal residues starved: {result}'
    assert other.exists() is (error is not FileNotFoundError)
    assert (result.count, result.bytes, result.failed) == (2, 5, 0 if error is FileNotFoundError else 1)
    assert failed_stats == ['unrelated']  # No metadata rewalk for emptiness.
    if nested:
        assert directory.exists() is (error is not FileNotFoundError)
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    with bind_context(case_id='case_PRIVATE', trace_id='trace_PRIVATE'):
        cleanup_emitter(logger)(cleaner.kind, result)
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert {e['event'].rsplit('.', 1)[1]: e['count'] for e in events} == {
        'count': 2, 'bytes': 5, 'failed_count': 0 if error is FileNotFoundError else 1}
    assert all(set(e) == {'timestamp', 'level', 'service', 'event', 'count'} for e in events)
    assert all(word not in output.getvalue() for word in
               ('PRIVATE', 'unrelated', 'aaaaaaa', 'case_secret', 'password', str(tmp_path)))


def test_large_directory_metadata_is_consumed_lazily_and_iterator_closes(tmp_path, monkeypatch):
    seed = aged(tmp_path/'seed').lstat()
    pulled, stats, closed = [], [], []
    class LargeDirectory:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            closed.append(True)
        def __iter__(self):
            for index in range(100_000):
                pulled.append(index)
                yield SimpleNamespace(name=f'item-{index}')
    with fs.pin_root(tmp_path) as directory:
        monkeypatch.setattr(fs.os, 'scandir', lambda path: LargeDirectory())
        def metadata(parent, name):
            stats.append(name)
            return seed
        monkeypatch.setattr(fs.Pinned, 'lstat', metadata)
        entries = directory.entries()
        try:
            assert next(iter(entries)) == ('item-0', seed)
            assert len(pulled) == len(stats) == 1, 'entire directory was prefetched'
        finally:
            if hasattr(entries, 'close'):
                entries.close()
    assert closed == [True]


@pytest.mark.parametrize('nonempty', [False, True])
def test_emptiness_uses_at_most_one_name_without_metadata(tmp_path, monkeypatch, nonempty):
    assert hasattr(fs.Pinned, 'is_empty'), 'bounded name-only emptiness check missing'
    pulled = []
    class Directory:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __iter__(self):
            if nonempty:
                pulled.append(1)
                yield SimpleNamespace(name='unrelated')
                pytest.fail('emptiness check enumerated past the first name')
    with fs.pin_root(tmp_path) as directory:
        monkeypatch.setattr(fs.os, 'scandir', lambda path: Directory())
        monkeypatch.setattr(fs.Pinned, 'lstat', lambda *args:
                            pytest.fail('emptiness check retried metadata'))
        assert directory.is_empty() is (not nonempty)
    assert len(pulled) == int(nonempty)
