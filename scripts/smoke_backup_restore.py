"""RT-13(b) opt-in actual Docker acceptance, including unchanged RT-13(a) smoke.

Linux host root required. Uses only a fresh, generated smoke project. Original
DB volume is discarded; the original media volume survives restore. No provider
calls. All artifacts/private files live inside the parent's TemporaryDirectory.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess

from backup_compose import ARTIFACT, BackupError, LogicalBackup, migration_heads, pack
from smoke_compose import ROOT, assert_no_secrets, record_failure, run_smoke, wait_for


def must_fail(operation):
    try:
        operation()
    except BackupError:
        return
    raise AssertionError("negative_control_accepted")


def reset_owned_database(project, volume, run, compose):
    # Never derive deletion from arbitrary inspect data. Both exact name AND
    # Compose ownership labels must match the generated project's mysql_data.
    from smoke_compose import cleanup_command
    cleanup_command(project, [])
    if volume != project + "_mysql_data": raise ValueError("unsafe_volume")
    info = json.loads(run(["docker", "volume", "inspect", volume]).stdout)[0]
    labels = info.get("Labels") or {}
    if labels.get("com.docker.compose.project") != project or labels.get("com.docker.compose.volume") != "mysql_data":
        raise ValueError("unsafe_volume")
    compose("down")  # Keep media; remove only this run's now-unused MySQL data.
    run(["docker", "volume", "rm", volume])
    compose("up", "-d", "mysql", timeout=240)


def backup_restore(context):
    compose, run = context["compose"], context["run"]
    root, project = context["root"], context["project"]
    record, report = context["record"], context["report"]
    stage = "restore_seed_snapshot"
    try:
        # Copy test-only probe into containers via a read-only bind overlay.
        overlay = root / "backup-probe.json"
        overlay.write_text(json.dumps({"services": {name: {"volumes": [{"type": "bind",
            "source": str(ROOT / "tests/deploy/backup_probe.py"), "target": "/opt/backup-probe.py",
            "read_only": True}]} for name in ("api", "worker")}}))
        base = [*context["base"], "-f", str(overlay)]
        def local_compose(*args, **kwargs): return run([*base, *args], **kwargs)
        local_compose("up", "-d", "--no-deps", "--force-recreate", "api", "worker", timeout=240)
        wait_for(lambda: context["inspect"]("api")["State"].get("Health", {}).get("Status") == "healthy", 120)
        # Recreate changes the ephemeral port; use a newly read port for view.
        import urllib.request
        port = local_compose("port", "api", "8000").stdout.strip().rsplit(":", 1)[1]
        def view():
            with urllib.request.urlopen("http://127.0.0.1:" + port + "/cases/" + context["case"] + "/view", timeout=15) as response:
                assert response.status == 200
                return json.load(response)
        def probe(mode):
            output = local_compose("exec", "-T", "api", "python", "/opt/backup-probe.py", mode).stdout
            return json.loads(output.strip().splitlines()[-1])
        before, case_view = probe("snapshot"), view()
        assert before["recording_entry"]["count"] > 0 and before["job_execution"]["count"] >= 2
        assert context["probe"]("worker", "files") == context["shared"]
        original_media = next(m["Name"] for m in context["inspect"]("api")["Mounts"] if m["Destination"] == "/media")
        volume = next(m["Name"] for m in context["inspect"]("mysql")["Mounts"] if m["Destination"] == "/var/lib/mysql")
        record(stage, durable_tables=len(before), recording_rows=before["recording_entry"]["count"],
            execution_rows=before["job_execution"]["count"], identity_values="fingerprinted_all_rows")
        local_compose("stop", "api", "worker")
        def binary_run(command, **kwargs):
            # Private SQL is captured as bytes, never printed or stored as RAW.
            result = subprocess.run(command, env=context["env"], cwd=ROOT, **kwargs)
            assert_no_secrets([result.stdout.decode(errors="replace"), result.stderr.decode(errors="replace")], context["secrets"])
            return result
        tool = LogicalBackup(base, run=binary_run)
        artifact_dir = root / "artifact"
        artifact_dir.mkdir(mode=0o700)
        stage = "logical_backup"
        tool.backup(artifact_dir)
        original = (artifact_dir / ARTIFACT).read_bytes()
        assert (artifact_dir / ARTIFACT).stat().st_mode & 0o777 == 0o600
        record(stage, database="daesingo", integrity="length_sha256", migration_heads=migration_heads())
        stage = "restore_nonempty_target_rejected"
        must_fail(lambda: tool.restore(artifact_dir))
        record(stage)
        stage = "backup_collision_and_duplicate_rejected"
        must_fail(lambda: tool.backup(artifact_dir))
        lock = "/tmp/daesingo-rt13-logical.lock"
        local_compose("exec", "-T", "mysql", "mkdir", lock)
        second = root / "second"
        second.mkdir(mode=0o700)
        try:
            must_fail(lambda: tool.backup(second))
            assert not (second / ARTIFACT).exists()
        finally:
            local_compose("exec", "-T", "mysql", "rmdir", lock)
        record(stage)
        stage = "clean_database_target"
        reset_owned_database(project, volume, run, local_compose)
        wait_for(lambda: context["inspect"]("mysql")["State"].get("Health", {}).get("Status") == "healthy", 180)
        record(stage, mysql_data="new_empty_volume", media="original_volume_preserved")
        stage = "corrupt_wrong_dump_rejected"
        path = artifact_dir / ARTIFACT
        for damaged in (original[:-7], b"unrelated SQL", original.replace(b'"daesingo"', b'"wrong_db"')):
            path.write_bytes(damaged)
            must_fail(lambda: tool.restore(artifact_dir))
        path.write_bytes(original)
        record(stage, negative_controls=3)
        stage = "partial_restore_failure"
        path.write_bytes(pack(b"CREATE TABLE rt13b_partial (id int);\nINVALID_SQL;\n", migration_heads()))
        must_fail(lambda: tool.restore(artifact_dir))
        # A second attempt must reject the table left by MySQL implicit DDL.
        path.write_bytes(original)
        must_fail(lambda: tool.restore(artifact_dir))
        record(stage, retry_partial_target="rejected")
        stage = "restore_to_clean_database"
        reset_owned_database(project, volume, run, local_compose)
        wait_for(lambda: context["inspect"]("mysql")["State"].get("Health", {}).get("Status") == "healthy", 180)
        tool.restore(artifact_dir)
        record(stage, full_schema_data_dump="byte_identical", heads="verified_before_startup_migration")
        stage = "restored_api_worker_media"
        local_compose("up", "-d", "api", "worker", timeout=240)
        wait_for(lambda: context["inspect"]("api")["State"].get("Health", {}).get("Status") == "healthy", 120)
        port = local_compose("port", "api", "8000").stdout.strip().rsplit(":", 1)[1]
        assert probe("snapshot") == before and view() == case_view
        assert context["probe"]("api", "files") == context["probe"]("worker", "files") == context["shared"]
        for name in ("api", "worker"):
            container = context["inspect"](name)
            assert container["State"]["Running"]
            assert next(m["Name"] for m in container["Mounts"] if m["Destination"] == "/media") == original_media
        probe("enqueue")
        wait_for(lambda: probe("processed") == [{"attempt": 1, "status": "FAILED"}], 45)
        for name in ("api", "worker", "mysql", "migrate"):
            assert_no_secrets(context["inspect"](name), context["secrets"])
            local_compose("logs", "--no-color", name)
        record(stage, api="healthy", worker="processed_new_job_in_restored_db", media="same_volume_refs_bytes",
            durable_snapshot="all_tables_rows_equal", case_view="equal", provider_calls=0)
        stage = "backup_rerun_after_restore"
        local_compose("stop", "api", "worker")
        tool.backup(second)
        assert (second / ARTIFACT).exists()
        record(stage)
    except BaseException as error:
        record_failure(report, stage, error)
        raise


def main(argv=None):
    from backup_compose import SafeParser
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--evidence", type=Path, required=True)
        args = parser.parse_args(argv)
        return run_smoke(args.evidence, after_persistence=backup_restore)
    except BaseException:
        print("restore smoke: failed")
        return 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
