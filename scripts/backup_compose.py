"""Local RT-13(b) logical backup/restore, NOT a production backup policy.

Stop api/worker/migrate before use. Only the Compose database `daesingo` is
supported. A failed/interrupted restore can leave DDL: inspect/discard that
owned target; never retry against a partial target. Media bytes are NOT backed
up. Input artifacts must be trusted: SHA256 is integrity, not authentication.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = "logical.rt13"
MAGIC = b"RT13-LOGICAL\n"
SEPARATOR = b"__RT13_SQL__\n"


class BackupError(RuntimeError):
    """Only fixed codes may cross the CLI boundary."""


def migration_heads():
    """Read release migration metadata without importing executable revisions."""
    result = {}
    for name in ("case", "runtime", "recording"):
        revisions, parents = set(), set()
        for path in (ROOT / "migrations" / name / "versions").glob("*.py"):
            for node in ast.parse(path.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                            value = ast.literal_eval(node.value)
                            if target.id == "revision":
                                if value in revisions: raise BackupError("migration_inventory")
                                revisions.add(value)
                            elif value is not None:
                                parents.update(value if isinstance(value, tuple) else (value,))
        heads = revisions - parents
        if len(heads) != 1 or not parents <= revisions: raise BackupError("migration_inventory")
        result[name] = heads.pop()
    return result


def pack(sql, heads):
    if not sql: raise BackupError("empty_dump")
    header = {"format": 1, "database": "daesingo", "heads": heads,
        "size": len(sql), "sha256": hashlib.sha256(sql).hexdigest()}
    return MAGIC + json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n" + sql


def unpack(data, expected):
    try:
        if not data.startswith(MAGIC): raise ValueError()
        header, sql = data[len(MAGIC):].split(b"\n", 1)
        if len(header) > 65536: raise ValueError()
        info = json.loads(header)
        if (set(info) != {"format", "database", "heads", "size", "sha256"}
                or info["format"] != 1 or info["database"] != "daesingo" or info["heads"] != expected
                or not sql or info["size"] != len(sql) or info["sha256"] != hashlib.sha256(sql).hexdigest()):
            raise ValueError()
        return sql
    except (ValueError, KeyError, TypeError):
        raise BackupError("invalid_artifact") from None


def remote_script(operation):
    if operation not in {"backup", "restore"}: raise BackupError("invalid_operation")
    # All values here are constants. The secret remains an unexported shell
    # variable and a 0600 client file inside the mysql container, never argv/env.
    # Atomic mkdir covers all callers/directories on this database container.
    # trap runs inside Docker even if the host CLI disconnects. Each database
    # client has a bounded deadline; stale locks are NEVER stolen automatically.
    setup = r'''set -eu
umask 077
lock=/tmp/daesingo-rt13-logical.lock
mkdir "$lock" 2>/dev/null || exit 20
config="$lock/client.cnf"
trap 'rm -f "$config"; rmdir "$lock"' EXIT
trap 'exit 21' HUP INT TERM
password=$(cat /run/secrets/mysql-password)
[ -n "$password" ] || exit 22
case "$password" in *'
'*|*''*) exit 22;; esac
escaped=$(printf '%s' "$password" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '[client]\nuser=daesingo\npassword="%s"\n' "$escaped" > "$config"
unset password escaped
client() { timeout 180 mysql --defaults-extra-file="$config" --batch --skip-column-names --raw --binary-mode --local-infile=0 --skip-reconnect --database=daesingo "$@" 2>/dev/null; }
version=$(client -e 'SELECT VERSION()')
case "$version" in 8.4.*) ;; *) exit 23;; esac
'''
    source_guard = r'''
unsupported=$(client -e "SELECT (SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.events WHERE event_schema='daesingo')")
[ "$unsupported" = 0 ] || exit 25
''' if operation == "backup" else ""
    clean = r'''
objects=$(client -e "SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.events WHERE event_schema='daesingo')")
[ "$objects" = 0 ] || exit 24
client <&0
''' if operation == "restore" else ""
    finish = r'''
client -e "SELECT 'case',version_num FROM case_alembic_version UNION ALL SELECT 'recording',version_num FROM recording_alembic_version UNION ALL SELECT 'runtime',version_num FROM runtime_alembic_version ORDER BY 1"
printf '__RT13_SQL__\n'
timeout 180 mysqldump --defaults-extra-file="$config" --single-transaction --quick --skip-lock-tables --skip-add-locks --skip-comments --skip-dump-date --skip-add-drop-table --order-by-primary --hex-blob --no-tablespaces --set-gtid-purged=OFF daesingo 2>/dev/null
'''
    return setup + source_guard + clean + finish


class LogicalBackup:
    def __init__(self, base, *, run=None):
        self.base = list(base)
        self.run = run or subprocess.run

    def _call(self, args, **kwargs):
        try:
            result = self.run([*self.base, *args], capture_output=True, timeout=600, **kwargs)
            if result.returncode: raise BackupError("command_failed")
            return result.stdout
        except (OSError, subprocess.SubprocessError):
            raise BackupError("command_failed") from None

    def _quiescent(self):
        try:
            output = self._call(["ps", "--all", "--format", "json"]).decode()
            try: rows = json.loads(output or "[]")
            except ValueError: rows = [json.loads(line) for line in output.splitlines()]
            if isinstance(rows, dict): rows = [rows]
            if not isinstance(rows, list): raise ValueError()
            if any(row["Service"] in {"api", "worker", "migrate"}
                   and row["State"] not in {"exited", "created"} for row in rows):
                raise BackupError("writers_active")
        except (ValueError, KeyError, TypeError):
            raise BackupError("invalid_service_state") from None

    def _execute(self, operation, heads, sql=None):
        output = self._call(["exec", "-T", "mysql", "sh", "-c", remote_script(operation)], input=sql)
        try:
            prefix, dump = output.split(SEPARATOR, 1)
            rows = [line.split("\t") for line in prefix.decode().splitlines()]
            if len(rows) != len(heads) or dict(rows) != heads or not dump:
                raise ValueError()
            return dump
        except (ValueError, UnicodeError):
            raise BackupError("migration_or_dump_mismatch") from None

    def backup(self, directory):
        path = Path(directory) / ARTIFACT
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            raise BackupError("artifact_unavailable") from None
        try:
            with os.fdopen(fd, "wb") as stream:
                heads = migration_heads()
                self._quiescent()
                dump = self._execute("backup", heads)
                stream.write(pack(dump, heads))
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink()
            raise

    def restore(self, directory):
        heads = migration_heads()
        try: data = (Path(directory) / ARTIFACT).read_bytes()
        except OSError: raise BackupError("artifact_unavailable") from None
        sql = unpack(data, heads)  # Validate completely BEFORE touching target.
        self._quiescent()
        restored = self._execute("restore", heads, sql)
        if restored != sql: raise BackupError("restored_state_mismatch")


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise BackupError("invalid_arguments")


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("operation", choices=("backup", "restore"))
        parser.add_argument("--project", required=True)
        parser.add_argument("--directory", required=True, type=Path)
        parser.add_argument("--compose-file", action="append", type=Path)
        args = parser.parse_args(argv)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", args.project):
            raise BackupError("invalid_project")
        base = ["docker", "compose", "--project-name", args.project,
            *[arg for path in (args.compose_file or [ROOT / "compose.yaml"]) for arg in ("-f", str(path))]]
        getattr(LogicalBackup(base), args.operation)(args.directory)
        print("logical backup: " + args.operation + " PASS")
        return 0
    except KeyboardInterrupt:
        print("logical backup: interrupted", file=sys.stderr)
        return 130
    except Exception:
        # No raw argv, paths, SQL, database rows, env values or exception text.
        print("logical backup: operation_failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
