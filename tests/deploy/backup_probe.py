"""TEST ONLY: durable state fingerprints and restored Worker dispatch probe.

Mounted read-only by acceptance; excluded from the application image.
Never print row values, filenames, locators or exception values.
"""
import hashlib
import json
import sys

from sqlalchemy import inspect


def durable_snapshot(conn):
    result = {}
    quote = conn.dialect.identifier_preparer.quote
    for name in sorted(inspect(conn).get_table_names()):
        rows = conn.exec_driver_sql("SELECT * FROM " + quote(name)).mappings().all()
        def encode(value):
            return {"binary": value.hex()} if isinstance(value, bytes) else str(value)
        serialized = sorted(json.dumps(dict(row), sort_keys=True, default=encode, separators=(",", ":")) for row in rows)
        result[name] = {"count": len(rows), "sha256": hashlib.sha256(json.dumps(serialized).encode()).hexdigest()}
    return result


def main():
    from daesingo.common.db import create_worker_engine
    from daesingo.worker.bootstrap import bootstrap
    startup = bootstrap(revision="restore-smoke")
    engine = create_worker_engine(startup.config.db)
    try:
        mode = sys.argv[1]
        with engine.begin() as conn:
            if mode == "snapshot":
                result = durable_snapshot(conn)
            elif mode == "enqueue":
                from daesingo.common.jobs.repository import enqueue
                enqueue(conn, [{"job_id": "rt13b-restored-job", "case_id": "rt13b-synthetic-case",
                    "kind": "RT13B_UNREGISTERED"}], "rt13b-smoke")
                result = {"queued": True}
            elif mode == "processed":
                rows = conn.exec_driver_sql("SELECT attempt,status FROM job_execution WHERE job_id=%s ORDER BY attempt",
                    ("rt13b-restored-job",)).mappings().all()
                result = [dict(row) for row in rows]
            else:
                raise ValueError()
        print(json.dumps(result, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print("backup probe: failed", file=sys.stderr)
        raise SystemExit(1)
