"""Coarse frames are execution-local and independent of Fine/clip."""
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.recording import RecordingCapabilityError
from daesingo.worker.search_handlers import search_registry
from search_failure_support import SuccessfulSearchPolicy
from test_search_handlers import context, fixtures


def test_coarse_payload_contains_frames_once_before_media_closes():
    from daesingo.worker.search_handlers import SearchInput
    scope, coarse, _ = fixtures()
    calls = []
    @contextmanager
    def service(data):
        class Service:
            def search_candidates(self, value, *, usage_sink):
                calls.append('provider')
                return coarse
        yield Service()
        calls.append('close')
    def frames(ctx, data, candidates):
        assert calls == ['provider']
        calls.append('frames')
        return {candidates[0].candidate_id: 'frame-one'}
    registry = search_registry(load=lambda ctx: SearchInput(scope=scope), intent_factory=lambda: None,
        service_factory=service, failures=SuccessfulSearchPolicy(), coarse_frames=frames)
    result = registry.dispatch(context('COARSE_SEARCH', object()))
    assert result.status == 'SUCCEEDED'
    assert result.objects[0].payload['candidate_frame_refs'] == {coarse.candidates[0].candidate_id: 'frame-one'}
    assert calls == ['provider', 'frames', 'close']


def setup_issuer(error=None):
    from daesingo.worker.coarse_frames import CoarseFrameIssuer
    from daesingo.worker.search_handlers import SearchInput
    scope, coarse, _ = fixtures()
    candidate = coarse.candidates[0]
    # Bind the fixed scope to the candidate fixture's timeline and range.
    raw = scope.model_dump(mode='json')
    span = candidate.span
    raw['time_ranges'] = [{'kind': 'TIMELINE_RELATIVE',
        'timeline_ref': {'timeline_id': span.timeline_id, 'revision': span.timeline_revision},
        'start_ms': span.start_ms, 'end_ms': span.end_ms}]
    data = SearchInput(scope=type(scope).model_validate(raw), case_id='case_one', video_stream_refs=('video',))
    ctx = context('COARSE_SEARCH', object())
    calls = []
    class Recording:
        def get_media_stream(self, ref):
            return SimpleNamespace(media_type='VIDEO', source_asset_ref='source')
        def owns_asset(self, case_id, ref): return case_id == 'case_one'
        def resolve_span(self, timeline, requested, **kwargs):
            calls.append('span')
            return SimpleNamespace(model_dump=lambda **kw: {})
        def resolve_frame(self, locator):
            calls.append('frame')
            if error: raise error
            return SimpleNamespace(frame_ref='frame-one')
    recording = Recording()
    @contextmanager
    def factory(data):
        calls.append('open')
        try: yield recording
        finally: calls.append('close')
    issuer = CoarseFrameIssuer(recording_factory=factory,
        candidate_ids=lambda events: (candidate.candidate_id,),
        candidate_position=lambda *args: ('video', .1))
    return issuer, ctx, data, candidate, recording, calls


def test_issuer_uses_own_scope_and_closes_context():
    issuer, ctx, data, candidate, _, calls = setup_issuer()
    assert issuer(ctx, data, (candidate,)) == {candidate.candidate_id: 'frame-one'}
    assert calls == ['open', 'span', 'frame', 'close']


@pytest.mark.parametrize('code', ['FRAME_NOT_FOUND', 'STREAM_UNAVAILABLE', 'OUT_OF_RANGE', 'TEMPORARY_FAILURE'])
def test_only_frame_refusals_become_null(code):
    issuer, ctx, data, candidate, _, calls = setup_issuer(RecordingCapabilityError(code, 'test'))
    assert issuer(ctx, data, (candidate,)) == {candidate.candidate_id: None}
    assert calls[-1] == 'close'


@pytest.mark.parametrize('error', [RecordingCapabilityError('UNKNOWN_REF', 'test'), ValueError('db')])
def test_other_errors_propagate_and_close(error):
    issuer, ctx, data, candidate, _, calls = setup_issuer(error)
    with pytest.raises(type(error)): issuer(ctx, data, (candidate,))
    assert calls[-1] == 'close'


@pytest.mark.parametrize('mode', ['scope', 'owner', 'cancel', 'foreign_stream', 'span_error'])
def test_binding_cancellation_and_non_frame_errors_do_not_issue(mode):
    issuer, ctx, data, candidate, recording, calls = setup_issuer()
    if mode == 'scope': data = replace(data, case_id='different')
    if mode == 'owner': recording.owns_asset = lambda *args: False
    if mode == 'cancel': ctx.cancel_signal.request()
    if mode == 'foreign_stream': issuer.candidate_position = lambda *args: ('foreign', .1)
    if mode == 'span_error':
        def fail(*args, **kwargs): raise RecordingCapabilityError('TEMPORARY_FAILURE', 'not frame')
        recording.resolve_span = fail
    with pytest.raises((ValueError, CancellationRequested, RecordingCapabilityError)):
        issuer(ctx, data, (candidate,))
    assert 'frame' not in calls


@pytest.mark.parametrize('mode', ['duplicate', 'rank_four', 'timeline', 'range'])
def test_unbound_candidate_is_rejected_before_recording(mode):
    issuer, ctx, data, candidate, _, calls = setup_issuer()
    raw = candidate.model_dump(mode='json')
    if mode == 'duplicate': issuer.candidate_ids = lambda events: (candidate.candidate_id,) * 2
    if mode == 'rank_four': raw['rank'] = 4
    if mode == 'timeline': raw['span']['timeline_id'] = 'other'
    if mode == 'range': raw['span']['end_ms'] += 1
    candidate = type(candidate).model_validate(raw)
    with pytest.raises(ValueError): issuer(ctx, data, (candidate,))
    assert calls == []


def test_valid_end_representative_is_delegated_to_case_without_decode():
    issuer, ctx, data, candidate, _, calls = setup_issuer()
    raw = candidate.model_dump(mode='json')
    raw['span']['representative_ms'] = raw['span']['end_ms']
    candidate = type(candidate).model_validate(raw)
    issuer.candidate_position = lambda *args: None
    assert issuer(ctx, data, (candidate,)) == {candidate.candidate_id: None}
    assert calls == ['open', 'span', 'close']


def test_no_selected_candidates_do_not_open_recording():
    issuer, ctx, data, _, _, calls = setup_issuer()
    issuer.candidate_ids = lambda events: ()
    assert issuer(ctx, data, ()) == {} and calls == []


def test_cancel_after_decode_propagates_and_closes():
    issuer, ctx, data, candidate, recording, calls = setup_issuer()
    original = recording.resolve_frame
    def decode(locator):
        result = original(locator)
        ctx.cancel_signal.request()
        return result
    recording.resolve_frame = decode
    with pytest.raises(CancellationRequested): issuer(ctx, data, (candidate,))
    assert calls[-1] == 'close'


@pytest.mark.parametrize('mode', ['frame_error', 'bad_refs', 'failed', 'empty', 'fine'])
def test_postprocessing_failure_never_repeats_paid_search(mode):
    from daesingo.worker.search_handlers import SearchInput
    scope, coarse, fine = fixtures()
    calls = []
    if mode == 'failed':
        from daesingo.search.runs import RunOutcome
        coarse = SimpleNamespace(analysis_run=coarse.analysis_run.model_copy(update={'outcome': RunOutcome.FAILED}),
                                 candidates=())
    if mode == 'empty': coarse = SimpleNamespace(analysis_run=coarse.analysis_run, candidates=())
    @contextmanager
    def service(data):
        class Service:
            resolver = SimpleNamespace(resolve=lambda scope: (SimpleNamespace(source_ref=fine.analysis_run.input_ref),))
            def search_candidates(self, *args, **kwargs):
                calls.append('provider')
                return coarse
            def verify_visual(self, *args, **kwargs):
                calls.append('fine')
                return fine
        try: yield Service()
        finally: calls.append('close')
    def frames(*args):
        calls.append('frames')
        if mode == 'frame_error': raise ValueError('persistence')
        return {'foreign': 'frame'}
    ctx = context('FINE_VERIFY' if mode == 'fine' else 'COARSE_SEARCH', object())
    registry = search_registry(load=lambda ctx: SearchInput(scope=scope, candidate=fixtures()[1].candidates[0],
        max_latency_sec=30), intent_factory=lambda: None, service_factory=service,
        failures=SuccessfulSearchPolicy(), coarse_frames=frames)
    result = registry.dispatch(ctx)
    assert calls[-1] == 'close'
    assert calls.count('provider') == (0 if mode == 'fine' else 1)
    if mode in {'frame_error', 'bad_refs'}:
        assert result.status == 'FAILED' and result.failure_kind == 'RUNTIME_HANDLER_ERROR'
        assert calls.count('frames') == 1 and not result.objects
    else:
        assert 'frames' not in calls
