"""Existing materializer constructor injection and close/cancellation scope."""
from importlib import import_module
import os
from pathlib import Path
import tempfile

import pytest
from test_cleanup import NOW, scanner
from test_cleanup_publish_safety import link_directory, path_alias


@pytest.mark.parametrize('outcome', ['success', 'exception', 'cancel'])
def test_materializer_receives_explicit_root_and_live_lease_until_finally(tmp_path, outcome):
    try:
        module = import_module('daesingo.common.storage.media')
    except ModuleNotFoundError:
        pytest.fail('Runtime temp_root injection and active scope missing')
    cleaner = scanner(tmp_path, kind='temp')
    class Cancel(BaseException):
        pass
    class Producer:
        def __init__(self, *, temp_root):
            self.root = temp_root
        def materialize(self):
            assert self.root == tmp_path
            with tempfile.TemporaryDirectory(prefix='recording-analysis-', dir=self.root) as work:
                path = Path(work)/'partial'
                path.write_bytes(b'abc')
                for p in (path, Path(work)):
                    os.utime(p, (NOW-4000, NOW-4000))
                assert cleaner.scan().count == 0
                assert path.read_bytes() == b'abc'
                if outcome == 'exception':
                    raise ValueError('PRIVATE')
                if outcome == 'cancel':
                    raise Cancel()
                return b'abc'
    producer = module.MediaRoot(cleaner).materializer(Producer)
    if outcome == 'success':
        assert producer.materialize() == b'abc'
    else:
        with pytest.raises(ValueError if outcome == 'exception' else Cancel):
            producer.materialize()
    assert not list(tmp_path.glob('recording-*'))
    assert cleaner.scan().count == 0


def test_media_refuses_configured_root_with_different_canonical_identity(tmp_path):
    from daesingo.common.storage._filesystem import configuration_path
    from daesingo.common.storage.media import MediaRoot

    configured, other = tmp_path/'configured', tmp_path/'other'
    configured.mkdir()
    other.mkdir()
    cleaner = scanner(configured, kind='temp')
    cleaner.root = configuration_path(other)
    with pytest.raises(OSError, match='unverifiable media root') as caught:
        MediaRoot(cleaner).materializer(lambda **kwargs: object())
    assert str(configured) not in str(caught.value)
    assert str(other) not in str(caught.value)
    assert not list(other.iterdir())


@pytest.mark.parametrize('spelling', ['namespace', 'separators', 'dot'] +
                         (['case', 'short', 'volume'] if os.name == 'nt' else []))
def test_media_aliases_keep_ordinary_io_under_canonical_lease(tmp_path, spelling):
    from daesingo.common.storage._filesystem import configuration_path
    from daesingo.common.storage.media import MediaRoot

    work = tmp_path/'long media directory'
    work.mkdir()
    canonical = configuration_path(work)
    configured = canonical if spelling == 'volume' else path_alias(work, spelling)
    cleaner = scanner(canonical, kind='temp', configured_root=configured)

    class Producer:
        def __init__(self, *, temp_root):
            self.root = temp_root

        def materialize(self):
            assert self.root.is_absolute()
            assert not str(self.root).startswith('\\\\?\\')
            assert os.path.samefile(self.root, work)
            with tempfile.TemporaryDirectory(prefix='recording-analysis-', dir=self.root) as name:
                path = Path(name)/'part'
                path.write_bytes(b'owned')
                for item in (path, path.parent):
                    os.utime(item, (1, 1))
                assert cleaner.scan().count == 0
                return path.read_bytes()

    assert MediaRoot(cleaner).materializer(Producer).materialize() == b'owned'
    assert cleaner.scan().count == 0


def test_tool_path_must_also_match_pinned_canonical_identity(tmp_path, monkeypatch):
    from daesingo.common.storage import media

    other = tmp_path/'other'
    other.mkdir()
    monkeypatch.setattr(media, 'tool_directory', lambda directory: other)
    with pytest.raises(OSError, match='unverifiable media root'):
        media.MediaRoot(scanner(tmp_path, kind='temp')).materializer(lambda **kwargs: object())
    assert not list(other.iterdir())


def test_media_revalidates_root_before_invocation_and_releases_pins(tmp_path, caplog):
    from daesingo.common.storage.media import MediaRoot

    work, outside, moved = tmp_path/'work', tmp_path/'outside', tmp_path/'moved'
    work.mkdir()
    outside.mkdir()
    keep = outside/'private-original-name.mp4'
    keep.write_bytes(b'keep')

    class Producer:
        def __init__(self, **kwargs):
            pass

        def materialize(self):
            pytest.fail('producer must not run through a replaced root')

    producer = MediaRoot(scanner(work, kind='temp')).materializer(Producer)
    work.rename(moved)  # Constructor pins have been released.
    link_directory(work, outside)
    try:
        with pytest.raises(OSError, match='unverifiable media root') as caught:
            producer.materialize()
        assert keep.read_bytes() == b'keep'
        assert all(secret not in str(caught.value) + caplog.text
                   for secret in (str(work), str(outside), keep.name))
    finally:
        if os.name == 'nt':
            work.rmdir()  # Remove this junction only, never traverse its target.
        else:
            work.unlink()
    moved.rename(work)


@pytest.mark.skipif(os.name != 'nt', reason='Windows DOS handle name failure')
def test_unavailable_dos_name_fails_closed_without_path_and_releases_handles(tmp_path, monkeypatch, caplog):
    from daesingo.common.storage import _filesystem as fs
    from daesingo.common.storage.media import MediaRoot

    work = tmp_path/'private-user-root'
    work.mkdir()
    media = MediaRoot(scanner(work, kind='temp'))
    final_name = fs._final_name

    def unavailable(handle, buffer, size, flags):
        return 0 if flags == 0 else final_name(handle, buffer, size, flags)

    monkeypatch.setattr(fs, '_final_name', unavailable)
    with pytest.raises(OSError, match='unverifiable media root') as caught:
        media.materializer(lambda **kwargs: object())
    assert str(work) not in str(caught.value) + caplog.text
    work.rename(tmp_path/'released')
