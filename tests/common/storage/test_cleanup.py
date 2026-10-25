"""Cleanup must never trade a live/young/outside file for reclaimed bytes."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread

import pytest


NOW = 20_000


def api():
    try:
        return importlib.import_module('daesingo.common.storage.cleanup')
    except ModuleNotFoundError as error:
        if error.name in ('daesingo.common.storage', 'daesingo.common.storage.cleanup'):
            pytest.fail('RT-12(a) cleanup implementation missing')
        raise


def aged(path, age=3601, data=b'abc'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (NOW-age, NOW-age))
    return path


def scanner(root, *, kind='staging', **kwargs):
    return api().CleanupScanner(root=root, kind=kind, age_sec=3600,
                                now=lambda: NOW, **kwargs)


@pytest.mark.parametrize('kind', ['staging', 'temp'])
@pytest.mark.parametrize('age,deleted', [(3599.999, False), (3600, False), (3600.001, True)])
def test_age_is_strict_even_at_startup(tmp_path, kind, age, deleted):
    path = aged(tmp_path / ('upload-residue_' if kind == 'staging' else 'recording-analysis-residue_') / 'bytes'
                 if kind == 'temp' else tmp_path / 'upload-residue_', age)
    if kind == 'temp':
        os.utime(path.parent, (NOW-age, NOW-age))
    result = scanner(tmp_path, kind=kind).scan()
    assert path.exists() is (not deleted)
    assert (result.count, result.bytes, result.failed) == ((1, 3, 0) if deleted else (0, 0, 0))


def test_only_known_residuals_and_never_publish_are_scanned(tmp_path):
    old = aged(tmp_path/'staging'/'upload-old_____')
    keep = [aged(tmp_path/'source'/'upload-publish_'), aged(tmp_path/'staging'/'user-data'),
            aged(tmp_path/'staging'/'upload-directory'/'user-data')]
    result = scanner(tmp_path/'staging').scan()
    assert not old.exists() and result.bytes == 3
    assert all(p.read_bytes() == b'abc' for p in keep)


@pytest.mark.parametrize('kind', ['staging', 'temp'])
def test_live_root_lease_defers_scan_even_if_mtime_is_old(tmp_path, kind):
    path = aged(tmp_path/'upload-old_____' if kind == 'staging' else tmp_path/'recording-chain-old_____'/'part')
    os.utime(path.parent, (NOW-4000, NOW-4000))
    cleaner = scanner(tmp_path, kind=kind)
    with cleaner.in_use():
        assert cleaner.scan().count == 0
        assert path.exists()
    assert cleaner.scan().count == 1
    assert not path.exists()


def test_nested_partial_tree_young_child_and_unknown_root_entries(tmp_path):
    work = tmp_path/'recording-analysis-old_____'
    old = aged(work/'partial'/'old')
    young = aged(work/'young', 1)
    unknown = aged(tmp_path/'personal-file')
    for directory in (old.parent, work):
        os.utime(directory, (NOW-4000, NOW-4000))
    cleaner = scanner(tmp_path, kind='temp')
    assert cleaner.scan().count == 1
    assert not old.exists() and young.exists() and unknown.exists()
    assert cleaner.scan().count == 0


@pytest.mark.parametrize('mutation', ['refresh', 'replace', 'disappear'])
def test_changed_candidate_between_enumeration_and_delete_is_preserved(tmp_path, monkeypatch, mutation):
    path = aged(tmp_path/'upload-old_____')
    module = api()
    original = module._delete_file
    def change(parent, name, snapshot, cutoff):
        if mutation == 'refresh':
            os.utime(path, (NOW, NOW))
        else:
            path.unlink()
            if mutation == 'replace':
                aged(path, 1, b'new')
        return original(parent, name, snapshot, cutoff)
    monkeypatch.setattr(module, '_delete_file', change)
    result = scanner(tmp_path).scan()
    assert (result.count, result.bytes, result.failed) == (0, 0, 0)
    assert path.exists() is (mutation != 'disappear')


def test_per_file_failure_does_not_abort_scan_or_leak_exception(tmp_path, monkeypatch):
    first = aged(tmp_path/'upload-denied__')
    second = aged(tmp_path/'upload-ok______', data=b'12345')
    module = api()
    original = module._delete_file
    def denied(parent, name, snapshot, cutoff):
        if name == first.name:
            raise PermissionError('PRIVATE case_secret /outside/path password=secret')
        return original(parent, name, snapshot, cutoff)
    monkeypatch.setattr(module, '_delete_file', denied)
    result = scanner(tmp_path).scan()
    assert first.exists() and not second.exists()
    assert (result.count, result.bytes, result.failed) == (1, 5, 1)
    assert 'PRIVATE' not in repr(result)


def link_directory(link, target):
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                                capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize('location', ['root', 'ancestor', 'child'])
def test_symlink_or_junction_never_traverses_outside(tmp_path, location):
    outside = tmp_path/'outside'
    keep = aged((outside/'nested' if location == 'ancestor' else outside)/'upload-keep____')
    root = tmp_path/'root'
    root.mkdir()
    if location == 'child':
        link_directory(root/'recording-analysis-link____', outside)
        cleaner = scanner(root, kind='temp')
    else:
        link_directory(root/'link', outside)
        cleaner = scanner(root/'link' if location == 'root' else root/'link'/'nested')
    result = cleaner.scan()
    assert result.count == 0 and keep.read_bytes() == b'abc'


def test_dotdot_root_is_rejected_before_touching_files(tmp_path):
    keep = aged(tmp_path/'upload-keep')
    with pytest.raises(ValueError):
        scanner(tmp_path/'nested'/'..')
    assert keep.exists()


def test_duplicate_scan_calls_never_double_count(tmp_path, monkeypatch):
    aged(tmp_path/'upload-old_____')
    module = api()
    entered, release = Event(), Event()
    original = module._delete_file
    def pause(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(module, '_delete_file', pause)
    cleaner = scanner(tmp_path)
    results = []
    thread = Thread(target=lambda: results.append(cleaner.scan()))
    try:
        thread.start()
        assert entered.wait(5)
        assert cleaner.scan().count == 0
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert [(r.count, r.bytes) for r in results] == [(1, 3)]


def test_process_interruption_releases_live_lease_for_later_cleanup(tmp_path):
    aged(tmp_path/'upload-old_____')
    cleaner = scanner(tmp_path)
    code = '''
import sys
from daesingo.common.storage.cleanup import CleanupScanner
c = CleanupScanner(root=sys.argv[1], kind='staging', age_sec=3600)
with c.in_use():
    print('ready', flush=True)
    sys.stdin.read()
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[3]/'src'))
    child = subprocess.Popen([sys.executable, '-u', '-c', code, str(tmp_path)], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
    ready = Event()
    lines = []
    def read_ready():
        lines.append(child.stdout.readline().strip())
        ready.set()
    reader = Thread(target=read_ready)
    try:
        reader.start()
        assert ready.wait(5) and lines == ['ready']
        assert cleaner.scan().count == 0
        child.kill()
        child.communicate(timeout=10)
        assert cleaner.scan().count == 1
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
        reader.join(5)
        assert not reader.is_alive()


def test_lookalike_names_and_temp_root_files_are_not_owned_residues(tmp_path):
    keep = [aged(tmp_path/'upload-user-document'),
            aged(tmp_path/'recording-analysis-user-document'/'private'),
            aged(tmp_path/'recording-analysis-abcdefgh')]
    os.utime(keep[1].parent, (NOW-4000, NOW-4000))
    assert scanner(tmp_path).scan().count == 0
    assert scanner(tmp_path, kind='temp').scan().count == 0
    assert all(path.read_bytes() == b'abc' for path in keep)


def test_hardlink_never_deletes_an_alias_of_external_content(tmp_path):
    outside = aged(tmp_path/'outside'/'private')
    root = tmp_path/'root'
    root.mkdir()
    linked = root/'upload-abcdefgh'
    os.link(outside, linked)
    assert scanner(root).scan().count == 0
    assert linked.exists() and outside.read_bytes() == b'abc'


def test_readonly_failure_is_isolated_and_counts_only_actual_removals(tmp_path):
    readonly = aged(tmp_path/'upload-readonly')
    other = aged(tmp_path/'upload-abcdefgh', data=b'12345')
    import stat
    readonly.chmod(stat.S_IREAD)
    try:
        result = scanner(tmp_path).scan()
        assert not other.exists()
        if os.name == 'nt':
            assert readonly.exists()
            assert (result.count, result.bytes, result.failed) == (1, 5, 1)
        else:
            assert not readonly.exists()
            assert (result.count, result.bytes, result.failed) == (2, 8, 0)
    finally:
        if readonly.exists():
            readonly.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_open_media_reader_is_not_marked_for_deferred_windows_deletion(tmp_path):
    path = aged(tmp_path/'upload-abcdefgh')
    cleaner = scanner(tmp_path)
    if os.name == 'nt':
        # Deliberately permit FILE_SHARE_DELETE in the existing reader: the
        # scanner must refuse a live file rather than merely mark it pending.
        from daesingo.common.storage import _filesystem as fs
        from ctypes import wintypes
        handle = fs._create(str(path), 0x80000000, 7, None, 3, 0, None)
        assert handle != wintypes.HANDLE(-1).value
        try:
            result = cleaner.scan()
            assert (result.count, result.bytes) == (0, 0)
            assert path.exists()
        finally:
            fs._close(handle)
    else:
        with path.open('rb'), cleaner.in_use():
            assert cleaner.scan().count == 0
    assert cleaner.scan().count == 1
