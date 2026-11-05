from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from daesingo import search
from daesingo.case.candidate_video import PREVIEW_KIND, eligible
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.produced import ProducedObject, ProducedReader
from daesingo.recording import ContractRef, RecordingCapabilityError
from daesingo.search.runs import AnalysisRun
from daesingo.search.scope import TimeRangeKind
from daesingo.worker.registry import KindRegistry


class PreviewSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)
    timeline_id: str = Field(min_length=1)
    timeline_revision: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class PreviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    candidate_id: str = Field(min_length=1)
    generation_job_id: str = Field(min_length=1)
    span: PreviewSpan
    video_stream_refs: tuple[str, ...] = Field(min_length=1)


NOT_CURRENT = 'RUNTIME_PREVIEW_NOT_CURRENT'


class PreviewNotCurrent(ValueError):
    """탐색 세대·후보가 바뀐 뒤 도착한 preview — 오류가 아니라 늦은 작업이라 실패 종류를 따로 둔다."""


@dataclass(frozen=True, slots=True)
class CandidateVideoInput:
    case_id: str
    request: PreviewRequest


class CandidateVideoInputs:
    def __init__(self, *, transaction, store_factory, reader=None):
        self.transaction, self.store_factory = transaction, store_factory
        self.reader = reader if reader is not None else ProducedReader()

    def __call__(self, context) -> CandidateVideoInput:
        return self.transaction(lambda conn: self._read(conn, context))

    def _read(self, conn, context) -> CandidateVideoInput:
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError('preview input store must share caller connection')
        case = store.get_case(context.case_id)
        record = next(r for r in case.job_records if r['job_id'] == context.job_id)
        if context.kind != PREVIEW_KIND or record['kind'] != PREVIEW_KIND or record['case_id'] != context.case_id:
            raise ValueError('preview job binding mismatch')
        request = PreviewRequest.model_validate(store.observation_input(context.case_id, context.job_id))
        candidate = next((c for c in case.candidates if c.candidate_id == request.candidate_id), None)
        if (candidate is None or not eligible(case, candidate)
                or request.generation_job_id != case.current_generation_job_id()):
            raise PreviewNotCurrent('preview candidate is no longer current')
        if request.span.model_dump() != candidate.span or request.span.end_ms <= request.span.start_ms:
            raise ValueError('preview candidate binding mismatch')
        selected = tuple(s['video_stream_ref'] for s in case.sources if s.get('video_stream_ref'))
        if request.video_stream_refs != selected or len(set(selected)) != len(selected):
            raise ValueError('preview stream binding mismatch')
        generation = next(r for r in case.job_records if r['job_id'] == request.generation_job_id)
        if (generation['kind'] != 'COARSE_SEARCH' or generation['case_id'] != context.case_id
                or generation['scope_ref'] != record['scope_ref']):
            raise ValueError('preview scope binding mismatch')
        scope = search.AnalysisScope.model_validate(case.analysis_scopes[record['scope_ref']])
        relative = [r for r in scope.time_ranges if r.kind == TimeRangeKind.TIMELINE_RELATIVE]
        if scope.scope_id != record['scope_ref'] or (relative and not any(
            r.timeline_ref.timeline_id == request.span.timeline_id
            and r.timeline_ref.revision == request.span.timeline_revision for r in relative
        )):
            raise ValueError('preview scope timeline binding mismatch')
        executions = [e for e in store.read_executions(case) if e['job_id'] == request.generation_job_id]
        latest = max(executions, key=lambda e: e['attempt'], default=None)
        if latest is None or latest['status'] != 'SUCCEEDED':
            raise ValueError('successful preview generation required')
        coarse = self.reader(conn, 'COARSE_SEARCH', tuple(latest['produced']))
        run = AnalysisRun.model_validate(coarse['analysis_run'])
        events = [search.CandidateEvent.model_validate(e) for e in coarse['candidate_events']
                  if e['candidate_id'] == request.candidate_id]
        if (run.operation != 'CANDIDATE_SEARCH' or run.outcome == 'FAILED'
                or run.input_ref.kind != 'ANALYSIS_SCOPE' or run.input_ref.ref != record['scope_ref']
                or len(events) != 1 or events[0].run_id != run.run_id
                or events[0].rank != candidate.rank
                or events[0].span.model_dump(include=set(PreviewSpan.model_fields)) != request.span.model_dump()):
            raise ValueError('preview coarse result binding mismatch')
        return CandidateVideoInput(context.case_id, request)


def candidate_video_registry(*, load, service_factory=None) -> KindRegistry:
    if service_factory is None:
        return KindRegistry({})

    def invoke(context) -> HandlerResult:
        context.checkpoint()
        try:
            data = load(context)
        except PreviewNotCurrent:
            return HandlerResult(status='FAILED', failure_kind=NOT_CURRENT)
        context.checkpoint()
        with service_factory(data) as recording:
            context.checkpoint()
            request = data.request
            for ref in request.video_stream_refs:
                stream = recording.get_media_stream(ref)
                context.checkpoint()
                if stream.media_type != 'VIDEO' or not recording.owns_asset(data.case_id,
                        ContractRef(kind='source_asset', ref=stream.source_asset_ref)):
                    raise ValueError('preview source is not owned VIDEO')
                context.checkpoint()
            span = request.span
            resolution = recording.resolve_span({'timeline_id': span.timeline_id, 'revision': span.timeline_revision},
                {'start_sec': span.start_ms / 1000, 'end_sec': span.end_ms / 1000},
                media_stream_refs=list(request.video_stream_refs))
            context.checkpoint()
            if any(s.media_stream_ref not in request.video_stream_refs for s in resolution.spans):
                raise ValueError('preview resolution stream mismatch')
            try:
                clip = recording.build_incident_clip(resolution)
            except RecordingCapabilityError as error:
                if error.code != 'INCIDENT_CLIP_BUILD_FAILED':
                    raise
                result = HandlerResult(status='FAILED', failure_kind='RECORDING_INCIDENT_CLIP_BUILD_FAILED')
            else:
                result = HandlerResult(objects=(ProducedObject(kind='candidate_video_result',
                    payload={'incident_clip_ref': clip.incident_clip_ref}),))
            context.checkpoint()
        context.checkpoint()
        return result

    return KindRegistry({PREVIEW_KIND: invoke})
