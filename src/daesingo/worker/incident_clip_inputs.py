"""Detached Case-fixed clip inputs, read only in a short caller transaction."""
from dataclasses import dataclass

from daesingo import search
from daesingo.common.jobs.produced import ProducedReader
from daesingo.search.runs import AnalysisRun
from daesingo.search.scope import TimeRangeKind
from daesingo.search.visual import VisualVerificationResult


@dataclass(frozen=True)
class IncidentClipInput:
    case_id: str
    timeline_ref: dict
    requested_range: dict
    analysis_source_ref: str
    video_stream_refs: tuple[str, ...]


class IncidentClipInputs:
    def __init__(self, *, transaction, store_factory, reader=None):
        self.transaction, self.store_factory = transaction, store_factory
        self.reader = reader if reader is not None else ProducedReader()

    def __call__(self, context):
        return self.transaction(lambda conn: self._read(conn, context))

    def _read(self, conn, context):
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError("clip input store must share caller connection")
        case = store.get_case(context.case_id)

        def job(identity, kind):
            matches = [r for r in case.job_records if r["job_id"] == identity]
            if len(matches) != 1 or matches[0]["kind"] != kind or matches[0]["case_id"] != context.case_id:
                raise ValueError("clip job binding mismatch")
            return matches[0]

        if context.kind != "INCIDENT_CLIP_BUILD":
            raise ValueError("unsupported clip input kind")
        clip_job = job(context.job_id, context.kind)
        source = store.observation_input(context.case_id, context.job_id)
        fine_job = job(source["fine_job_id"], "FINE_VERIFY")
        generation = job(source["generation_job_id"], "COARSE_SEARCH")
        scope_ref = clip_job["scope_ref"]
        scope = search.AnalysisScope.model_validate(case.analysis_scopes[scope_ref])
        if scope.scope_id != scope_ref or fine_job["scope_ref"] != scope_ref or generation["scope_ref"] != scope_ref:
            raise ValueError("clip scope binding mismatch")
        fine_input = store.observation_input(context.case_id, fine_job["job_id"])
        if any(source[key] != fine_input[key] for key in ("candidate_id", "generation_job_id", "span")):
            raise ValueError("clip Fine input binding mismatch")
        executions = store.read_executions(case)

        def successful(record):
            latest = max((e for e in executions if e["job_id"] == record["job_id"]),
                         key=lambda e: e["attempt"], default=None)
            if latest is None or latest["status"] != "SUCCEEDED":
                raise ValueError("successful clip dependency required")
            return self.reader(conn, record["kind"], tuple(latest["produced"]))

        coarse = successful(generation)
        run = AnalysisRun.model_validate(coarse["analysis_run"])
        if (run.operation != "CANDIDATE_SEARCH" or run.outcome == "FAILED"
                or run.input_ref.kind != "ANALYSIS_SCOPE" or run.input_ref.ref != scope_ref):
            raise ValueError("clip generation result binding mismatch")
        candidates = [c for c in coarse["candidate_events"] if c["candidate_id"] == source["candidate_id"]]
        if len(candidates) != 1:
            raise ValueError("fixed clip candidate unavailable")
        candidate = search.CandidateEvent.model_validate(candidates[0])
        span = {key: getattr(candidate.span, key) for key in ("timeline_id", "timeline_revision", "start_ms", "end_ms")}
        if span != source["span"] or candidate.run_id != run.run_id:
            raise ValueError("clip candidate binding mismatch")
        relative = [r for r in scope.time_ranges if r.kind == TimeRangeKind.TIMELINE_RELATIVE]
        if relative and not any(
            r.timeline_ref.timeline_id == span["timeline_id"]
            and r.timeline_ref.revision == span["timeline_revision"]
            for r in relative
        ):
            raise ValueError("clip scope timeline binding mismatch")
        # Recording's actual frame coverage may exceed the requested scope.
        # Search/Fine use that source coverage; do not impose a new range policy.
        fine = VisualVerificationResult.model_validate(successful(fine_job))
        if (fine.analysis_run.outcome == "FAILED" or fine.visual_evidence.candidate_id != candidate.candidate_id
                or fine.analysis_run.input_ref.kind != "analysis_source"):
            raise ValueError("clip Fine result binding mismatch")
        return IncidentClipInput(case_id=context.case_id,
            timeline_ref={"timeline_id": span["timeline_id"], "revision": span["timeline_revision"]},
            requested_range={"start_sec": span["start_ms"] / 1000, "end_sec": span["end_ms"] / 1000},
            analysis_source_ref=fine.analysis_run.input_ref.ref,
            video_stream_refs=tuple(s["video_stream_ref"] for s in case.sources if s.get("video_stream_ref")))
