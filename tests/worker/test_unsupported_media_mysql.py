"""Real production Search/Recording composition, T1/T2 and offline media rejection."""

from io import StringIO
from threading import Event
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from daesingo.case import service, command, get_view
from daesingo.case.timeline_source import RecordingSequentialTimelineSource
from daesingo.common.db import create_worker_engine
from daesingo.common.config import DbSettings, RuntimeConfig
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.schema import job_execution
from daesingo.common.jobs.produced import produced_objects
from daesingo.recording import RecordingService, RecordingCapabilityError
from daesingo.recording.factory import RecordingSettings
from daesingo.recording.materialization import LocalAnalysisMaterializer
from daesingo.recording.mysql_repository import MySQLRecordingRepository
from daesingo.search.config import GeminiSearchConfig
from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
from daesingo.worker.search_composition import compose_search_registry
from tests.recording.test_local_time_sources import make_media as _make_media
from tests.recording.test_factory_config import mapping
from test_worker_mysql import queue as _queue, composed, row
from test_search_handlers import fixtures
from mysql_fault_proxy import CommitResponseProxy

pytestmark = pytest.mark.mysql
queue = _queue
make_media = _make_media


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
@pytest.mark.parametrize(
    "fault", ["none", "t1_rollback", "t1_unknown", "t2_rollback", "t2_unknown", "gap"]
)
def test_production_unsupported_terminal_receipt_and_projection(
    queue, make_media, monkeypatch, tmp_path, kind, fault
):
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir()
    temp.mkdir()
    video = make_media("media/input.avi")
    with queue.begin() as conn:
        facade = stored_case_store(conn, storage_root=root)
        case_id = service.create_case(store=facade)
        with RecordingService(
            MySQLRecordingRepository(conn, storage_root=root)
        ) as recording:
            registered = recording.register_local_source(video, case_id=case_id)
            service.record_source_registered(
                case_id,
                registered.source_asset.model_dump(mode="json"),
                media_streams=[
                    s.model_dump(mode="json") for s in registered.media_streams
                ],
                store=facade,
            )
            issued = command.execute_command(
                {
                    "case_id": case_id,
                    "expected_case_rev": 1,
                    "kind": "START_ANALYSIS",
                    "payload": {"description": ""},
                },
                store=facade,
                timelines=RecordingSequentialTimelineSource(recording),
            )
            (coarse_id,) = enqueue(conn, issued.appended_job_records, "trace-offline")
    cfg = RuntimeConfig.from_mapping(
        "worker",
        {
            "DAESINGO_RUNTIME_DB_URL": queue.url.render_as_string(hide_password=False),
            "DAESINGO_RUNTIME_MEDIA_ROOT": str(root),
            "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp),
        },
    )
    startup = SimpleNamespace(
        config=cfg,
        modules={
            "recording": RecordingSettings.from_mapping(mapping()),
            "search": SimpleNamespace(
                api_key=SecretStr("offline-key"), config=GeminiSearchConfig()
            ),
        },
        logger=None,
    )
    calls, closes, dispatched = [], [], []
    reject = [kind == "COARSE_SEARCH"]
    original_materialize, original_close = (
        LocalAnalysisMaterializer.materialize,
        RecordingService.close,
    )

    def materialize(*args):
        calls.append("media")
        assert active.pool.checkedout() == 0
        if reject[0]:
            raise RecordingCapabilityError(
                "UNSUPPORTED_MEDIA", "private filename /path locator content"
            )
        return original_materialize(*args)

    def close(self):
        original_close(self)
        closes.append(True)

    monkeypatch.setattr(LocalAnalysisMaterializer, "materialize", materialize)
    monkeypatch.setattr(RecordingService, "close", close)
    _, coarse, _ = fixtures()

    def build(key, resolver, config):
        def search_candidates(scope, **kwargs):
            calls.append("coarse_search")
            span = scope.time_ranges[0]
            candidate = coarse.candidates[0].model_copy(
                update={
                    "span": coarse.candidates[0].span.model_copy(
                        update={
                            "timeline_id": span.timeline_ref.timeline_id,
                            "timeline_revision": span.timeline_ref.revision,
                            "start_ms": 100,
                            "end_ms": 800,
                            "representative_ms": 400,
                        }
                    )
                }
            )
            return coarse.model_copy(update={"candidates": (candidate,)})

        return SimpleNamespace(
            resolver=resolver,
            search_candidates=search_candidates,
            verify_visual=lambda *a, **k: pytest.fail("Fine Search after rejection"),
        )

    monkeypatch.setattr("daesingo.search.build_gemini_search_service", build)
    reflector = StoredCaseReflector(storage_root=root)
    stream = StringIO()

    def once(engine, expected, reflection=reflector):
        registry = compose_search_registry(engine=engine, startup=startup)
        stop = Event()

        def invoke(ctx):
            dispatched.append(ctx.execution_id)
            assert ctx.kind == expected
            result = registry.dispatch(ctx)
            stop.set()
            return result

        loop = composed(
            engine, {expected: invoke}, stop=stop, reflector=reflection, stream=stream
        )
        if fault == "gap" and reject[0]:
            loop.reflect = lambda *a: None
        loop.run()

    active = queue
    if kind == "FINE_VERIFY":
        once(queue, "COARSE_SEARCH")
        reject[0] = True
    before_calls = list(calls)
    before_closes = len(closes)
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        extra = None
        if fault.endswith("unknown"):
            extra = active = create_worker_engine(
                DbSettings(
                    url=queue.url.set(host="127.0.0.1", port=proxy.port)
                    .update_query_dict({"ssl_disabled": "true"})
                    .render_as_string(hide_password=False)
                )
            )
        injected = []

        def inject(conn, cursor, sql, *args):
            target = (
                "UPDATE JOB_EXECUTION SET STATUS="
                if fault.startswith("t1_")
                else "UPDATE JOB_EXECUTION SET CASE_APPLIED_AT"
            )
            if (
                fault not in {"none", "gap"}
                and not injected
                and sql.upper().startswith(target)
            ):
                injected.append(True)
                if fault.endswith("rollback"):
                    raise sa.exc.OperationalError(
                        "injected", {}, Exception(1213, "deadlock")
                    )
                proxy.arm()

        sa.event.listen(active, "after_cursor_execute", inject)
        try:
            once(active, kind)
            if fault == "gap":
                failed_id = dispatched[-1]
                assert row(queue, failed_id)["case_applied_at"] is None
                redeliver_once(active, reflector, sleep=lambda _: None)
            assert bool(injected) == (fault not in {"none", "gap"})
            assert proxy.commit_ok_dropped == int(fault.endswith("unknown"))
        finally:
            sa.event.remove(active, "after_cursor_execute", inject)
            if extra is not None:
                extra.dispose()
    failed_id = dispatched[-1]
    terminal = row(queue, failed_id)
    assert (
        terminal["status"] == "FAILED"
        and terminal["failure_kind"] == "RECORDING_UNSUPPORTED_MEDIA"
    )
    assert terminal["produced"] == [] and terminal["case_applied_at"] is not None
    assert calls == before_calls + ["media"] and len(closes) > before_closes
    assert not queue.pool.checkedout()
    with queue.begin() as conn:
        facade = stored_case_store(conn, storage_root=root)
        case = facade.get_case(case_id)
        view = get_view(case_id, store=facade)
        assert case.processed_executions[failed_id] == terminal["job_id"]
        assert not view["running_jobs"]
        if kind == "COARSE_SEARCH":
            assert (
                next(
                    p["state"] for p in view["progress"] if p["step"] == "coarse_search"
                )
                == "FAILED"
            )
            assert case.candidate_search_failed and case.stage == "SEARCHING"
            assert not view["candidates"]
            (notice,) = [
                n
                for n in view["notices"]
                if n["code"] == "search.candidate_search_failed"
            ]
            assert notice["actions"] == ["RETRY_SEARCH"]
        else:
            assert case.observation_outcomes[terminal["job_id"]]["status"] == "FAILED"
            assert len(view["candidates"]) == 1
            (notice,) = [
                n for n in view["notices"] if n["code"] == "search.visual_verify_failed"
            ]
            assert notice["actions"] == [] and notice["blocking"]
            # Existing Case policy omits unstarted downstream steps after Fine
            # failure; it exposes failure through the notice, not a Fine step.
            assert view["progress"] == [
                {"step": s, "state": "DONE"}
                for s in ("file_intake", "coarse_search", "candidate_review")
            ]
        assert (
            conn.scalar(
                sa.select(sa.func.count())
                .select_from(produced_objects)
                .where(produced_objects.c.execution_id == failed_id)
            )
            == 0
        )
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == (
            1 if kind == "COARSE_SEARCH" else 2
        )
        state = case.processed_executions.copy()
    receipt = terminal["case_applied_at"]
    count_calls = list(calls)
    assert redeliver_once(queue, reflector, sleep=lambda _: None) == ()
    # A restarted idle Worker must also leave paid/media work untouched.
    composed(
        queue, {kind: lambda _: pytest.fail("replayed handler")}, reflector=reflector
    ).run()
    assert calls == count_calls and row(queue, failed_id)["case_applied_at"] == receipt
    with queue.begin() as conn:
        loaded = stored_case_store(conn, storage_root=root).get_case(case_id)
        assert loaded.processed_executions == state
    assert not queue.pool.checkedout()
    assert not list(temp.glob("recording-*/**/*"))
    assert not any(
        word in stream.getvalue()
        for word in ("private", "filename", "locator", "offline-key")
    )
