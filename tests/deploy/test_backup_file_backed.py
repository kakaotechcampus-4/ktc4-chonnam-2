"""Bounded file transport and integrity controls; no Docker or MySQL is run."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from test_backup_compose import module, SQL


LIMIT = 1024 * 1024


class BoundedBytes(io.BytesIO):
    def read(self, size=-1):
        assert 0 <= size <= LIMIT, "SQL read must be bounded to 1MiB"
        return super().read(size)

    def readline(self, size=-1):
        assert 0 <= size <= LIMIT, "header read must be bounded"
        return super().readline(size)

    def write(self, data):
        assert len(data) <= LIMIT, "SQL write must be bounded to 1MiB"
        return super().write(data)


def file_transport(m, data=SQL, *, heads=None, after_import=None, failure=None):
    calls = []

    def run(command, **kwargs):
        record = dict(kwargs)
        calls.append((command, record))
        assert kwargs["timeout"] == 600
        if "ps" in command:
            return SimpleNamespace(returncode=0, stdout=b"[]", stderr=b"")
        assert not kwargs.get("capture_output"), (
            "large SQL must go to a file, not capture_output"
        )
        assert "input" not in kwargs, "SQL import must use file stdin"
        out = kwargs["stdout"]
        out.fileno()  # subprocess receives a real file descriptor
        stdin = kwargs.get("stdin")
        if stdin is not None and stdin != subprocess.DEVNULL:
            assert stdin.readable() and not stdin.writable(), (
                "validated SQL stdin must be readonly"
            )
            record["stdin_data"] = stdin.read(LIMIT)
            assert stdin.read(1) == b""  # small import fixture in these tests
            if after_import:
                after_import()
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 600, output=b"private-canary")
        if failure == "cancel":
            raise KeyboardInterrupt("private-canary")
        revisions = m.migration_heads() if heads is None else heads
        out.write(
            "".join(k + "\t" + v + "\n" for k, v in sorted(revisions.items())).encode()
        )
        out.write(m.SEPARATOR)
        if failure == "nonzero":
            out.write(data[:4])
            return SimpleNamespace(returncode=7)
        out.write(data)
        return SimpleNamespace(returncode=0)

    return run, calls


def test_large_envelope_uses_only_bounded_reads_writes():
    m = module()
    assert callable(getattr(m, "pack_file", None)), (
        "file-backed artifact encoder missing"
    )
    assert callable(getattr(m, "unpack_file", None)), (
        "file-backed artifact validator missing"
    )
    data = b"x" * (2 * LIMIT + 17)
    artifact = BoundedBytes()
    m.pack_file(BoundedBytes(data), artifact, m.migration_heads())
    artifact.seek(0)
    restored = BoundedBytes()
    m.unpack_file(artifact, restored, m.migration_heads())
    assert restored.getvalue() == data


@pytest.mark.parametrize("helper", ["pack", "unpack"])
def test_bytes_compatibility_helpers_cannot_accept_large_sql(helper):
    m = module()
    data = b"x" * (LIMIT + 1)
    if helper == "pack":
        with pytest.raises(m.BackupError):
            m.pack(data, m.migration_heads())
    else:
        header = {
            "format": 1,
            "database": "daesingo",
            "heads": m.migration_heads(),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        artifact = m.MAGIC + json.dumps(header).encode() + b"\n" + data
        with pytest.raises(m.BackupError):
            m.unpack(artifact, m.migration_heads())


def test_runtime_uses_file_output_and_readonly_file_stdin(tmp_path, monkeypatch):
    m = module()
    run, calls = file_transport(m)

    def forbidden(*args, **kwargs):
        pytest.fail("runtime must not use byte pack/unpack")

    monkeypatch.setattr(m, "pack", forbidden)
    monkeypatch.setattr(m, "unpack", forbidden)
    t = m.LogicalBackup(["docker", "compose"], run=run)
    t.backup(tmp_path)
    before = (tmp_path / m.ARTIFACT).read_bytes()
    t.restore(tmp_path)
    assert [r["stdin_data"] for _, r in calls if "stdin_data" in r] == [SQL]
    assert (tmp_path / m.ARTIFACT).read_bytes() == before
    assert set(p.name for p in tmp_path.iterdir()) == {m.ARTIFACT}


@pytest.mark.parametrize(
    "damage",
    [
        "truncate",
        "trailing",
        "hash",
        "heads",
        "size_bool",
        "format_bool",
        "header_large",
        "empty_sql",
    ],
)
def test_file_validation_rejects_before_any_docker(tmp_path, damage):
    m = module()
    header = {
        "format": 1,
        "database": "daesingo",
        "heads": m.migration_heads(),
        "size": len(SQL),
        "sha256": hashlib.sha256(SQL).hexdigest(),
    }
    data = SQL
    if damage == "truncate":
        data = data[:-1]
    elif damage == "trailing":
        data += b"extra"
    elif damage == "hash":
        header["sha256"] = "0" * 64
    elif damage == "heads":
        header["heads"]["recording"] = "recording_0001"
    elif damage == "size_bool":
        header["size"] = True
    elif damage == "format_bool":
        header["format"] = True
    elif damage == "header_large":
        header["padding"] = "x" * 65537
    elif damage == "empty_sql":
        data = b""
        header["size"] = 0
        header["sha256"] = hashlib.sha256(b"").hexdigest()
    artifact = m.MAGIC + json.dumps(header).encode() + b"\n" + data
    (tmp_path / m.ARTIFACT).write_bytes(artifact)

    def forbidden(*a, **k):
        pytest.fail("invalid artifact must precede Docker")

    with pytest.raises(m.BackupError):
        m.LogicalBackup(["docker"], run=forbidden).restore(tmp_path)
    assert (tmp_path / m.ARTIFACT).read_bytes() == artifact
    assert set(p.name for p in tmp_path.iterdir()) == {m.ARTIFACT}


@pytest.mark.parametrize("failure", ["timeout", "cancel", "nonzero"])
def test_failed_file_transport_only_removes_its_own_files(tmp_path, failure):
    m = module()
    sentinel = tmp_path / "caller-evidence"
    sentinel.write_bytes(b"preserve")
    run, _ = file_transport(m, failure=failure)
    with pytest.raises((m.BackupError, KeyboardInterrupt)):
        m.LogicalBackup(["docker"], run=run).backup(tmp_path)
    assert sentinel.read_bytes() == b"preserve"
    assert set(p.name for p in tmp_path.iterdir()) == {"caller-evidence"}


def test_same_length_redump_mismatch_is_not_accepted(tmp_path):
    m = module()
    artifact = m.pack(SQL, m.migration_heads())
    (tmp_path / m.ARTIFACT).write_bytes(artifact)
    run, _ = file_transport(m, data=SQL[:-1] + b"?")
    with pytest.raises(m.BackupError, match="restored_state_mismatch"):
        m.LogicalBackup(["docker"], run=run).restore(tmp_path)
    assert (tmp_path / m.ARTIFACT).read_bytes() == artifact
    assert set(p.name for p in tmp_path.iterdir()) == {m.ARTIFACT}


def source_root(tmp_path, recording):
    root = tmp_path / recording
    for name, head in [
        ("case", "case_0001"),
        ("runtime", "runtime_0006"),
        ("recording", recording),
    ]:
        directory = root / "migrations" / name / "versions"
        directory.mkdir(parents=True)
        (directory / "head.py").write_text(f"revision={head!r}\ndown_revision=None\n")
    return root


@pytest.mark.parametrize("recording", ["recording_0001", "recording_0002"])
def test_explicit_source_root_controls_header_and_db_head_check(tmp_path, recording):
    m = module()
    root = source_root(tmp_path, recording)
    heads = {"case": "case_0001", "runtime": "runtime_0006", "recording": recording}
    run, _ = file_transport(m, heads=heads)
    t = m.LogicalBackup(["docker"], run=run, source_root=root)
    target = tmp_path / "artifact"
    target.mkdir()
    t.backup(target)
    assert m.unpack((target / m.ARTIFACT).read_bytes(), heads) == SQL
    t.restore(target)


def test_wrong_latest_source_root_is_not_applied_to_old_artifact(tmp_path):
    m = module()
    old = source_root(tmp_path, "recording_0001")
    latest = source_root(tmp_path, "recording_0002")
    heads = {
        "case": "case_0001",
        "runtime": "runtime_0006",
        "recording": "recording_0001",
    }
    (tmp_path / m.ARTIFACT).write_bytes(m.pack(SQL, heads))

    def forbidden(*a, **k):
        pytest.fail("wrong source heads must reject before Docker")

    with pytest.raises(m.BackupError):
        m.LogicalBackup(["docker"], run=forbidden, source_root=latest).restore(tmp_path)
    assert old.exists() and latest.exists()


def test_host_cli_requires_explicit_source_root(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(
        m,
        "LogicalBackup",
        lambda *a, **k: pytest.fail("missing source root must reject CLI"),
    )
    assert m.main(["backup", "--project", "test", "--directory", str(tmp_path)]) == 1


def test_cleanup_cannot_unlink_replacement_caller_file(tmp_path):
    m = module()
    remove = getattr(m, "remove_owned", None)
    assert callable(remove), "owned-inode cleanup missing"
    path = tmp_path / "owned"
    path.write_bytes(b"ours")
    identity = path.stat()
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"caller")
    path.unlink()
    replacement.rename(path)
    remove(path, identity)
    assert path.read_bytes() == b"caller"


def test_dump_options_remain_current_not_measured_e50_profile():
    m = module()
    assert "--hex-blob" in m.remote_script("backup")
    assert "--skip-extended-insert" in m.remote_script("backup")


def shell_restore(
    tmp_path,
    *,
    client_packet=67108864,
    server_packet=67108864,
    objects=0,
    import_error=0,
    occupied_lock=False,
    help_error=0,
):
    """Run the actual generated shell with small local mysql/dump functions only."""
    m = module()
    bash = (
        Path("C:/Program Files/Git/bin/bash.exe")
        if os.name == "nt"
        else Path("/bin/sh")
    )
    assert bash.is_file(), "offline shell required; do not skip packet guards"
    lock = tmp_path / "lock"
    if occupied_lock:
        lock.mkdir()
        (lock / "caller").write_bytes(b"preserve")
    secret = tmp_path / "password"
    secret.write_text("synthetic-test-secret")
    marker = tmp_path / "imported"
    dumped = tmp_path / "dumped"
    preamble = f"""
timeout() {{ [ "$1" = 180 ] || exit 98; shift; "$@"; }}
mysql() {{
    case " $* " in *' --max-allowed-packet=67108864 '*) ;; *) return 97;; esac
    case "$*" in
      *'--verbose --help'*) printf 'max-allowed-packet {client_packet}\\n'; return {help_error};;
      *'SELECT VERSION()'*) printf '8.4.7\\n';;
      *'SELECT @@GLOBAL'*) printf '{server_packet}\\t{server_packet}\\n';;
      *'information_schema.tables'*) printf '{objects}\\n';;
      *'case_alembic_version'*) printf 'case\\tcase_0001\\nrecording\\trecording_0002\\nruntime\\truntime_0006\\n';;
      *) cat > '{marker.as_posix()}'; return {import_error};;
    esac
}}
mysqldump() {{ printf 'invoked' > '{dumped.as_posix()}'; printf 'synthetic SQL\\n'; }}
"""
    script = m.remote_script("restore").replace(
        "/tmp/daesingo-rt13-logical.lock", lock.as_posix()
    )
    script = script.replace("/run/secrets/mysql-password", secret.as_posix())
    script_path = tmp_path / "offline-shell.sh"
    script_path.write_text(preamble + script, encoding="utf-8", newline="\n")
    result = subprocess.run(
        [str(bash), str(script_path)], input=SQL, capture_output=True, timeout=10
    )
    return result, lock, marker, dumped


@pytest.mark.parametrize(
    "client,server", [(16777216, 67108864), (67108864, 33554432), (67108864, 134217728)]
)
def test_remote_packet_mismatch_rejects_before_import(tmp_path, client, server):
    result, lock, marker, dumped = shell_restore(
        tmp_path, client_packet=client, server_packet=server
    )
    assert result.returncode == 26
    assert not marker.exists() and not dumped.exists() and not lock.exists()


def test_remote_packet_probe_command_error_is_not_ignored(tmp_path):
    result, lock, marker, dumped = shell_restore(tmp_path, help_error=3)
    assert result.returncode == 3
    assert not marker.exists() and not dumped.exists() and not lock.exists()


def test_remote_matching_packet_import_and_redump(tmp_path):
    result, lock, marker, dumped = shell_restore(tmp_path)
    assert result.returncode == 0, result.stderr
    assert marker.read_bytes() == SQL and dumped.exists() and not lock.exists()
    assert result.stdout.endswith(b"__RT13_SQL__\nsynthetic SQL\n")


@pytest.mark.parametrize("failure", ["nonempty", "partial", "caller_lock"])
def test_remote_empty_target_partial_failure_and_lock_cleanup(tmp_path, failure):
    result, lock, marker, dumped = shell_restore(
        tmp_path,
        objects=1 if failure == "nonempty" else 0,
        import_error=3 if failure == "partial" else 0,
        occupied_lock=failure == "caller_lock",
    )
    assert (
        result.returncode == {"nonempty": 24, "partial": 3, "caller_lock": 20}[failure]
    )
    assert marker.exists() == (failure == "partial")
    assert not dumped.exists()
    if failure == "caller_lock":
        assert (lock / "caller").read_bytes() == b"preserve"
    else:
        assert not lock.exists()


def test_sql_disk_write_failure_cleans_spool_without_docker(tmp_path, monkeypatch):
    m = module()
    artifact = m.pack(SQL, m.migration_heads())
    (tmp_path / m.ARTIFACT).write_bytes(artifact)

    def failed(*a, **k):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(m, "unpack_file", failed)
    with pytest.raises(m.BackupError):
        m.LogicalBackup(
            ["docker"], run=lambda *a, **k: pytest.fail("no DB before validation")
        ).restore(tmp_path)
    assert (tmp_path / m.ARTIFACT).read_bytes() == artifact
    assert set(p.name for p in tmp_path.iterdir()) == {m.ARTIFACT}


def test_import_uses_validated_snapshot_not_reopened_caller_artifact(tmp_path):
    m = module()
    path = tmp_path / m.ARTIFACT
    path.write_bytes(m.pack(SQL, m.migration_heads()))
    run, calls = file_transport(
        m, after_import=lambda: path.write_bytes(b"caller replacement")
    )
    m.LogicalBackup(["docker"], run=run).restore(tmp_path)
    assert [r["stdin_data"] for _, r in calls if "stdin_data" in r] == [SQL]
    assert path.read_bytes() == b"caller replacement"


@pytest.mark.parametrize("failure", ["timeout", "cancel", "nonzero"])
def test_restore_transport_failure_preserves_artifact_and_cleans_spools(
    tmp_path, failure
):
    m = module()
    artifact = m.pack(SQL, m.migration_heads())
    (tmp_path / m.ARTIFACT).write_bytes(artifact)
    run, _ = file_transport(m, failure=failure)
    with pytest.raises((m.BackupError, KeyboardInterrupt)):
        m.LogicalBackup(["docker"], run=run).restore(tmp_path)
    assert (tmp_path / m.ARTIFACT).read_bytes() == artifact
    assert set(p.name for p in tmp_path.iterdir()) == {m.ARTIFACT}


def test_backup_fsync_failure_does_not_leave_success_artifact(tmp_path, monkeypatch):
    m = module()
    run, _ = file_transport(m)

    def failed(*args):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(m.os, "fsync", failed)
    with pytest.raises(OSError):
        m.LogicalBackup(["docker"], run=run).backup(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_comparison_is_bounded_and_checks_end_bytes():
    m = module()
    data = b"x" * (2 * LIMIT + 17)
    assert m.same_bytes(BoundedBytes(data), BoundedBytes(data))
    assert not m.same_bytes(BoundedBytes(data), BoundedBytes(data + b"extra"))
    assert not m.same_bytes(BoundedBytes(data), BoundedBytes(data[:-1] + b"?"))


def test_source_db_heads_mismatch_removes_owned_backup(tmp_path):
    m = module()
    root = source_root(tmp_path, "recording_0001")
    artifact_dir = tmp_path / "backup"
    artifact_dir.mkdir()
    run, _ = file_transport(m)  # actual source expectation is old; DB prefix is current
    with pytest.raises(m.BackupError, match="migration_or_dump_mismatch"):
        m.LogicalBackup(["docker"], run=run, source_root=root).backup(artifact_dir)
    assert list(artifact_dir.iterdir()) == []
