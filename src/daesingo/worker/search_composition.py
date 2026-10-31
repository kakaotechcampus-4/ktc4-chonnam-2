"""Production Search wiring; media capability stays an explicit dependency."""

from daesingo.common.db.transactions import run_worker_transaction
from daesingo.search import build_intent_hint_extractor
from daesingo.worker.search_handlers import search_registry
from daesingo.worker.search_inputs import SearchInputs
from daesingo.worker.case_composition import stored_case_store
from daesingo.worker.production_media import ProductionMediaFactory
from daesingo.common.storage.cleanup import configured_cleanup
from daesingo.common.storage.media import MediaRoot
from daesingo.case.search_progress import record_search_progress
from daesingo.common.logging import log_event_best_effort


def compose_search_registry(*, engine, startup, service_factory=None, failures=None):
    def transaction(callback):
        return run_worker_transaction(engine, callback, logger=startup.logger)

    inputs = SearchInputs(transaction=transaction,
        store_factory=lambda conn: stored_case_store(conn, storage_root=startup.config.media_root))
    modules = getattr(startup, "modules", {})
    recording = modules.get("recording")
    if service_factory is None and recording is not None and recording.profile_ref is not None:
        cleanup = configured_cleanup(startup.config, startup.logger)
        media = MediaRoot(next(s for s in cleanup.scanners if s.kind == "temp"))
        service_factory = ProductionMediaFactory(transaction=transaction,
            storage_root=startup.config.media_root, temp_root=startup.config.temp_root,
            settings=recording, search_settings=modules["search"], media=media)

    def intent():
        settings = startup.modules["search"]
        return build_intent_hint_extractor(settings.api_key.get_secret_value(), startup.modules["intent"])

    def report_progress(context, phase):
        # Display updates must never turn a successful analysis into a failed job.
        if context.ownership.lost:
            return
        try:
            transaction(lambda conn: record_search_progress(
                stored_case_store(conn, storage_root=startup.config.media_root),
                context.case_id, context.job_id, phase, execution_id=context.execution_id))
        except Exception:
            log_event_best_effort(startup.logger, "search.progress_unavailable")

    return search_registry(load=inputs, intent_factory=intent, service_factory=service_factory,
                           failures=failures, report_progress=report_progress)
