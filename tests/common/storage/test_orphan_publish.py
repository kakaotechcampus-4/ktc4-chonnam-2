"""P-6 deletion is conditional on a public, fail-closed registration verdict."""
import importlib
import os
from pathlib import Path
from threading import Event, Thread
import subprocess
import sys

import pytest


NOW = 200_000
NAME = 'a' * 32


def api():
    module = importlib.import_module('daesingo.common.storage.cleanup')
    assert hasattr(module, 'OrphanPublishScanner'), 'P-6 orphan boundary missing'
    return module


def candidate(root, name=NAME, age=86401):
    path = root / 'source' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'synthetic')
    os.utime(path, (NOW - age, NOW - age))
    return path


def scanner(root, registration=lambda locator: False):
    return api().OrphanPublishScanner(root=root / 'source', lease_root=root,
        age_sec=86400, now=lambda: NOW, registration=registration)


@pytest.mark.parametrize('age,removed', [(86399, False), (86400, False), (86401, True)])
def test_only_strictly_old_unregistered_publish_is_deleted(tmp_path, age, removed):
    path = candidate(tmp_path, age=age)
    seen = []
    def read(locator):
        seen.append(locator)
        return False
    result = scanner(tmp_path, read).scan()
    assert path.exists() is (not removed)
    assert (result.count, result.bytes, result.failed) == ((1, 9, 0) if removed else (0, 0, 0))
    assert seen == (['source/' + NAME] if removed else [])


@pytest.mark.parametrize('verdict,failures', [(True, 0), (None, 1), (0, 1), ('UNREGISTERED', 1)])
def test_registration_and_uncertain_response_preserve(tmp_path, verdict, failures):
    path = candidate(tmp_path)
    result = scanner(tmp_path, lambda locator: verdict).scan()
    assert path.exists()
    assert (result.count, result.bytes, result.failed) == (0, 0, failures)


@pytest.mark.parametrize('error', [RuntimeError, FileNotFoundError])
def test_query_failure_is_isolated_and_never_false(tmp_path, error):
    paths = [candidate(tmp_path, name=n * 32) for n in ('a', 'b')]
    def read(locator):
        if locator.endswith('a' * 32):
            raise error('PRIVATE-path-error')
        return False
    result = scanner(tmp_path, read).scan()
    assert paths[0].exists() and not paths[1].exists()
    assert (result.count, result.bytes, result.failed) == (1, 9, 1)


def test_live_root_defers_query_and_deletion(tmp_path):
    path = candidate(tmp_path)
    cleaner = scanner(tmp_path, lambda locator: pytest.fail('queried active publish'))
    with cleaner.in_use():
        assert cleaner.scan().count == 0
        assert path.exists()


@pytest.mark.parametrize('mutation', ['replace', 'refresh', 'disappear', 'hardlink'])
def test_post_lookup_identity_change_preserved_or_disappearance_not_counted(tmp_path, mutation):
    path = candidate(tmp_path)
    def read(locator):
        if mutation in ('replace', 'disappear'):
            path.unlink()
        if mutation == 'replace':
            candidate(tmp_path)
        if mutation == 'refresh':
            os.utime(path, (NOW, NOW))
        if mutation == 'hardlink':
            os.link(path, tmp_path / 'outside')
        return False
    result = scanner(tmp_path, read).scan()
    assert path.exists() is (mutation != 'disappear')
    assert (result.count, result.bytes, result.failed) == (0, 0, 0)


def test_hardlink_unknown_names_and_nested_entries_not_candidates(tmp_path):
    path = candidate(tmp_path)
    os.link(path, tmp_path / 'external')
    other = candidate(tmp_path, 'user-owned')
    nested = candidate(tmp_path, 'nested/' + 'b' * 32)
    result = scanner(tmp_path, lambda locator: pytest.fail('unsafe candidate queried')).scan()
    assert result.count == result.failed == 0
    assert all(p.exists() for p in (path, other, nested))


def test_wall_clock_rollback_delays_and_forward_jump_never_bypasses_registration(tmp_path):
    path = candidate(tmp_path, age=1)
    cleaner = scanner(tmp_path, lambda locator: True)
    cleaner.now = lambda: NOW - 100000
    assert cleaner.scan().count == 0
    cleaner.now = lambda: NOW + 100000
    assert cleaner.scan().count == 0
    assert path.exists()


@pytest.mark.parametrize('spelling', ['namespace', 'separators', 'dot'] + (['case', 'short'] if os.name == 'nt' else []))
def test_root_alias_uses_same_live_lease_and_registered_identity(tmp_path, spelling):
    from test_cleanup_publish_safety import path_alias
    path = candidate(tmp_path)
    alias = Path(path_alias(tmp_path, spelling))
    assert os.path.samefile(alias, tmp_path)
    cleaner = scanner(alias, lambda locator: True)
    assert cleaner.scan().count == 0 and path.exists()
    cleaner.registration = lambda locator: False
    with scanner(tmp_path).in_use():
        assert cleaner.scan().count == 0
    assert cleaner.scan().count == 1


@pytest.mark.parametrize('kind', ['root', 'source', 'nested'])
def test_directory_symlink_or_junction_never_followed(tmp_path, kind):
    from test_cleanup import link_directory
    outside = tmp_path/'outside'
    path = candidate(outside)
    root = tmp_path/'managed'
    root.mkdir()
    if kind == 'root':
        root.rmdir()
        link_directory(root, outside)
    elif kind == 'source':
        link_directory(root/'source', outside/'source')
    else:
        (root/'source').mkdir()
        link_directory(root/'source'/('b'*32), outside/'source')
    if kind in ('root', 'source'):
        with pytest.raises(ValueError):
            scanner(root)
    else:
        assert scanner(root).scan().count == 0
    assert path.exists()


def test_metadata_and_delete_failures_are_isolated(tmp_path, monkeypatch):
    from daesingo.common.storage import _filesystem as fs
    paths = [candidate(tmp_path, name=n*32) for n in ('a', 'b', 'c')]
    lstat, remove = fs.Pinned.lstat, fs.Pinned.remove
    def broken_stat(self, name):
        if name == 'a'*32:
            raise PermissionError('PRIVATE metadata')
        return lstat(self, name)
    def broken_delete(self, name, child, **kw):
        if name == 'b'*32:
            raise PermissionError('PRIVATE delete')
        return remove(self, name, child, **kw)
    monkeypatch.setattr(fs.Pinned, 'lstat', broken_stat)
    monkeypatch.setattr(fs.Pinned, 'remove', broken_delete)
    result = scanner(tmp_path).scan()
    assert (result.count, result.bytes, result.failed) == (1, 9, 2)
    assert paths[0].exists() and paths[1].exists() and not paths[2].exists()


def test_readonly_platform_semantics_and_remaining_file_isolation(tmp_path):
    import stat
    path = candidate(tmp_path)
    other = candidate(tmp_path, 'b'*32)
    path.chmod(stat.S_IREAD)
    try:
        result = scanner(tmp_path).scan()
        assert not other.exists()
        assert (result.count, result.bytes, result.failed) == ((1, 9, 1) if os.name == 'nt' else (2, 18, 0))
    finally:
        if path.exists():
            path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_actual_separate_process_lease_and_crash_release(tmp_path):
    path = candidate(tmp_path)
    code = '''
import sys
from pathlib import Path
from daesingo.common.storage.cleanup import OrphanPublishScanner
root = Path(sys.argv[1])
scanner = OrphanPublishScanner(root=root/'source', lease_root=root, age_sec=86400, registration=lambda locator: False)
with scanner.in_use():
    print('ready', flush=True)
    sys.stdin.read()
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[3]/'src'))
    child = subprocess.Popen([sys.executable, '-u', '-c', code, str(tmp_path)],
        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready, lines = Event(), []
    def listen():
        lines.append(child.stdout.readline().strip())
        ready.set()
    thread = Thread(target=listen)
    thread.start()
    try:
        assert ready.wait(10) and lines == ['ready']
        cleaner = scanner(tmp_path)
        assert cleaner.scan().count == 0 and path.exists()
        child.kill()
        child.communicate(timeout=10)
        assert cleaner.scan().count == 1 and not path.exists()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
        thread.join(10)
        assert not thread.is_alive()


def test_negative_control_omitting_lease_exposes_active_publish(tmp_path):
    from daesingo.common.storage._filesystem import pin_root
    path = candidate(tmp_path)
    cleaner = scanner(tmp_path)
    with cleaner.in_use():
        assert cleaner.scan().count == 0
        # Deliberately bypass only synchronization on synthetic bytes: the
        # vulnerable lookup -> unlink path deletes a live pre-registration file.
        result = api().ScanResult()
        with pin_root(cleaner.root) as root:
            cleaner._walk(root, NOW*1_000_000_000, result, top=True)
        assert result.count == 1 and not path.exists()


def test_orphan_structured_logs_never_inherit_private_context():
    import json
    from io import StringIO
    from daesingo.common.logging import bind_context, configure_logging
    output = StringIO()
    with bind_context(case_id='PRIVATE', trace_id='PRIVATE', execution_id='PRIVATE'):
        api().cleanup_emitter(configure_logging('api', stream=output))('orphan', api().ScanResult(2, 18, 1))
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(events) == 3 and 'PRIVATE' not in output.getvalue()
    assert {event['count'] for event in events} == {2, 18, 1}
    assert all(set(event) == {'timestamp', 'level', 'service', 'event', 'count'} for event in events)


@pytest.mark.parametrize('boundary', ['lease', 'query'])
def test_root_replacement_never_scans_a_tree_under_another_lease(tmp_path, monkeypatch, boundary):
    from contextlib import contextmanager
    module = api()
    root, moved = tmp_path/'managed', tmp_path/'moved'
    candidate(root)
    cleaner = scanner(root)
    original = module._lease
    replaced = []
    def replace_root():
        if os.name == 'nt':
            with pytest.raises(PermissionError):
                root.rename(moved)
            return
        root.rename(moved)
        candidate(root)
        replaced.append(True)
    if boundary == 'lease':
        @contextmanager
        def leased(*args, **kwargs):
            with original(*args, **kwargs) as acquired:
                if acquired and kwargs['exclusive']:
                    replace_root()
                yield acquired
        monkeypatch.setattr(module, '_lease', leased)
    else:
        def read(locator):
            replace_root()
            return False
        cleaner.registration = read
    result = cleaner.scan()
    if os.name == 'nt':
        assert not replaced and result.count == 1  # OS refused replacement
    else:
        assert replaced and result.count == 0 and result.failed == 1
        assert (root/'source'/NAME).exists() and (moved/'source'/NAME).exists()


def test_publish_shared_leases_coexist_without_nested_registration_deadlock(tmp_path):
    candidate(tmp_path)
    code = '''
import sys
from pathlib import Path
from daesingo.common.storage.cleanup import OrphanPublishScanner
root = Path(sys.argv[1])
c = OrphanPublishScanner(root=root/'source', lease_root=root, age_sec=86400, registration=lambda locator: False)
with c.in_use():
    print('outer', flush=True)
    with c.in_use():
        assert c.scan().count == 0
        print('inner', flush=True)
print('released', flush=True)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[3]/'src'))
    result = subprocess.run([sys.executable, '-u', '-c', code, str(tmp_path)],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.splitlines() == ['outer', 'inner', 'released']
    assert scanner(tmp_path).scan().count == 1


def test_orphan_lock_permission_failure_is_not_normal_contention(tmp_path, monkeypatch):
    path = candidate(tmp_path)
    def denied(*args, **kwargs):
        raise PermissionError('PRIVATE lock failure')
    if os.name == 'nt':
        from daesingo.common.storage import _filesystem as fs
        monkeypatch.setattr(fs, 'publish_lock', denied)
    else:
        import fcntl
        monkeypatch.setattr(fcntl, 'flock', denied)
    result = scanner(tmp_path).scan()
    assert path.exists()
    assert (result.count, result.bytes, result.failed) == (0, 0, 1)
    with pytest.raises(PermissionError):
        with scanner(tmp_path).in_use():
            pytest.fail('lock permission failure accepted')
