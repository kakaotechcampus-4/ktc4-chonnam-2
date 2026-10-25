"""Public Recording scope resolution -> execution-local Search media resources."""
from contextlib import contextmanager
from functools import partial

from daesingo import search
from daesingo.recording import ContractRef, TransactionalRecordingRepository, LocalAnalysisMaterializer
from daesingo.recording.factory import build_recording_service
from daesingo.search.sources import RecordingAnalysisSourceResolver, SourceMeta


class ProductionMediaFactory:
    def __init__(self, *, transaction, storage_root, temp_root, settings, search_settings, media=None):
        self.transaction, self.storage_root, self.temp_root = transaction, storage_root, temp_root
        self.settings, self.search_settings, self.media = settings, search_settings, media

    @contextmanager
    def __call__(self, data):
        repository = TransactionalRecordingRepository(self.transaction, storage_root=self.storage_root)
        materializer = partial(self.media.materializer, LocalAnalysisMaterializer) if self.media is not None else None
        with build_recording_service(repository, self.settings, temp_root=self.temp_root,
                                     materializer_factory=materializer, case_id=data.case_id) as recording:
            scope = data.scope
            if scope is None or data.case_id is None or self.settings.profile_ref is None:
                raise ValueError("bound scope and explicit Recording profile required")
            if len(scope.time_ranges) != 1 or scope.time_ranges[0].kind != "TIMELINE_RELATIVE":
                raise ValueError("one explicit relative range required")
            span = scope.time_ranges[0]
            timeline_ref = {"timeline_id": span.timeline_ref.timeline_id, "revision": span.timeline_ref.revision}
            if not data.video_stream_refs:
                raise ValueError("Case-selected VIDEO refs required")
            for stream_ref in data.video_stream_refs:
                stream = recording.get_media_stream(stream_ref)
                data.checkpoint()
                if not recording.owns_asset(data.case_id, ContractRef(kind="source_asset", ref=stream.source_asset_ref)):
                    raise ValueError("scope source is not owned by case")
                data.checkpoint()
            resolution = recording.resolve_span(timeline_ref,
                {"start_sec": span.start_ms / 1000, "end_sec": span.end_ms / 1000},
                media_stream_refs=list(data.video_stream_refs))
            data.checkpoint()
            if not resolution.spans:
                raise ValueError("scope has no usable source")
            for source_ref in dict.fromkeys(s.source_asset_ref for s in resolution.spans):
                recording.observe_time_sources(source_ref)
                data.checkpoint()
            source = recording.prepare_analysis_source_from_resolution(resolution, self.settings.profile_ref)
            data.checkpoint()
            ref = search.ContractRef(kind="analysis_source", ref=source.analysis_source_ref)
            resolver = RecordingAnalysisSourceResolver({scope.scope_id: (ref,)},
                {ref.ref: SourceMeta(source.duration_sec, source.timeline_ref.timeline_id,
                    source.timeline_ref.revision, source.timeline_range.start_sec)}, recording)
            service = search.build_gemini_search_service(self.search_settings.api_key.get_secret_value(),
                                                       resolver, self.search_settings.config)
            data.checkpoint()
            yield service
