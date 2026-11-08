from pathlib import Path
import pytest

from daesingo.common.public_runtime.temporary import case_temp_scope, delete_case_temp
from daesingo.common.storage.cleanup import CleanupScanner
from daesingo.common.storage.media import MediaRoot


def test_recording_factory_uses_owned_case_scope_and_delete_preserves_siblings(tmp_path):
    media = MediaRoot(CleanupScanner(root=tmp_path, kind="temp", age_sec=1))
    protected = tmp_path / "protected-original.mp4"
    protected.write_bytes(b"KEEP")
    token = "a" * 32
    with case_temp_scope(tmp_path, token) as directory:
        with media.detached_temp() as actual:
            assert actual == directory
        (directory / "export-crashed").mkdir()
        (directory / "export-crashed" / "output.mp4").write_bytes(b"DISPOSABLE")
    delete_case_temp(tmp_path, token)
    assert not directory.exists() and protected.read_bytes() == b"KEEP"
    with media.detached_temp() as actual:
        assert actual == tmp_path


def test_unowned_directory_and_traversal_do_not_become_cleanup_targets(tmp_path):
    target = tmp_path / ("a1-" + "b" * 32)
    target.mkdir()
    (target / "protected").write_bytes(b"KEEP")
    with pytest.raises((ValueError, OSError)):
        delete_case_temp(tmp_path, "b" * 32)
    assert (target / "protected").exists()
    with pytest.raises(ValueError):
        delete_case_temp(tmp_path, "../outside")


def test_retry_after_marker_removed_before_rmdir(tmp_path):
    # Durable DB token identifies the exact path. No unknown file may remain.
    token = "c" * 32
    target = tmp_path / ("a1-" + token)
    target.mkdir()
    delete_case_temp(tmp_path, token)
    assert not target.exists()


@pytest.mark.parametrize("partial", [b"", b"ddd"])
def test_partial_marker_from_failed_initialization_is_retryable(tmp_path, partial):
    token = "d" * 32
    target = tmp_path / ("a1-" + token)
    target.mkdir()
    (target / ".owned").write_bytes(partial)
    delete_case_temp(tmp_path, token)
    assert not target.exists()


def test_partial_marker_never_authorizes_removal_of_unknown_contents(tmp_path):
    token = "f" * 32
    target = tmp_path / ("a1-" + token)
    target.mkdir()
    (target / ".owned").write_bytes(b"f")
    protected = target / "unverified"
    protected.write_bytes(b"KEEP")
    with pytest.raises(ValueError):
        delete_case_temp(tmp_path, token)
    assert protected.read_bytes() == b"KEEP"


def test_search_preparer_uses_shared_root_even_with_different_service_temp_roots(tmp_path):
    from daesingo.common.public_runtime.temporary import public_temp_root
    from daesingo.search.media import MediaPreparer
    from daesingo.search.config import GeminiSearchConfig
    media_root, worker_root = tmp_path / "shared-media", tmp_path / "worker-temp"
    media_root.mkdir(); worker_root.mkdir()
    root = public_temp_root(media_root)
    media = MediaRoot(CleanupScanner(root=worker_root, kind="temp", age_sec=1), public_root=root)
    with case_temp_scope(root, "e" * 32) as owned:
        preparer = MediaPreparer(GeminiSearchConfig(), temp_context=media.detached_temp)
        with preparer._temporary_directory() as actual:
            assert actual.parent == owned
            (actual / "synthetic.mp4").write_bytes(b"TEMP")
        assert not actual.exists()
    delete_case_temp(public_temp_root(media_root), "e" * 32)
    assert not owned.exists() and worker_root.exists()
