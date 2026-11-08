"""Case-selected Coarse frames before T1; no provider or Case mutation."""
import math

from daesingo.recording import ContractRef
from daesingo.worker.incident_frames import FRAME_REFUSALS
from daesingo.recording import RecordingCapabilityError


def validate_frame_refs(refs, candidates):
    allowed = {c.candidate_id for c in candidates if type(c.rank) is int and 1 <= c.rank <= 3}
    if (type(refs) is not dict or len(refs) > 3 or not set(refs) <= allowed
            or any(type(key) is not str or not key for key in refs)
            or any(value is not None and (type(value) is not str or not value) for value in refs.values())):
        raise ValueError('invalid Coarse candidate frame refs')
    return dict(refs)


class CoarseFrameIssuer:
    def __init__(self, *, recording_factory, candidate_ids, candidate_position):
        self.recording_factory = recording_factory
        self.candidate_ids, self.candidate_position = candidate_ids, candidate_position

    def __call__(self, context, data, candidates):
        context.checkpoint()
        if context.case_id != data.case_id or data.scope is None:
            raise ValueError('Coarse frame Case binding required')
        selected_ids = tuple(self.candidate_ids(candidates))
        if (len(selected_ids) > 3 or len(set(selected_ids)) != len(selected_ids)
                or any(type(cid) is not str or not cid for cid in selected_ids)):
            raise ValueError('invalid Case candidate selection')
        if not selected_ids:
            return {}
        events = {c.candidate_id: c for c in candidates}
        if len(events) != len(candidates) or not set(selected_ids) <= events.keys():
            raise ValueError('candidate identity mismatch')
        scope = data.scope
        if len(scope.time_ranges) != 1 or scope.time_ranges[0].kind != 'TIMELINE_RELATIVE':
            raise ValueError('one fixed relative range required')
        fixed = scope.time_ranges[0]
        timeline = {'timeline_id': fixed.timeline_ref.timeline_id, 'revision': fixed.timeline_ref.revision}
        selected = data.video_stream_refs
        if not selected or len(set(selected)) != len(selected):
            raise ValueError('explicit VIDEO selection required')
        for cid in selected_ids:
            c = events[cid]
            s = c.span
            if (type(c.rank) is not int or not 1 <= c.rank <= 3
                    or s.timeline_id != timeline['timeline_id'] or s.timeline_revision != timeline['revision']
                    or not fixed.start_ms <= s.start_ms < s.end_ms <= fixed.end_ms
                    or s.representative_ms is None or not s.start_ms <= s.representative_ms <= s.end_ms):
                raise ValueError('Coarse candidate scope mismatch')
        refs: dict[str, str | None] = {}
        cache: dict[tuple[str, float], str | None] = {}
        with self.recording_factory(data) as recording:
            for ref in selected:
                stream = recording.get_media_stream(ref)
                context.checkpoint()
                if stream.media_type != 'VIDEO' or not recording.owns_asset(data.case_id,
                        ContractRef(kind='source_asset', ref=stream.source_asset_ref)):
                    raise ValueError('Coarse frame source is not owned VIDEO')
                context.checkpoint()
            for cid in selected_ids:
                context.checkpoint()
                span = events[cid].span
                resolution = recording.resolve_span(timeline,
                    {'start_sec': span.start_ms / 1000, 'end_sec': span.end_ms / 1000},
                    **({'media_stream_ref': selected[0]} if len(selected) == 1
                       else {'media_stream_refs': list(selected)}))
                context.checkpoint()
                position = self.candidate_position(resolution.model_dump(mode='json'),
                    span.model_dump(mode='json'), span.representative_ms)
                context.checkpoint()
                if position is None:
                    refs[cid] = None
                    continue
                ref, offset = position
                if (ref not in selected or isinstance(offset, bool) or not isinstance(offset, (int, float))
                        or not math.isfinite(offset) or offset < 0):
                    raise ValueError('invalid Case frame position')
                key = (ref, offset)
                if key not in cache:
                    try:
                        frame = recording.resolve_frame({'kind': 'STREAM_POSITION',
                            'media_stream_ref': ref, 'source_offset_sec': offset})
                    except RecordingCapabilityError as error:
                        if error.code not in FRAME_REFUSALS:
                            raise
                        cache[key] = None
                    else:
                        cache[key] = frame.frame_ref
                    context.checkpoint()
                refs[cid] = cache[key]
        context.checkpoint()
        return validate_frame_refs(refs, candidates)
