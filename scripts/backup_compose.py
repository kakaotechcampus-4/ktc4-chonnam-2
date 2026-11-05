"""Local RT-13(b) logical backup/restore, NOT a production backup policy.

Stop api/worker/migrate before use. Only the Compose database `daesingo` is
supported. A failed/interrupted restore can leave DDL: inspect/discard that
owned target; never retry against a partial target. Media bytes are NOT backed
up. Input artifacts must be trusted: SHA256 is integrity, not authentication.
"""

import argparse
import ast
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = "logical.rt13"
MAGIC = b"RT13-LOGICAL\n"
SEPARATOR = b"__RT13_SQL__\n"
CHUNK_BYTES = 1024 * 1024
HEADER_BYTES = 65536


class BackupError(RuntimeError):
    """Only fixed codes may cross the CLI boundary."""


def migration_heads(source_root=None):
    """Read release migration metadata without importing executable revisions."""
    result = {}
    for name in ("case", "runtime", "recording"):
        revisions, parents = set(), set()
        for path in (Path(source_root or ROOT) / "migrations" / name / "versions").glob(
            "*.py"
        ):
            for node in ast.parse(path.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "revision",
                            "down_revision",
                        }:
                            value = ast.literal_eval(node.value)
                            if target.id == "revision":
                                if value in revisions:
                                    raise BackupError("migration_inventory")
                                revisions.add(value)
                            elif value is not None:
                                parents.update(
                                    value if isinstance(value, tuple) else (value,)
                                )
        heads = revisions - parents
        if len(heads) != 1 or not parents <= revisions:
            raise BackupError("migration_inventory")
        result[name] = heads.pop()
    return result


def pack_file(source, destination, heads):
    """Encode from the current SQL offset, never buffering the whole dump."""
    start, size, digest = source.tell(), 0, hashlib.sha256()
    while chunk := source.read(CHUNK_BYTES):
        size += len(chunk)
        digest.update(chunk)
    if not size:
        raise BackupError("empty_dump")
    header = {
        "format": 1,
        "database": "daesingo",
        "heads": heads,
        "size": size,
        "sha256": digest.hexdigest(),
    }
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(encoded) > HEADER_BYTES:
        raise BackupError("invalid_artifact")
    destination.write(MAGIC)
    destination.write(encoded)
    source.seek(start)
    copied, check = 0, hashlib.sha256()
    while chunk := source.read(CHUNK_BYTES):
        destination.write(chunk)
        copied += len(chunk)
        check.update(chunk)
    if copied != size or check.digest() != digest.digest():
        raise BackupError("dump_changed")


def unpack_file(source, destination, expected):
    """Validate the complete envelope into a private SQL spool before import."""
    try:
        if source.read(len(MAGIC)) != MAGIC:
            raise ValueError()
        header = source.readline(HEADER_BYTES)
        if not header.endswith(b"\n") or len(header) >= HEADER_BYTES:
            raise ValueError()
        info = json.loads(header)
        if (
            set(info) != {"format", "database", "heads", "size", "sha256"}
            or type(info["format"]) is not int
            or info["format"] != 1
            or info["database"] != "daesingo"
            or info["heads"] != expected
            or type(info["size"]) is not int
            or info["size"] <= 0
            or not isinstance(info["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
        ):
            raise ValueError()
        remaining, digest = info["size"], hashlib.sha256()
        while remaining:
            chunk = source.read(min(CHUNK_BYTES, remaining))
            if not chunk:
                raise ValueError()
            digest.update(chunk)
            destination.write(chunk)
            remaining -= len(chunk)
        if source.read(1) or digest.hexdigest() != info["sha256"]:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise BackupError("invalid_artifact") from None


def pack(sql, heads):
    """Bounded compatibility API for existing small synthetic smoke fixtures."""
    if len(sql) > CHUNK_BYTES:
        raise BackupError("use_file_api")
    result = io.BytesIO()
    pack_file(io.BytesIO(sql), result, heads)
    return result.getvalue()


def unpack(data, expected):
    if len(data) > CHUNK_BYTES + HEADER_BYTES + len(MAGIC):
        raise BackupError("use_file_api")
    result = io.BytesIO()
    unpack_file(io.BytesIO(data), result, expected)
    if result.tell() > CHUNK_BYTES:
        raise BackupError("use_file_api")
    return result.getvalue()


def remove_owned(path, identity):
    """Never remove a caller replacement at an old temporary/artifact name."""
    try:
        current = path.lstat()
        if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
            path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def readonly_sql(directory, artifact, heads):
    fd, name = tempfile.mkstemp(prefix=".rt13-sql-", dir=directory)
    path, identity = Path(name), os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as sql:
            unpack_file(artifact, sql, heads)
        with path.open("rb") as sql:
            current = os.fstat(sql.fileno())
            if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                raise BackupError("artifact_unavailable")
            yield sql
    finally:
        remove_owned(path, identity)


def same_bytes(left, right):
    while True:
        a, b = left.read(CHUNK_BYTES), right.read(CHUNK_BYTES)
        if a != b:
            return False
        if not a:
            return True


def remote_script(operation):
    if operation not in {"backup", "restore"}:
        raise BackupError("invalid_operation")
    # All values here are constants. The secret remains an unexported shell
    # variable and a 0600 client file inside the mysql container, never argv/env.
    # Atomic mkdir covers all callers/directories on this database container.
    # trap runs inside Docker even if the host CLI disconnects. Each database
    # client has a bounded deadline; stale locks are NEVER stolen automatically.
    setup = r"""set -eu
umask 077
lock=/tmp/daesingo-rt13-logical.lock
mkdir "$lock" 2>/dev/null || exit 20
config="$lock/client.cnf"
trap 'rm -f "$config"; rmdir "$lock"' EXIT
trap 'exit 21' HUP INT TERM
password=$(cat /run/secrets/mysql-password)
[ -n "$password" ] || exit 22
case "$password" in *'
'*|*'
'*) exit 22;; esac
escaped=$(printf '%s' "$password" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '[client]\nuser=daesingo\npassword="%s"\n' "$escaped" > "$config"
unset password escaped
client() { timeout 180 mysql --defaults-extra-file="$config" --batch --skip-column-names --raw --binary-mode --local-infile=0 --skip-reconnect --database=daesingo "$@" 2>/dev/null; }
version=$(client -e 'SELECT VERSION()')
case "$version" in 8.4.*) ;; *) exit 23;; esac
"""
    source_guard = (
        r"""
unsupported=$(client -e "SELECT (SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.events WHERE event_schema='daesingo')")
[ "$unsupported" = 0 ] || exit 25
"""
        if operation == "backup"
        else ""
    )
    clean = (
        r"""
client_help=$(client --verbose --help)
client_packet=$(printf '%s\n' "$client_help" | awk '$1 == "max-allowed-packet" {print $2}')
unset client_help
[ "$client_packet" = 67108864 ] || exit 26
server_packet=$(client -e 'SELECT @@GLOBAL.max_allowed_packet,@@SESSION.max_allowed_packet')
expected_packet=$(printf '67108864\t67108864')
[ "$server_packet" = "$expected_packet" ] || exit 26
objects=$(client -e "SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='daesingo') + (SELECT COUNT(*) FROM information_schema.events WHERE event_schema='daesingo')")
[ "$objects" = 0 ] || exit 24
client <&0
"""
        if operation == "restore"
        else ""
    )
    finish = r"""
client -e "SELECT 'case',version_num FROM case_alembic_version UNION ALL SELECT 'recording',version_num FROM recording_alembic_version UNION ALL SELECT 'runtime',version_num FROM runtime_alembic_version ORDER BY 1"
printf '__RT13_SQL__\n'
timeout 180 mysqldump --defaults-extra-file="$config" --single-transaction --quick --skip-lock-tables --skip-add-locks --skip-comments --skip-dump-date --skip-add-drop-table --order-by-primary --hex-blob --skip-extended-insert --no-tablespaces --set-gtid-purged=OFF daesingo 2>/dev/null
"""
    if operation == "restore":
        setup = setup.replace(
            '"$config" --batch', '"$config" --max-allowed-packet=67108864 --batch'
        )
    return setup + source_guard + clean + finish


class LogicalBackup:
    def __init__(self, base, *, run=None, source_root=None):
        self.base = list(base)
        self.run = run or subprocess.run
        self.source_root = source_root

    def _call(self, args, **kwargs):
        try:
            if "stdout" not in kwargs:
                kwargs["capture_output"] = True
            result = self.run([*self.base, *args], timeout=600, **kwargs)
            if result.returncode:
                raise BackupError("command_failed")
            return getattr(result, "stdout", None)
        except (OSError, subprocess.SubprocessError):
            raise BackupError("command_failed") from None

    def _quiescent(self):
        try:
            output = self._call(["ps", "--all", "--format", "json"]).decode()
            try:
                rows = json.loads(output or "[]")
            except ValueError:
                rows = [json.loads(line) for line in output.splitlines()]
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list):
                raise ValueError()
            if any(
                row["Service"] in {"api", "worker", "migrate"}
                and row["State"] not in {"exited", "created"}
                for row in rows
            ):
                raise BackupError("writers_active")
        except (ValueError, KeyError, TypeError):
            raise BackupError("invalid_service_state") from None

    @contextmanager
    def _execute(self, operation, heads, directory, sql=None):
        with tempfile.TemporaryFile(dir=directory, prefix=".rt13-output-") as output:
            self._call(
                ["exec", "-T", "mysql", "sh", "-c", remote_script(operation)],
                stdin=sql if sql is not None else subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
            )
            output.seek(0)
            try:
                rows, length = [], 0
                for _ in range(len(heads)):
                    line = output.readline(HEADER_BYTES)
                    length += len(line)
                    if length >= HEADER_BYTES or not line.endswith(b"\n"):
                        raise ValueError()
                    rows.append(line.decode().rstrip("\n").split("\t"))
                if (
                    dict(rows) != heads
                    or output.readline(len(SEPARATOR) + 1) != SEPARATOR
                ):
                    raise ValueError()
                start = output.tell()
                if not output.read(1):
                    raise ValueError()
                output.seek(start)
            except (ValueError, UnicodeError):
                raise BackupError("migration_or_dump_mismatch") from None
            yield output

    def backup(self, directory):
        path = Path(directory) / ARTIFACT
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            raise BackupError("artifact_unavailable") from None
        identity = os.fstat(fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                heads = migration_heads(self.source_root)
                self._quiescent()
                with self._execute("backup", heads, directory) as dump:
                    pack_file(dump, stream, heads)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            remove_owned(path, identity)
            raise

    def restore(self, directory):
        heads = migration_heads(self.source_root)
        try:
            with (Path(directory) / ARTIFACT).open("rb") as artifact:
                if not stat.S_ISREG(os.fstat(artifact.fileno()).st_mode):
                    raise BackupError("artifact_unavailable")
                with readonly_sql(directory, artifact, heads) as sql:
                    # All envelope bytes/heads have been checked before any Docker call.
                    self._quiescent()
                    with self._execute("restore", heads, directory, sql) as restored:
                        sql.seek(0)
                        if not same_bytes(sql, restored):
                            raise BackupError("restored_state_mismatch")
        except OSError:
            raise BackupError("artifact_unavailable") from None


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
        parser.add_argument(
            "--source-root",
            required=True,
            type=Path,
            help="Verified source migrations of the backup/restore release, not the host tool checkout",
        )
        args = parser.parse_args(argv)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", args.project):
            raise BackupError("invalid_project")
        base = [
            "docker",
            "compose",
            "--project-name",
            args.project,
            *[
                arg
                for path in (args.compose_file or [ROOT / "compose.yaml"])
                for arg in ("-f", str(path))
            ],
        ]
        getattr(LogicalBackup(base, source_root=args.source_root), args.operation)(
            args.directory
        )
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
    signal.signal(
        signal.SIGTERM, lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    raise SystemExit(main())
