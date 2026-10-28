"""One public clip build per execution; T1/T2 remain Worker responsibilities."""
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.produced import ProducedObject
from daesingo.recording import ContractRef, RecordingCapabilityError
from daesingo.worker.registry import KindRegistry


def incident_clip_registry(*, load, service_factory=None):
    if service_factory is None:
        return KindRegistry({})

    def invoke(context):
        context.checkpoint()
        data = load(context)
        context.checkpoint()
        with service_factory(data) as recording:
            context.checkpoint()
            source = recording.get_analysis_source(data.analysis_source_ref)
            context.checkpoint()
            if (source.timeline_ref is None or source.timeline_range is None or source.duration_sec is None
                    or source.duration_sec <= 0
                    or source.timeline_ref.timeline_id != data.timeline_ref["timeline_id"]
                    or source.timeline_ref.revision != data.timeline_ref["revision"]
                    # Search publishes CandidateSpan with round(seconds * 1000).
                    # Compare in that coordinate system, preserving the exact
                    # Case request for Recording's authoritative resolution.
                    or round(source.timeline_range.start_sec * 1000) > round(data.requested_range["start_sec"] * 1000)
                    or round((source.timeline_range.start_sec + source.duration_sec) * 1000)
                        < round(data.requested_range["end_sec"] * 1000)):
                raise ValueError("clip source timeline binding mismatch")
            videos = []
            for ref in source.media_stream_refs:
                stream = recording.get_media_stream(ref)
                context.checkpoint()
                if stream.media_type == "VIDEO":
                    if not recording.owns_asset(data.case_id, ContractRef(kind="source_asset", ref=stream.source_asset_ref)):
                        raise ValueError("clip source is not owned by case")
                    context.checkpoint()
                    videos.append(ref)
            if len(videos) != 1:
                raise ValueError("exactly one Fine VIDEO stream required")
            resolution = recording.resolve_span(data.timeline_ref, data.requested_range, media_stream_ref=videos[0])
            context.checkpoint()
            # Only this invocation's confirmed Recording code is mapped. Input,
            # context, metadata reads, checkpoint and persistence stay outside.
            try:
                clip = recording.build_incident_clip(resolution)
            except RecordingCapabilityError as error:
                if error.code != "INCIDENT_CLIP_BUILD_FAILED":
                    raise
                result = HandlerResult(status="FAILED", failure_kind="RECORDING_INCIDENT_CLIP_BUILD_FAILED")
            else:
                # The payload points to immutable Recording media. The result
                # receipt belongs to this execution, even when a new job reuses it.
                result = HandlerResult(objects=(ProducedObject(kind="incident_clip_result",
                    payload={"incident_clip_ref": clip.incident_clip_ref}),))
            context.checkpoint()
        context.checkpoint()
        return result

    return KindRegistry({"INCIDENT_CLIP_BUILD": invoke})
