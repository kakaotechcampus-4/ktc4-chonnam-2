"""Caller-owned short transactions; singleton current-read lock is authoritative."""
from datetime import timedelta, timezone
import hmac
import re
from uuid import uuid4

import sqlalchemy as sa
from daesingo.common.jobs.schema import job_execution
from daesingo.common.usage.schema import usage_inflight

from . import schema as t
from .policy import PublicDenied


def now(conn):
    clock = (sa.func.current_timestamp(sa.literal_column("6"), type_=sa.DateTime)
             if conn.dialect.name == "mysql" else sa.func.current_timestamp(type_=sa.DateTime))
    return conn.execute(sa.select(clock)).scalar_one()


def day_start(value):
    # Public daily limits follow KST; MySQL session timestamps remain UTC.
    local = value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=9)))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)


def case_key(case_id):
    if not isinstance(case_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", case_id) is None:
        raise PublicDenied("NOT_FOUND")


class PublicStore:
    def __init__(self, policy, *, require_public, worker_id=None):
        self.policy, self.require_public = policy, require_public
        self.worker_id = worker_id

    def fingerprint(self, value):
        if self.policy is None or not isinstance(value, str):
            raise PublicDenied()
        return hmac.digest(self.policy.session_key.get_secret_value().encode(), value.encode(), "sha256")

    def locked(self, conn):
        row = conn.execute(sa.select(t.control).where(t.control.c.id == 1).with_for_update()).mappings().one_or_none()
        if row is None:
            raise PublicDenied()
        return row

    def accepting(self, conn):
        state = self.locked(conn)
        if self.policy is None:
            raise PublicDenied()
        if not state["accepting"] or state["policy_hash"] != self.policy.fingerprint():
            raise PublicDenied("STOPPED")

    def set_open(self, conn, opened):
        self.locked(conn)
        if opened and self.policy is None:
            raise PublicDenied()
        conn.execute(t.control.update().where(t.control.c.id == 1).values(
            accepting=opened, **({"policy_hash": self.policy.fingerprint()} if opened else {})))

    def create_session(self, conn, owner, ip):
        self.accepting(conn)
        existing = conn.execute(sa.select(t.sessions).where(t.sessions.c.session_hash == owner)
                                .with_for_update()).mappings().one_or_none()
        if existing is not None:
            if existing["expires_at"] <= now(conn) or existing["ip_hash"] != ip:
                raise PublicDenied("NOT_FOUND")
            return
        stamp = now(conn)
        count = conn.execute(sa.select(sa.func.count()).select_from(t.sessions).where(
            t.sessions.c.ip_hash == ip, t.sessions.c.created_at >= day_start(stamp))).scalar_one()
        if count >= self.policy.ip_daily:
            raise PublicDenied("LIMIT")
        conn.execute(t.sessions.insert().values(session_hash=owner, ip_hash=ip, created_at=stamp,
            expires_at=stamp + timedelta(seconds=self.policy.session_ttl_sec)))

    def session(self, conn, owner):
        row = conn.execute(sa.select(t.sessions).where(t.sessions.c.session_hash == owner)
                           .with_for_update()).mappings().one_or_none()
        if row is None or row["expires_at"] <= now(conn):
            raise PublicDenied("NOT_FOUND")
        return row

    def claim_case(self, conn, case_id, owner):
        self.accepting(conn)
        case_key(case_id)
        session = self.session(conn, owner)
        stamp = now(conn)
        count = conn.execute(sa.select(sa.func.count()).select_from(t.cases).where(
            t.cases.c.session_hash == owner, t.cases.c.created_at >= day_start(stamp))).scalar_one()
        if count >= self.policy.session_daily:
            raise PublicDenied("LIMIT")
        conn.execute(t.cases.insert().values(case_id=case_id, session_hash=owner, ip_hash=session["ip_hash"],
            state="ACTIVE", created_at=stamp, expires_at=stamp + timedelta(seconds=self.policy.case_ttl_sec),
            source_expires_at=stamp + timedelta(seconds=self.policy.source_ttl_sec), sources=[], temp_token=uuid4().hex))

    def require_owner(self, conn, case_id, owner, *, deleting=False):
        case_key(case_id)
        self.session(conn, owner)
        row = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == case_id)
                           .with_for_update()).mappings().one_or_none()
        # A lost completion response can be retried by its still-valid owner.
        # Reads and non-DELETE mutations must never expose a tombstone.
        states = ("ACTIVE", "DELETING", "DELETED") if deleting else ("ACTIVE",)
        if (row is None or row["session_hash"] != owner or row["state"] not in states
                or row["expires_at"] <= now(conn)):
            raise PublicDenied("NOT_FOUND")
        return row

    def bind_sample(self, conn, case_id, sample_id, sources):
        self.accepting(conn)
        if (not sources or any(type(s.get("duration_ms")) is not int or s["duration_ms"] <= 0 for s in sources)
                or sum(s["duration_ms"] for s in sources) > 600000
                or sum(s["byte_size"] for s in sources) > self.policy.max_input_bytes):
            raise PublicDenied("INPUT")
        row = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == case_id).with_for_update()).mappings().one()
        if row["state"] != "ACTIVE" or row["sources"] or row["source_expires_at"] <= now(conn):
            raise PublicDenied("INPUT")
        conn.execute(t.cases.update().where(t.cases.c.case_id == case_id).values(
            sample_id=sample_id, manifest_hash=bytes.fromhex(self.policy.manifest_sha256), sources=sources))

    def begin_preparation(self, conn, case_id, owner, sample_id, token):
        self.accepting(conn)
        row = self.require_owner(conn, case_id, owner)
        if row["sources"]:
            if row["sample_id"] != sample_id or row["manifest_hash"] != bytes.fromhex(self.policy.manifest_sha256):
                raise PublicDenied("INPUT")
            return False
        stamp = now(conn)
        def count(*conditions):
            return conn.execute(sa.select(sa.func.count()).select_from(t.preparations).where(*conditions)).scalar_one()
        if (row["source_expires_at"] <= stamp
                or count(t.preparations.c.case_id == case_id) >= self.policy.case_repeats + 1
                or count(t.preparations.c.ip_hash == row["ip_hash"],
                         t.preparations.c.created_at >= day_start(stamp)) >= self.policy.ip_daily
                or count(t.preparations.c.session_hash == owner,
                         t.preparations.c.created_at >= day_start(stamp)) >= self.policy.session_daily):
            raise PublicDenied("LIMIT")
        self.refresh_active(conn)
        active = conn.execute(sa.select(sa.func.count()).select_from(t.admissions)
            .where(t.admissions.c.active.is_(True))).scalar_one()
        active_owner = conn.execute(sa.select(sa.func.count()).select_from(t.admissions).where(
            t.admissions.c.active.is_(True), t.admissions.c.session_hash == owner)).scalar_one()
        if (count(t.preparations.c.case_id == case_id, t.preparations.c.finished_at.is_(None))
                or active + count(t.preparations.c.finished_at.is_(None)) >= self.policy.global_concurrent
                or active_owner + count(t.preparations.c.finished_at.is_(None),
                    t.preparations.c.session_hash == owner) >= self.policy.session_concurrent):
            raise PublicDenied("CONCURRENT")
        conn.execute(t.preparations.insert().values(token=token, case_id=case_id, session_hash=owner,
            ip_hash=row["ip_hash"], created_at=stamp))
        return True

    def finish_preparation(self, conn, token):
        self.locked(conn)
        conn.execute(t.preparations.update().where(t.preparations.c.token == token,
            t.preparations.c.finished_at.is_(None)).values(finished_at=now(conn)))

    def _bound_case(self, conn, case_id):
        case_key(case_id)
        row = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == case_id).with_for_update()).mappings().one_or_none()
        if row is None:
            if self.require_public:
                raise PublicDenied("NOT_FOUND")
            return None
        self.accepting(conn)
        if (row["state"] != "ACTIVE" or row["expires_at"] <= now(conn)
                or row["source_expires_at"] <= now(conn) or not row["sources"]
                or row["manifest_hash"] != bytes.fromhex(self.policy.manifest_sha256)):
            raise PublicDenied("INPUT")
        return row

    def refresh_active(self, conn):
        active = conn.execute(sa.select(t.admissions.c.case_id).where(t.admissions.c.active.is_(True))
                              .distinct()).scalars().all()
        for case_id in active:
            busy = conn.exec_driver_sql("SELECT COUNT(*) FROM job_execution WHERE case_id = %s AND "
                "(status IN ('QUEUED','RUNNING') OR (status IN ('SUCCEEDED','FAILED') AND case_applied_at IS NULL))"
                if conn.dialect.name == "mysql" else
                "SELECT COUNT(*) FROM job_execution WHERE case_id = ? AND "
                "(status IN ('QUEUED','RUNNING') OR (status IN ('SUCCEEDED','FAILED') AND case_applied_at IS NULL))",
                (case_id,)).scalar_one()
            unobserved = conn.execute(sa.select(sa.func.count()).select_from(usage_inflight).where(
                usage_inflight.c.case_id == case_id, usage_inflight.c.observed_at.is_(None))).scalar_one()
            # STALE/terminal recovery can precede the old leased HTTP returning.
            # Even FINALIZED recovery is not an actual observation. Keep its
            # slot until a real (possibly late) finish, without refunding cost.
            if not busy and not unobserved:
                conn.execute(t.admissions.update().where(t.admissions.c.case_id == case_id).values(active=False))

    def admit(self, conn, case_id, key, *, initial):
        self.accepting(conn)
        row = self._bound_case(conn, case_id)
        existing = conn.execute(sa.select(t.admissions).where(t.admissions.c.case_id == case_id,
            t.admissions.c.request_hash == key).with_for_update()).mappings().one_or_none()
        if existing is not None:
            return
        self.refresh_active(conn)
        stamp = now(conn)
        def count(*conditions):
            return conn.execute(sa.select(sa.func.count()).select_from(t.admissions).where(*conditions)).scalar_one()
        if (count(t.admissions.c.ip_hash == row["ip_hash"], t.admissions.c.created_at >= day_start(stamp)) >= self.policy.ip_daily
                or (initial and count(t.admissions.c.session_hash == row["session_hash"],
                    t.admissions.c.initial.is_(True), t.admissions.c.created_at >= day_start(stamp)) >= self.policy.session_daily)
                or (not initial and count(t.admissions.c.case_id == case_id,
                    t.admissions.c.initial.is_(False)) >= self.policy.case_repeats)):
            raise PublicDenied("LIMIT")
        preparing = conn.execute(sa.select(sa.func.count()).select_from(t.preparations).where(
            t.preparations.c.finished_at.is_(None))).scalar_one()
        preparing_owner = conn.execute(sa.select(sa.func.count()).select_from(t.preparations).where(
            t.preparations.c.finished_at.is_(None), t.preparations.c.session_hash == row["session_hash"])).scalar_one()
        if (count(t.admissions.c.active.is_(True)) + preparing >= self.policy.global_concurrent
                or count(t.admissions.c.active.is_(True), t.admissions.c.session_hash == row["session_hash"])
                + preparing_owner >= self.policy.session_concurrent):
            raise PublicDenied("CONCURRENT")
        conn.execute(t.admissions.insert().values(case_id=case_id, request_hash=key,
            session_hash=row["session_hash"], ip_hash=row["ip_hash"], initial=initial, active=True, created_at=stamp))

    def reserve(self, conn, snapshot):
        # Always detect tagged Cases, even if a new Worker was misconfigured internal.
        self.locked(conn)
        row = self._bound_case(conn, snapshot["case_id"])
        if row is None:
            return
        execution = conn.execute(sa.select(job_execution.c.case_id, job_execution.c.status,
            job_execution.c.lease_owner, job_execution.c.lease_expires_at, job_execution.c.cancel_requested_at)
            .where(job_execution.c.execution_id == snapshot["execution_ref"]).with_for_update()).mappings().one_or_none()
        if (execution is None or execution["case_id"] != snapshot["case_id"] or execution["status"] != "RUNNING"
                or self.worker_id is None or execution["lease_owner"] != self.worker_id
                or execution["lease_expires_at"] is None or execution["lease_expires_at"] <= now(conn)):
            raise PublicDenied("CLAIM_LOST")
        if execution["cancel_requested_at"] is not None:
            raise PublicDenied("CANCELLED")
        if not conn.execute(sa.select(sa.func.count()).select_from(t.admissions).where(
                t.admissions.c.case_id == snapshot["case_id"], t.admissions.c.active.is_(True))).scalar_one():
            raise PublicDenied("INPUT")
        amount = self.policy.bound(snapshot["operation"], snapshot["provider_label"])
        values = {k: snapshot[k] for k in ("usage_id", "execution_ref", "case_id", "operation", "provider_label")}
        existing = conn.execute(sa.select(t.reservations).where(t.reservations.c.usage_id == snapshot["usage_id"])
                                .with_for_update()).mappings().one_or_none()
        if existing is not None:
            if any(existing[k] != v for k, v in values.items()) or existing["amount_micros"] != amount:
                raise PublicDenied("CONFLICT")
            return
        stamp = now(conn)
        def spent(*conditions):
            return int(conn.execute(sa.select(sa.func.coalesce(sa.func.sum(t.reservations.c.amount_micros), 0))
                .where(*conditions)).scalar_one())
        if (spent() + amount > self.policy.total_budget_micros
                or spent(sa.or_(t.reservations.c.created_at >= day_start(stamp),
                                t.reservations.c.settled_at >= day_start(stamp),
                                t.reservations.c.settled_at.is_(None))) + amount > self.policy.daily_budget_micros
                or spent(t.reservations.c.case_id == snapshot["case_id"]) + amount > self.policy.case_budget_micros):
            raise PublicDenied("BUDGET")
        conn.execute(t.reservations.insert().values(**values, amount_micros=amount, created_at=stamp))
        # Keep the complete worst-case reservation, even on failure/unknown spend.
        # No finish/restart/day rollover refunds uncertain liabilities.

    def settle(self, conn, identity, cost):
        from decimal import Decimal, localcontext, ROUND_CEILING
        self.locked(conn)
        row = conn.execute(sa.select(t.reservations).where(t.reservations.c.usage_id == identity)
                           .with_for_update()).mappings().one_or_none()
        if row is None or cost.get("amount") is None:
            return
        try:
            with localcontext() as ctx:
                ctx.prec = 100
                amount = Decimal(str(cost["amount"]))
                if not amount.is_finite() or amount < 0 or cost.get("currency") != "KRW":
                    raise ValueError
                micros = int((amount * 1000000).to_integral_value(rounding=ROUND_CEILING))
            if micros > row["amount_micros"]:
                raise ValueError
        except Exception:
            # A violated approved ceiling is an operational incident. Commit
            # observations and close admission; never hide spend by rolling it back.
            conn.execute(t.control.update().where(t.control.c.id == 1).values(accepting=False))
            return
        conn.execute(t.reservations.update().where(t.reservations.c.usage_id == identity,
            t.reservations.c.settled_at.is_(None)).values(settled_at=now(conn)))

    def begin_delete(self, conn, case_id, owner=None):
        self.locked(conn)
        if owner is not None:
            self.require_owner(conn, case_id, owner, deleting=True)
        conn.execute(t.cases.update().where(t.cases.c.case_id == case_id,
            t.cases.c.state == "ACTIVE").values(state="DELETING"))
