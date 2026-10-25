"""Read-only, detached Search inputs through Case's public facade.

Only DB reads happen in the supplied transaction callback. No domain capability
is invoked here; provider/media work starts after the caller releases it.
"""

from copy import deepcopy

from daesingo import search
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.read_port import read_executions
from daesingo.worker.search_handlers import SearchInput


def _store(conn):
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions)


class SearchInputs:
    def __init__(self, *, transaction, store_factory=_store, reader=None):
        self.transaction = transaction
        self.store_factory = store_factory
        self.reader = reader if reader is not None else ProducedReader()

    def __call__(self, context) -> SearchInput:
        return self.transaction(lambda conn: self._read(conn, context))

    def _read(self, conn, context):
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError("Search input store must share caller connection")
        case = store.get_case(context.case_id)
        job = next((r for r in case.job_records if r["job_id"] == context.job_id), None)
        if (job is None or job["kind"] != context.kind or job["case_id"] != context.case_id):
            raise ValueError("Search job binding mismatch")
        if context.kind == "HINT_EXTRACT":
            return SearchInput(description=case.description, prior_hints=deepcopy(case.hints),
                               case_id=context.case_id, checkpoint=context.checkpoint)
        scope = search.AnalysisScope.model_validate(case.analysis_scopes[job["scope_ref"]])
        if scope.scope_id != job["scope_ref"]:
            raise ValueError("Search scope binding mismatch")
        if context.kind == "COARSE_SEARCH":
            return SearchInput(scope=scope, prior_hints=deepcopy(case.hints),
                               case_id=context.case_id, checkpoint=context.checkpoint,
                               video_stream_refs=tuple(s["video_stream_ref"] for s in case.sources if s.get("video_stream_ref")))
        if context.kind != "FINE_VERIFY":
            raise ValueError("unsupported Search input kind")
        source = store.observation_input(context.case_id, context.job_id)
        generation = next((r for r in case.job_records if r["job_id"] == source["generation_job_id"]), None)
        if (generation is None or generation["kind"] != "COARSE_SEARCH"
                or generation["scope_ref"] != job["scope_ref"]):
            raise ValueError("Search generation binding mismatch")
        executions = [e for e in store.read_executions(case) if e["job_id"] == generation["job_id"]]
        latest = max(executions, key=lambda e: e["attempt"], default=None)
        if latest is None or latest["status"] != "SUCCEEDED":
            raise ValueError("successful Search generation required")
        content = self.reader(conn, "COARSE_SEARCH", tuple(latest["produced"]))
        candidates = [c for c in content["candidate_events"] if c["candidate_id"] == source["candidate_id"]]
        if len(candidates) != 1:
            raise ValueError("fixed Search candidate unavailable")
        candidate = search.CandidateEvent.model_validate(candidates[0])
        # Case fixes the interval's four coordinates; representative_ms is a
        # CandidateEvent observation, not part of observation_input.span.
        interval = {key: getattr(candidate.span, key)
                    for key in ("timeline_id", "timeline_revision", "start_ms", "end_ms")}
        if interval != source["span"]:
            raise ValueError("Search candidate span mismatch")
        return SearchInput(scope=scope, candidate=candidate, prior_hints=deepcopy(case.hints),
                           case_id=context.case_id, checkpoint=context.checkpoint,
                           video_stream_refs=tuple(s["video_stream_ref"] for s in case.sources if s.get("video_stream_ref")))
