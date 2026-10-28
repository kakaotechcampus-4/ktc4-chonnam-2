"""Transport fakes test failure boundaries; these are NOT Docker acceptance."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / "scripts/backup_compose.py"
    assert path.is_file(), "RT-13(b) logical backup tool missing"
    spec = importlib.util.spec_from_file_location("logical_backup", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


SQL = b"CREATE TABLE sample(id int primary key);\nINSERT INTO sample VALUES (7);\n"


def transport(m, *, data=SQL, fail=False, active=False, heads=None):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        if "ps" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"Service": "api", "State": "running" if active else "exited"}]).encode(), stderr=b"")
        if fail:
            raise subprocess.CalledProcessError(7, ["private-canary"], stderr=b"private-canary")
        revisions = m.migration_heads() if heads is None else heads
        prefix = "".join(k + "\t" + v + "\n" for k, v in sorted(revisions.items())).encode()
        return SimpleNamespace(returncode=0, stdout=prefix + m.SEPARATOR + data, stderr=b"")
    return run, calls


def tool(m, run):
    return m.LogicalBackup(["docker", "compose", "--project-name", "test", "-f", "compose.yaml"], run=run)


def test_envelope_roundtrip_and_database_identity():
    m = module()
    packed = m.pack(SQL, m.migration_heads())
    assert m.unpack(packed, m.migration_heads()) == SQL
    assert b'"database":"daesingo"' in packed


@pytest.mark.parametrize("damage", ["truncate", "bitflip", "raw_sql", "wrong_db", "wrong_version", "trailing", "empty"])
def test_corrupt_or_wrong_dump_is_rejected(damage):
    m = module()
    packed = m.pack(SQL, m.migration_heads())
    bad = {"truncate": packed[:-5], "bitflip": packed[:-1] + b"?", "raw_sql": SQL,
        "wrong_db": packed.replace(b'"daesingo"', b'"other_db"'),
        "wrong_version": packed.replace(b'"format":1', b'"format":9'),
        "trailing": packed + b"extra", "empty": b""}[damage]
    with pytest.raises(m.BackupError): m.unpack(bad, m.migration_heads())


def test_migration_mismatch_rejected_before_any_docker_call(tmp_path):
    m = module()
    (tmp_path / m.ARTIFACT).write_bytes(m.pack(SQL, {"case": "old"}))
    with pytest.raises(m.BackupError): tool(m, lambda *a, **k: pytest.fail("must not invoke Docker")).restore(tmp_path)


def test_backup_then_restore_requires_exact_full_dump_match(tmp_path):
    m = module()
    run, calls = transport(m)
    t = tool(m, run)
    t.backup(tmp_path)
    assert m.unpack((tmp_path / m.ARTIFACT).read_bytes(), m.migration_heads()) == SQL
    t.restore(tmp_path)
    restore = [c for c in calls if c[1].get("input") == SQL]
    assert len(restore) == 1
    assert "--all-databases" not in str(calls)
    assert "--databases" not in str(calls)
    assert "--force" not in str(calls)
    assert "--database=daesingo" in str(calls)
    assert "private-canary" not in str(calls)
    assert "--single-transaction" in str(calls)


def test_existing_backup_collision_never_overwritten(tmp_path):
    m = module()
    path = tmp_path / m.ARTIFACT
    path.write_bytes(b"existing-private")
    with pytest.raises(m.BackupError): tool(m, lambda *a, **k: pytest.fail("collision must precede Docker")).backup(tmp_path)
    assert path.read_bytes() == b"existing-private"


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_active_writers_refused(tmp_path, operation):
    m = module()
    if operation == "restore": (tmp_path / m.ARTIFACT).write_bytes(m.pack(SQL, m.migration_heads()))
    run, calls = transport(m, active=True)
    with pytest.raises(m.BackupError): getattr(tool(m, run), operation)(tmp_path)
    assert len(calls) == 1
    assert not (tmp_path / m.ARTIFACT).exists() if operation == "backup" else True


@pytest.mark.parametrize("failure", ["command", "cancel", "nonzero", "migration"])
def test_backup_failure_removes_owned_artifact_and_can_rerun(tmp_path, failure):
    m = module()
    run, _ = transport(m, fail=failure == "command", heads={"case": "old"} if failure == "migration" else None)
    if failure in {"cancel", "nonzero"}:
        good = run
        def run(command, **kwargs):
            if "ps" in command: return good(command, **kwargs)
            if failure == "cancel": raise KeyboardInterrupt("private-canary")
            return SimpleNamespace(returncode=7, stdout=b"private-canary", stderr=b"private-canary")
    with pytest.raises((m.BackupError, KeyboardInterrupt)): tool(m, run).backup(tmp_path)
    assert not (tmp_path / m.ARTIFACT).exists()
    tool(m, transport(m)[0]).backup(tmp_path)


@pytest.mark.parametrize("failure", ["command", "partial", "migration", "empty"])
def test_failed_or_partial_restore_never_succeeds(tmp_path, failure):
    m = module()
    artifact = m.pack(SQL, m.migration_heads())
    (tmp_path / m.ARTIFACT).write_bytes(artifact)
    run, _ = transport(m, fail=failure == "command", data=SQL[:-1] if failure == "partial" else b"" if failure == "empty" else SQL,
        heads={"case": "old"} if failure == "migration" else None)
    with pytest.raises(m.BackupError): tool(m, run).restore(tmp_path)
    assert (tmp_path / m.ARTIFACT).read_bytes() == artifact


def test_remote_lock_and_clean_target_guard_precede_restore():
    m = module()
    script = m.remote_script("restore")
    assert script.index('mkdir "$lock"') < script.index('client <&0')
    assert script.index("information_schema.tables") < script.index('client <&0')
    assert "information_schema.routines" in script and "information_schema.events" in script
    assert "trap" in script and "rmdir" in script and "--defaults-extra-file=" in script
    assert "MYSQL_PWD" not in script and "--password=" not in script
    assert "set -x" not in script


def test_cli_does_not_echo_bad_arguments_or_exceptions(tmp_path, capsys):
    m = module()
    assert m.main(["restore", "--private-canary"]) != 0
    assert "private-canary" not in str(capsys.readouterr())
    assert m.main(["restore", "--project", "test", "--directory", str(tmp_path / "private-canary")]) != 0
    output = capsys.readouterr()
    assert "private-canary" not in str(output) and str(tmp_path) not in str(output)


def test_migration_inventory_uses_actual_single_heads():
    m = module()
    heads = m.migration_heads()
    assert set(heads) == {"case", "runtime", "recording"}
    assert heads["recording"] == "recording_0001"


@pytest.mark.parametrize("objects", ["routines", "events"])
def test_backup_rejects_schema_objects_omitted_by_default_dump(objects):
    m = module()
    script = m.remote_script("backup")
    assert "information_schema." + objects in script
    assert script.index('[ "$unsupported" = 0 ] || exit 25') < script.index("mysqldump")
