"""Detached fixed Readout inputs through Case and Runtime public read ports."""
from daesingo.worker.produced_reader import worker_produced_reader
from daesingo.worker.readout_handlers import ReadoutInput


class ReadoutInputs:
    def __init__(self, *, transaction, store_factory, reader=None):
        self.transaction, self.store_factory = transaction, store_factory
        self.reader = reader if reader is not None else worker_produced_reader()

    def __call__(self, context):
        return self.transaction(lambda conn: self._read(conn, context))

    def _read(self, conn, context):
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError("Readout input store must share caller connection")
        case = store.get_case(context.case_id)
        if case.case_id != context.case_id or context.kind not in {"PLATE_READ", "OVERLAY_TIME_READ"}:
            raise ValueError("Readout case or kind binding mismatch")

        def job(identity, kind):
            matches = [r for r in case.job_records if r["job_id"] == identity]
            if len(matches) != 1 or matches[0]["kind"] != kind or matches[0]["case_id"] != context.case_id:
                raise ValueError("Readout job binding mismatch")
            return matches[0]

        record = job(context.job_id, context.kind)
        source = store.observation_input(context.case_id, context.job_id)
        generation = job(source["generation_job_id"], "COARSE_SEARCH")
        if record["scope_ref"] != generation["scope_ref"]:
            raise ValueError("Readout generation scope mismatch")
        clip_ref = source["incident_clip_ref"]
        if not isinstance(clip_ref, str) or not clip_ref.strip():
            raise ValueError("Readout incident clip required")
        executions = store.read_executions(case)

        def successful(record):
            latest = max((e for e in executions if e["job_id"] == record["job_id"]),
                         key=lambda e: e["attempt"], default=None)
            if latest is None or latest["status"] != "SUCCEEDED":
                return None
            return self.reader(conn, record["kind"], tuple(latest["produced"]))

        coarse = successful(generation)
        if coarse is None or sum(c["candidate_id"] == source["candidate_id"] for c in coarse["candidate_events"]) != 1:
            raise ValueError("Readout fixed generation candidate unavailable")
        # Case fixes no clip-job id on a Readout input. Prove the shared clip
        # came from a successful build for this exact candidate and generation.
        for clip in case.job_records:
            if clip["kind"] != "INCIDENT_CLIP_BUILD":
                continue
            fixed = store.observation_input(context.case_id, clip["job_id"])
            if any(fixed[key] != source[key] for key in ("candidate_id", "generation_job_id")):
                continue
            clip = job(clip["job_id"], "INCIDENT_CLIP_BUILD")
            if clip["scope_ref"] != record["scope_ref"]:
                raise ValueError("Readout clip scope mismatch")
            content = successful(clip)
            if content is not None and content["incident_clip_ref"] == clip_ref:
                return ReadoutInput(context.case_id, source["candidate_id"], source["generation_job_id"], clip_ref)
        raise ValueError("Readout clip binding mismatch")
