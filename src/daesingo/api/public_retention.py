"""Retryable owned public Case cleanup; never deletes source evidence/backups.

Filesystem work stays outside DB callbacks. Tombstone + saved metadata plan,
existing exclusive leases, and verified apply make interrupted cleanup resumable.
"""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import re
import stat

import sqlalchemy as sa

from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicDenied
from daesingo.common.public_runtime.repository import now, day_start
from daesingo.common.public_runtime.temporary import delete_case_temp
from daesingo.common.storage.cleanup import _lease, ScanResult
from daesingo.common.storage._filesystem import pin_root, tool_directory, ordinary, version
from daesingo.common.jobs.schema import job_execution, job_exhaustion_notice
from daesingo.common.jobs.produced import produced_objects
from daesingo.common.usage.schema import usage_inflight
from daesingo.case.store_mysql import cases_table, job_records_table, correction_records_table, analysis_scopes_table
from daesingo.recording.purge import build_plan, apply_plan, PurgeBlocked


def delete_source_files(media_root, files):
    removed = 0
    with pin_root(media_root) as root:
        for item in files:
            if re.fullmatch(r"source/[0-9a-f]{32}", item["locator"]) is None:
                raise PurgeBlocked("UNSAFE_FILE")
            name = item["locator"].split("/")[1]
            with root.child("source", directory=True) as directory:
                try:
                    before = directory.lstat(name)
                except FileNotFoundError:
                    continue
                if (not ordinary(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                        or before.st_size != item["byte_size"]):
                    raise PurgeBlocked("CHANGED")
                path = tool_directory(directory) / name
                digest = hashlib.sha256()
                with directory.child(name) as pinned, path.open("rb") as reader:
                    while chunk := reader.read(1024 * 1024):
                        digest.update(chunk)
                    if version(pinned.stat()) != version(before) or digest.hexdigest() != item["sha256"]:
                        raise PurgeBlocked("CHANGED")
                with directory.child(name, delete=True) as pinned:
                    if version(pinned.stat()) != version(before):
                        raise PurgeBlocked("CHANGED")
                    directory.remove(name, pinned)
                removed += 1
    return removed


def apply_case_plan(conn, plan):
    """Runtime-owned adapter; Case Owner may supply an equivalent same-conn port."""
    apply_plan(conn, plan)
    case_id = plan["case_id"]
    conn.execute(produced_objects.delete().where(produced_objects.c.case_id == case_id))
    conn.execute(job_exhaustion_notice.delete().where(job_exhaustion_notice.c.case_id == case_id))
    conn.execute(job_execution.delete().where(job_execution.c.case_id == case_id))
    for table in (analysis_scopes_table, correction_records_table, job_records_table, cases_table):
        conn.execute(table.delete().where(table.c.case_id == case_id))
    # Final usage, reservation and daily security receipts are intentionally retained.


class PublicRetention:
    kind = "public_case"

    def __init__(self, *, engine, store, media_root, temp_root, plan=build_plan, apply=apply_case_plan):
        self.engine, self.store = engine, store
        self.media_root, self.temp_root = Path(media_root), Path(temp_root)
        self.plan, self.apply = plan, apply

    def transaction(self, callback):
        return run_api_transaction(self.engine, callback)

    def _busy(self, conn, case_id):
        jobs = conn.execute(sa.select(sa.func.count()).select_from(job_execution).where(
            job_execution.c.case_id == case_id, sa.or_(job_execution.c.status.in_(("QUEUED", "RUNNING")),
                sa.and_(job_execution.c.status.in_(("SUCCEEDED", "FAILED")), job_execution.c.case_applied_at.is_(None)))))
        if jobs.scalar_one():
            raise PublicDenied("BUSY")
        if conn.execute(sa.select(sa.func.count()).select_from(usage_inflight).where(
                usage_inflight.c.case_id == case_id, sa.or_(usage_inflight.c.state != "FINALIZED",
                    usage_inflight.c.observed_at.is_(None)))).scalar_one():
            raise PublicDenied("BUSY")

    def _phase(self, conn, case_id):
        self.store.locked(conn)
        row = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == case_id).with_for_update()).mappings().one_or_none()
        if row is None:
            raise PublicDenied("NOT_FOUND")
        if row["state"] == "DELETED":
            return row
        if row["state"] != "DELETING":
            raise PublicDenied("BUSY")
        self._busy(conn, case_id)
        if row["deletion_plan"] is None:
            plan = self.plan(conn, case_id)
            conn.execute(t.cases.update().where(t.cases.c.case_id == case_id).values(deletion_plan=plan))
            row = dict(row, deletion_plan=plan)
        return row

    def purge(self, case_id):
        try:
            with ExitStack() as stack:
                # Public HTTP/copy/tool/T1 work shares these exact existing leases.
                media = stack.enter_context(_lease(self.media_root, "orphan", exclusive=True,
                                                  blocking=False, with_root=True))
                if media is None:
                    raise PublicDenied("BUSY")
                temp = stack.enter_context(_lease(self.temp_root, "temp", exclusive=True,
                                                 blocking=False, with_root=True))
                if temp is None:
                    raise PublicDenied("BUSY")
                def reconcile_preparations(conn):
                    self.store.locked(conn)
                    # Exclusive orphan lease proves no preparation is still
                    # hashing/copying. Do not expire permits solely by a clock.
                    conn.execute(t.preparations.update().where(t.preparations.c.finished_at.is_(None))
                                 .values(finished_at=now(conn)))
                self.transaction(reconcile_preparations)
                row = self.transaction(lambda conn: self._phase(conn, case_id))
                if row["state"] == "DELETED":
                    return {"state": "DELETED", "files": 0}
                plan = row["deletion_plan"]
                removed = delete_source_files(self.media_root, plan["files"])
                delete_case_temp(self.temp_root, row["temp_token"])
                def finish(conn):
                    current = self._phase(conn, case_id)
                    if current["deletion_plan"] != plan:
                        raise PurgeBlocked("CHANGED")
                    self.apply(conn, plan)
                    conn.execute(t.cases.update().where(t.cases.c.case_id == case_id).values(
                        state="DELETED", sources=[], deletion_plan=None, sample_id=None,
                        manifest_hash=None, sources_deleted_at=now(conn)))
                    conn.execute(t.admissions.update().where(t.admissions.c.case_id == case_id).values(active=False))
                self.transaction(finish)
                return {"state": "DELETED", "files": removed, "shared_entries_preserved": plan["shared_entries"]}
        except (PublicDenied, PurgeBlocked) as error:
            return {"state": "DELETING", "reason": error.code}
        except Exception:
            return {"state": "DELETING", "reason": "RETRY_REQUIRED"}

    def scan(self):
        result = ScanResult()
        try:
            def expired(conn):
                self.store.locked(conn)
                stamp = now(conn)
                rows = conn.execute(sa.select(t.cases.c.case_id).where(sa.or_(t.cases.c.state == "DELETING",
                    sa.and_(t.cases.c.state == "ACTIVE", sa.or_(t.cases.c.expires_at <= stamp,
                        t.cases.c.source_expires_at <= stamp)))).order_by(t.cases.c.case_id).limit(100)).scalars().all()
                for case_id in rows:
                    self.store.begin_delete(conn, case_id)
                return rows
            for case_id in self.transaction(expired):
                if self.purge(case_id)["state"] == "DELETED":
                    result.count += 1
                else:
                    result.failed += 1
            def expire_security_receipts(conn):
                self.store.locked(conn)
                stamp = now(conn)
                cutoff = day_start(stamp)
                # Keep same-day receipts after DELETE, so deleting a Case never
                # resets its IP/session quota. Cost/reservation ledgers survive.
                deleted = sa.select(t.cases.c.case_id).where(t.cases.c.state == "DELETED")
                for table in (t.admissions, t.preparations):
                    conn.execute(table.delete().where(table.c.case_id.in_(deleted), table.c.created_at < cutoff))
                conn.execute(t.cases.update().where(t.cases.c.state == "DELETED", t.cases.c.created_at < cutoff)
                             .values(session_hash=None, ip_hash=None))
                conn.execute(t.sessions.delete().where(t.sessions.c.expires_at <= stamp,
                                                       t.sessions.c.created_at < cutoff))
            self.transaction(expire_security_receipts)
        except Exception:
            result.failed += 1
        return result
