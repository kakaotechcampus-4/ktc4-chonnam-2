from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace

import pytest

from daesingo.case.service import candidates_from_events
from daesingo.case.store import CaseStore
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import validated_terminal
from daesingo.recording import RecordingCapabilityError
from test_search_inputs import setup_input
from test_search_handlers import fixtures

KIND = 'CANDIDATE_VIDEO_PREVIEW'


def bound():
    ctx, case, old, read, execution = setup_input(KIND)
    source = case.observation_inputs[ctx.job_id]
    source.pop('max_latency_sec')
    source['video_stream_refs'] = ['video']
    case.sources = [{'video_stream_ref': 'video'}]
    case.stage = 'EVIDENCE_REVIEW'
    case.settled_jobs['generation'] = 'REFLECTED'
    coarse = read(old.conn, 'COARSE_SEARCH', tuple(execution['produced']))
    coarse['analysis_run'] = fixtures()[1].analysis_run.model_dump(mode='json')
    case.candidates = candidates_from_events(coarse['candidate_events'])
    def make():
        store = CaseStore(conn=old.conn, executions=lambda conn, ids: [deepcopy(execution)])
        store.register(case)
        module = import_module('daesingo.worker.candidate_video')
        return module.CandidateVideoInputs(transaction=lambda callback: callback(store.conn),
            store_factory=lambda conn: store, reader=lambda *args: deepcopy(coarse))
    return ctx, case, coarse, execution, make


def test_inputs_bind_current_top_three_without_fine_and_detach():
    ctx, case, _, _, make = bound()
    data = make()(ctx)
    assert data.case_id == ctx.case_id
    assert data.request.candidate_id == case.candidates[0].candidate_id
    assert data.request.video_stream_refs == ('video',)
    case.observation_inputs[ctx.job_id]['span']['end_ms'] += 1
    assert data.request.span.end_ms != case.observation_inputs[ctx.job_id]['span']['end_ms']


@pytest.mark.parametrize('mode', ['foreign_case', 'wrong_kind', 'scope', 'generation', 'failed_coarse',
    'candidate', 'span', 'rank', 'stale', 'streams', 'coarse_span', 'coarse_run', 'scope_timeline'])
def test_mismatched_inputs_are_rejected_before_decode(mode):
    ctx, case, coarse, execution, make = bound()
    source = case.observation_inputs[ctx.job_id]
    if mode == 'foreign_case': ctx = replace(ctx, case_id='foreign')
    if mode == 'wrong_kind': ctx = replace(ctx, kind='INCIDENT_CLIP_BUILD')
    if mode == 'scope': case.job_records[-1]['scope_ref'] = 'foreign'
    if mode == 'generation': source['generation_job_id'] = 'foreign'
    if mode == 'failed_coarse': execution['status'] = 'FAILED'
    if mode == 'candidate': source['candidate_id'] = 'foreign'
    if mode == 'span': source['span']['end_ms'] += 1
    if mode == 'rank': case.candidates[0].rank = 4
    if mode == 'stale': case.candidates[0].stale_revision = True
    if mode == 'streams': source['video_stream_refs'] = ['foreign']
    if mode == 'coarse_span': coarse['candidate_events'][0]['span']['end_ms'] += 1
    if mode == 'scope_timeline':
        scope = case.analysis_scopes[case.job_records[0]['scope_ref']]
        scope['time_ranges'] = [{'kind': 'TIMELINE_RELATIVE', 'timeline_ref': {'timeline_id': 'foreign', 'revision': 1}, 'start_ms': 0, 'end_ms': 999999}]
    if mode == 'coarse_run': coarse['candidate_events'][0]['run_id'] = 'foreign'
    with pytest.raises((ValueError, KeyError)):
        make()(ctx)


def dependencies(*, owns=True, build_error=None, cancel=False):
    ctx, _, _, _, make = bound()
    data = make()(ctx)
    calls = []
    class Recording:
        def get_media_stream(self, ref):
            assert ref == 'video'
            return SimpleNamespace(media_type='VIDEO', source_asset_ref='source')
        def owns_asset(self, case_id, ref):
            assert case_id == ctx.case_id and ref.kind == 'source_asset'
            return owns
        def resolve_span(self, timeline, requested, **kwargs):
            calls.append('resolve')
            assert timeline['timeline_id'] == data.request.span.timeline_id
            assert requested['start_sec'] == data.request.span.start_ms / 1000
            assert kwargs == {'media_stream_refs': ['video']}
            return SimpleNamespace(spans=[SimpleNamespace(media_stream_ref='video')])
        def build_incident_clip(self, resolution):
            calls.append('build')
            if cancel: ctx.cancel_signal.request()
            if build_error: raise build_error
            return SimpleNamespace(incident_clip_ref='preview-clip')
    @contextmanager
    def factory(value):
        assert value is data
        try: yield Recording()
        finally: calls.append('close')
    module = import_module('daesingo.worker.candidate_video')
    registry = module.candidate_video_registry(load=lambda context: data, service_factory=factory)
    return ctx, registry, calls


def test_handler_builds_one_clip_and_produces_preview_only():
    ctx, registry, calls = dependencies()
    result = validated_terminal(registry.dispatch(ctx), execution_id=ctx.execution_id)
    assert result.status == 'SUCCEEDED'
    assert result.objects[0].payload == {'incident_clip_ref': 'preview-clip'}
    assert result.objects[0].kind == 'candidate_video_result'
    assert calls == ['resolve', 'build', 'close']


def test_foreign_source_rejected_before_resolution():
    ctx, registry, calls = dependencies(owns=False)
    with pytest.raises(ValueError): registry._handlers[ctx.kind](ctx)
    assert calls == ['close']


def test_expected_build_failure_is_local_but_db_errors_propagate():
    ctx, registry, _ = dependencies(build_error=RecordingCapabilityError('INCIDENT_CLIP_BUILD_FAILED', 'unavailable'))
    assert registry.dispatch(ctx).status == 'FAILED'
    ctx, registry, _ = dependencies(build_error=RuntimeError('database failed'))
    with pytest.raises(RuntimeError): registry._handlers[ctx.kind](ctx)


def test_cancellation_is_not_swallowed_after_decode():
    ctx, registry, calls = dependencies(cancel=True)
    with pytest.raises(CancellationRequested): registry.dispatch(ctx)
    assert calls[-1] == 'close'
