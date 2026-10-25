"""RT-12(a) P1: an injected temp ancestor must never reclaim published bytes."""
from io import StringIO
import os
from pathlib import Path
from threading import enumerate as threads

import pytest

from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.storage import cleanup
from test_cleanup import link_directory


def config(service, media, temp):
    return RuntimeConfig.from_mapping(service, {
        'DAESINGO_RUNTIME_DB_URL': 'mysql+pymysql://test@127.0.0.1:1/test_cleanup',
        'DAESINGO_RUNTIME_MEDIA_ROOT': str(media),
        'DAESINGO_RUNTIME_'+service.upper()+'_TEMP_ROOT': str(temp),
    })


def published(media):
    path = media/'source'/'registered-media'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'published')
    for item in (path, path.parent, media):
        os.utime(item, (1, 1))
    return path


@pytest.mark.parametrize('service', ['api', 'worker'])
def test_publish_under_matching_temp_ancestor_is_never_deleted(tmp_path, service):
    # Exact review repro: the enclosing media directory matches a temp name.
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    owner = cleanup.configured_cleanup(config(service, media, tmp_path),
                                        configure_logging(service, stream=StringIO()))
    temp = next(s for s in owner.scanners if s.kind == 'temp')
    result = temp.scan()
    assert path.exists(), f'published data deleted: {result}'
    assert path.read_bytes() == b'published'
    assert (result.count, result.bytes, result.failed) == (0, 0, 0)
    assert temp.scan().count == 0


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('relation', ['separate', 'same', 'below', 'above'])
def test_publish_root_relationships_and_startup_ownership(tmp_path, service, relation):
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    if relation == 'separate':
        temp = tmp_path/'temp'
        temp.mkdir()
    elif relation == 'same':
        temp = path.parent
    elif relation == 'below':
        temp = path.parent/'nested'
    else:
        temp = tmp_path
    before = {t.ident for t in threads() if t.name == 'runtime-cleanup'}
    if relation in ('same', 'below'):
        with pytest.raises(ValueError):
            cleanup.configured_cleanup(config(service, media, temp),
                                        configure_logging(service, stream=StringIO()))
    else:
        work = temp/'recording-chain-12345678'
        work.mkdir()
        residue = work/'partial'
        residue.write_bytes(b'abc')
        for item in (residue, work):
            os.utime(item, (1, 1))
        owner = cleanup.configured_cleanup(config(service, media, temp),
                                            configure_logging(service, stream=StringIO()))
        try:
            owner.start()
            assert not residue.exists()
            assert path.read_bytes() == b'published'
        finally:
            owner.stop_and_join()
        assert not owner.thread.is_alive()
    assert {t.ident for t in threads() if t.name == 'runtime-cleanup'} == before
    assert path.read_bytes() == b'published'


@pytest.mark.parametrize('service', ['api', 'worker'])
def test_relative_and_normalized_ancestor_still_protects_publish(tmp_path, monkeypatch, service):
    monkeypatch.chdir(tmp_path)
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    owner = cleanup.configured_cleanup(
        config(service, Path('./recording-analysis-abcdefgh/.'), Path('./.')),
        configure_logging(service, stream=StringIO()))
    assert next(s for s in owner.scanners if s.kind == 'temp').scan().count == 0
    assert path.read_bytes() == b'published'
    # Existing parent-traversal rejection remains fail-closed, even if the
    # normalized path would point back to this directory.
    with pytest.raises(ValueError):
        cleanup.configured_cleanup(config(service, media, Path('nested/..')),
                                    configure_logging(service, stream=StringIO()))


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('aliased', ['temp', 'media', 'publish'])
def test_link_alias_configuration_is_rejected_before_cleanup_owner_exists(tmp_path, monkeypatch, service, aliased):
    real = tmp_path/'real'
    real.mkdir()
    media = real/'recording-analysis-abcdefgh'
    path = published(media)
    temp = real
    alias = tmp_path/'alias'
    if aliased == 'temp':
        link_directory(alias, real)
        temp = alias
    elif aliased == 'media':
        link_directory(alias, media)
        media = alias
    else:
        # A publish directory that is a link is unsafe even when no temp name
        # happens to match today. Reject before allocating a scan lifecycle.
        path.unlink()
        path.parent.rmdir()
        external = tmp_path/'published'
        external.mkdir()
        path = external/'registered-media'
        path.write_bytes(b'published')
        link_directory(media/'source', external)
    allocated = []
    original = cleanup.CleanupService
    def allocate(**kwargs):
        allocated.append(True)
        return original(**kwargs)
    monkeypatch.setattr(cleanup, 'CleanupService', allocate)
    with pytest.raises(ValueError):
        cleanup.configured_cleanup(config(service, media, temp),
                                    configure_logging(service, stream=StringIO()))
    assert allocated == []
    assert path.read_bytes() == b'published'


def path_alias(path, spelling):
    text = str(path)
    if spelling == 'namespace':
        return '\\\\?\\' + text if os.name == 'nt' else '/' + text
    if spelling == 'case':
        return text.swapcase()
    if spelling == 'separators':
        return text.replace('\\', '//') if os.name == 'nt' else text.replace('/', '///')
    if spelling == 'dot':
        return str(path.parent) + os.sep + '.' + os.sep + path.name
    if spelling == 'short':
        import ctypes
        from ctypes import wintypes
        get_short = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        get_short.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
        get_short.restype = wintypes.DWORD
        size = get_short(text, None, 0)
        if not size:
            pytest.skip('volume does not provide a short name')
        buffer = ctypes.create_unicode_buffer(size + 1)
        used = get_short(text, buffer, len(buffer))
        assert 0 < used < len(buffer)
        if '~' not in buffer.value:
            pytest.skip('8.3 short-name generation is unavailable on this volume')
        return buffer.value
    raise AssertionError(spelling)


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('combination', ['normal', 'media-alias', 'temp-alias', 'both-alias'])
@pytest.mark.parametrize('spelling', ['namespace', 'separators', 'dot'] + (['case', 'short'] if os.name == 'nt' else []))
def test_os_confirmed_aliases_preserve_publish_and_reclaim_only_outside(tmp_path, service, combination, spelling):
    # This catches a lexical-only protection comparison. samefile proves the
    # spelling aliases real OS objects before any product behavior is asserted.
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    media_arg = path_alias(media, spelling) if combination in ('media-alias', 'both-alias') else str(media)
    temp_arg = path_alias(tmp_path, spelling) if combination in ('temp-alias', 'both-alias') else str(tmp_path)
    assert os.path.samefile(media_arg, media)
    assert os.path.samefile(temp_arg, tmp_path)
    # A component prefix is not a protected branch.
    other = tmp_path/'recording-chain-12345678'
    other.mkdir()
    residue = other/'partial'
    residue.write_bytes(b'abc')
    for item in (residue, other):
        os.utime(item, (1, 1))
    before = {t.ident for t in threads() if t.name == 'runtime-cleanup'}
    owner = cleanup.configured_cleanup(config(service, media_arg, temp_arg),
                                        configure_logging(service, stream=StringIO()))
    temp = next(s for s in owner.scanners if s.kind == 'temp')
    result = temp.scan()
    assert path.exists(), f'publish deleted via {spelling}/{combination}: {result}'
    assert path.read_bytes() == b'published'
    assert path.parent.is_dir() and media.is_dir()
    assert (result.count, result.bytes, result.failed) == (1, 3, 0)
    assert other.name not in {p.name for p in tmp_path.iterdir()}
    again = temp.scan()
    assert (again.count, again.bytes, again.failed) == (0, 0, 0)
    try:
        owner.start()
        assert path.read_bytes() == b'published'
    finally:
        owner.stop_and_join()
    assert not owner.thread.is_alive()
    assert {t.ident for t in threads() if t.name == 'runtime-cleanup'} == before


@pytest.mark.parametrize('service', ['api', 'worker'])
def test_parent_traversal_alias_is_rejected_without_lifecycle_or_lease(tmp_path, monkeypatch, service):
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    (tmp_path/'nested').mkdir()
    alias = str(tmp_path) + os.sep + 'nested' + os.sep + '..'
    assert os.path.samefile(alias, tmp_path)
    before = {t.ident for t in threads() if t.name == 'runtime-cleanup'}
    def unexpected_owner(**kwargs):
        pytest.fail('parent traversal allocated a lifecycle')
    monkeypatch.setattr(cleanup, 'CleanupService', unexpected_owner)
    with pytest.raises(ValueError):
        cleanup.configured_cleanup(config(service, media, alias),
                                    configure_logging(service, stream=StringIO()))
    assert not list(tmp_path.rglob('.runtime-cleanup-*.lock'))
    assert {t.ident for t in threads() if t.name == 'runtime-cleanup'} == before
    assert path.read_bytes() == b'published'


@pytest.mark.parametrize('service', ['api', 'worker'])
def test_component_boundary_does_not_protect_unrelated_staging(tmp_path, service):
    media = tmp_path/'media'
    path = published(media)
    # 'source' and 'staging' share a parent, not an ancestor relationship.
    staging = media/'staging'
    staging.mkdir()
    old = staging/'upload-abcdefgh'
    old.write_bytes(b'abc')
    os.utime(old, (1, 1))
    temp = media/'source-copy'
    temp.mkdir()
    work = temp/'recording-chain-12345678'
    work.mkdir()
    residue = work/'partial'
    residue.write_bytes(b'12345')
    for item in (residue, work):
        os.utime(item, (1, 1))
    owner = cleanup.configured_cleanup(config(service, media, temp),
                                        configure_logging(service, stream=StringIO()))
    result = next(s for s in owner.scanners if s.kind == 'temp').scan()
    assert (result.count, result.bytes, result.failed) == (1, 5, 0)
    assert work.name not in {p.name for p in temp.iterdir()}
    if service == 'api':
        result = owner.scanners[0].scan()
        assert (result.count, result.bytes, result.failed) == (1, 3, 0)
        assert not old.exists()
    else:
        owner.start()
        owner.stop_and_join()
        assert old.read_bytes() == b'abc'
    assert path.read_bytes() == b'published'


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('changed', ['root', 'publish-ancestor'])
def test_after_configuration_replacement_with_link_cannot_redirect_scan(tmp_path, service, changed):
    root = tmp_path/'root'
    root.mkdir()
    media = root/'recording-analysis-abcdefgh'
    path = published(media)
    outside = tmp_path/'outside'
    outside.mkdir()
    keep = published(outside/'recording-chain-12345678')
    owner = cleanup.configured_cleanup(config(service, media, root),
                                        configure_logging(service, stream=StringIO()))
    target = root if changed == 'root' else media
    moved = tmp_path/'moved'
    target.rename(moved)
    link_directory(target, outside)
    result = next(s for s in owner.scanners if s.kind == 'temp').scan()
    assert (result.count, result.bytes) == (0, 0)
    assert result.failed == (1 if changed == 'root' else 0)
    assert keep.read_bytes() == b'published'
    preserved = moved/'recording-analysis-abcdefgh'/'source'/'registered-media' if changed == 'root' else moved/'source'/'registered-media'
    assert preserved.read_bytes() == b'published'


@pytest.mark.skipif(os.name != 'nt', reason='Windows namespace policy')
@pytest.mark.parametrize('temp', [r'\\localhost\rt12a-no-share', r'\\?\UNC\localhost\rt12a-no-share',
                                 r'\\.\C:\rt12a', 'missing. ', 'missing~1'])
def test_unverifiable_windows_namespaces_and_suffixes_fail_before_io_owner(tmp_path, monkeypatch, temp):
    media = tmp_path/'media'
    path = published(media)
    temp = temp if temp.startswith('\\') else str(tmp_path/temp)
    def unexpected_owner(**kwargs):
        pytest.fail('unverifiable path allocated a lifecycle')
    monkeypatch.setattr(cleanup, 'CleanupService', unexpected_owner)
    with pytest.raises(ValueError):
        cleanup.configured_cleanup(config('worker', media, temp),
                                    configure_logging('worker', stream=StringIO()))
    assert not list(tmp_path.rglob('.runtime-cleanup-*.lock'))
    assert path.read_bytes() == b'published'


@pytest.mark.skipif(os.name != 'nt', reason='Windows handle canonicalization')
def test_unavailable_handle_canonicalization_fails_closed_and_releases_pins(tmp_path, monkeypatch):
    import ctypes
    from ctypes import wintypes
    from daesingo.common.storage import _filesystem as fs
    media = tmp_path/'media'
    published(media)
    before = {t.ident for t in threads() if t.name == 'runtime-cleanup'}
    opened = []
    original_open = fs._handle
    def opened_handle(path, **kwargs):
        handle = original_open(path, **kwargs)
        opened.append(handle)
        return handle
    monkeypatch.setattr(fs, '_handle', opened_handle)
    def unavailable(*args):
        raise PermissionError('PRIVATE /unsafe filename password=secret')
    monkeypatch.setattr(fs, '_canonical_directory', unavailable)
    with pytest.raises(ValueError) as error:
        cleanup.configured_cleanup(config('api', media, tmp_path),
                                    configure_logging('api', stream=StringIO()))
    # Query the actual OS handles, rather than infer leaked Runtime pins from
    # rename, which can also be denied by an unrelated Windows reader.
    get_info = fs._kernel.GetHandleInformation
    get_info.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    get_info.restype = wintypes.BOOL
    assert opened
    for handle in opened:
        flags = wintypes.DWORD()
        ctypes.set_last_error(0)
        assert not get_info(handle, ctypes.byref(flags))
        assert ctypes.get_last_error() == 6  # ERROR_INVALID_HANDLE
    assert 'PRIVATE' not in str(error.value)
    assert {t.ident for t in threads() if t.name == 'runtime-cleanup'} == before
    assert not list(tmp_path.rglob('.runtime-cleanup-*.lock'))
    assert (media/'source'/'registered-media').read_bytes() == b'published'


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('combination', ['media-alias', 'temp-alias'])
def test_alias_with_missing_media_and_publish_suffix_is_still_protected(tmp_path, service, combination):
    media = tmp_path/'recording-analysis-abcdefgh'
    media_arg = path_alias(media, 'namespace') if combination == 'media-alias' else str(media)
    temp_arg = path_alias(tmp_path, 'namespace') if combination == 'temp-alias' else str(tmp_path)
    # The nearest existing ancestor has a real identity; descendants do not yet
    # exist. Creation after composition must not defeat publish protection.
    assert os.path.samefile(Path(media_arg).parent, tmp_path)
    owner = cleanup.configured_cleanup(config(service, media_arg, temp_arg),
                                        configure_logging(service, stream=StringIO()))
    path = published(media)
    result = next(s for s in owner.scanners if s.kind == 'temp').scan()
    assert path.exists(), f'late publish deleted: {result}'
    assert (result.count, result.bytes, result.failed) == (0, 0, 0)


@pytest.mark.parametrize('service', ['api', 'worker'])
@pytest.mark.parametrize('relation', ['same', 'below'])
@pytest.mark.parametrize('aliased', ['media', 'temp'])
def test_alias_cannot_bypass_forbidden_target_relation(tmp_path, monkeypatch, service, relation, aliased):
    media = tmp_path/'recording-analysis-abcdefgh'
    path = published(media)
    temp = path.parent if relation == 'same' else path.parent/'nested'
    media_arg = path_alias(media, 'namespace') if aliased == 'media' else str(media)
    temp_arg = path_alias(temp, 'namespace') if aliased == 'temp' else str(temp)
    before = {t.ident for t in threads() if t.name == 'runtime-cleanup'}
    def unexpected_owner(**kwargs):
        pytest.fail('unsafe configuration allocated a lifecycle')
    monkeypatch.setattr(cleanup, 'CleanupService', unexpected_owner)
    with pytest.raises(ValueError):
        cleanup.configured_cleanup(config(service, media_arg, temp_arg),
                                    configure_logging(service, stream=StringIO()))
    assert {t.ident for t in threads() if t.name == 'runtime-cleanup'} == before
    assert not list(tmp_path.rglob('.runtime-cleanup-*.lock'))
    assert path.read_bytes() == b'published'
