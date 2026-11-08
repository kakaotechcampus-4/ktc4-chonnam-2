"""One public child-job admission port for direct T2 and durable redelivery."""
import hashlib

from sqlalchemy import select

from daesingo.common.jobs.reflection import validated_result
from daesingo.common.jobs.exhaustion import ExhaustionResult
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.work import local_only
from daesingo.common.public_runtime.policy import PublicDenied


class _PublicJobAdmission:
    def __init__(self, inner, public):
        self.inner, self.public = inner, public

    def tagged(self, conn, case_id):
        self.public.locked(conn)
        return conn.execute(select(schema.cases.c.case_id).where(schema.cases.c.case_id == case_id)).first() is not None

    def admit(self, conn, case_id, identity, records):
        if any(job["case_id"] != case_id for job in records):
            raise ValueError("invalid reflection job case")
        if records:
            if local_only(records):
                key = hashlib.sha256(identity.encode()).digest()
                self.public.admit_local(conn, case_id, key, records)
            else:
                self.public.accepting(conn)


class PublicResultReflector(_PublicJobAdmission):
    def reflect(self, conn, incoming):
        tagged = self.tagged(conn, incoming.case_id)
        admitted = {}
        deferred = []
        def automatic(records):
            if not records or any(r['case_id'] != incoming.case_id or r['kind'] not in
                    {'REPORT_VIDEO_EXPORT', 'PLATE_IMAGE_EXPORT'} for r in records):
                raise ValueError('invalid automatic exports')
            try:
                with conn.begin_nested():
                    self.admit(conn, incoming.case_id, 'auto-export:' + incoming.execution_id, records)
            except PublicDenied as error:
                deferred.append(error.code)
                return False
            admitted.update({r['job_id']: {k: r[k] for k in ('job_id', 'case_id', 'kind')} for r in records})
            return True
        def remember(case_rev):
            conn.execute(schema.cases.update().where(schema.cases.c.case_id == incoming.case_id)
                .values(local_work_state={'case_rev': case_rev, 'reason': deferred[-1]}))
        capable = getattr(self.inner, 'reflect_with_admission', None)
        raw = (capable(conn, incoming, admit_auto_exports=automatic, on_auto_exports_deferred=remember)
               if tagged and callable(capable) else self.inner.reflect(conn, incoming))
        result = validated_result(raw)
        records = [{"job_id": job.job_id, "case_id": job.case_id, "kind": job.kind} for job in result.jobs]
        if tagged:
            if any(r['job_id'] in admitted and r != admitted[r['job_id']] for r in records):
                raise ValueError('automatic export identity changed')
            self.admit(conn, incoming.case_id, "followup:" + incoming.execution_id,
                       [r for r in records if r['job_id'] not in admitted])
        # Called inside reflect_terminal's transaction, BEFORE child enqueue.
        # Refusal leaves T1/usage intact and T2 unapplied on every delivery path.
        return result


class PublicExhaustionReceiver(_PublicJobAdmission):
    def receive(self, conn, notice):
        tagged = self.tagged(conn, notice.case_id)
        result = self.inner.receive(conn, notice)
        if type(result) is not ExhaustionResult:
            raise ValueError("invalid exhaustion result")
        result = ExhaustionResult(result.status, result.appended_job_records)
        if tagged:
            self.admit(conn, notice.case_id, "exhaustion:" + notice.notice_id, result.appended_job_records)
        return result
