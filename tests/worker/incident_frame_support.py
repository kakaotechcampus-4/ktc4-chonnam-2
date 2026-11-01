"""TEST ONLY: stand-ins for the unmerged Case position/Top-3 interface.

Never imported by src or used to claim Case integration. Real Recording, DB,
Worker and HTTP are retained in acceptance tests using this seam.
"""


def selected_thumbnail(case, source, events):
    return [source["candidate_id"]]


def preview_position(clip, span, representative_ms):
    if representative_ms is None:
        return None
    # Test oracle only. The production implementation belongs to Case #470.
    if clip["timeline_ref"] != {"timeline_id": span["timeline_id"], "revision": span["timeline_revision"]}:
        return None
    at = representative_ms / 1000
    if not clip["timeline_range"]["start_sec"] <= at < clip["timeline_range"]["end_sec"]:
        return None
    return unique_position(clip["source_provenance"]["asset_spans"], at)


def candidate_position(resolution, span, representative_ms):
    if representative_ms is None or resolution["status"] == "FAILED":
        return None
    if resolution["timeline_ref"] != {"timeline_id": span["timeline_id"], "revision": span["timeline_revision"]}:
        return None
    return unique_position(resolution["spans"], representative_ms / 1000)


def unique_position(spans, at):
    matches = [s for s in spans if s["timeline_range"]["start_sec"] <= at < s["timeline_range"]["end_sec"]]
    if len(matches) != 1:
        return None
    item = matches[0]
    return item["media_stream_ref"], item["source_range"]["start_sec"] + at - item["timeline_range"]["start_sec"]


def test_registry(engine, startup, *, frames=None):
    from daesingo.common.db.transactions import run_worker_transaction
    from daesingo.worker.case_composition import stored_case_store
    from daesingo.worker.incident_clip_inputs import IncidentClipInputs
    from daesingo.worker.incident_clip_composition import IncidentRecordingFactory
    from daesingo.worker.incident_clip_handlers import incident_clip_registry
    from daesingo.worker.incident_frames import IncidentFrameIssuer
    def transaction(callback):
        return run_worker_transaction(engine, callback, logger=startup.logger)
    inputs = IncidentClipInputs(transaction=transaction,
        store_factory=lambda conn: stored_case_store(conn, storage_root=startup.config.media_root),
        thumbnail_candidates=selected_thumbnail)
    factory = IncidentRecordingFactory(transaction=transaction, storage_root=startup.config.media_root,
        temp_root=startup.config.temp_root, settings=startup.modules["recording"])
    return incident_clip_registry(load=inputs, service_factory=factory,
        frames=frames if frames is not None else IncidentFrameIssuer(
            preview_position=preview_position, candidate_position=candidate_position))
