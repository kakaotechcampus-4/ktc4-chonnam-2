"""Actual Case -> Search -> T1 payload/usage -> T2, with offline provider I/O."""

from contextlib import contextmanager
from dataclasses import replace
from io import StringIO
from threading import Event
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from daesingo.case import observation
from daesingo.case.stored_observation import stored_adapter_factory
from daesingo.common.config import DbSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.jobs.produced import ProducedReader, produced_objects
from daesingo.search import SearchService
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.intent import IntentHintExtraction
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver
from daesingo.search.runs import ContractRef
from daesingo.worker.case_reflector import CaseReflector
from daesingo.worker.search_composition import compose_search_registry
from tests.search._search_service_support import OpenableResolver
from tests.search.test_usage_sink import _Completions, _provider, _media
from mysql_fault_proxy import CommitResponseProxy
from redelivery_support import seed, store, Timelines, snapshot
from test_worker_mysql import queue, composed, row  # noqa: F401
from usage_sink_support import rows
from search_failure_support import SuccessfulSearchPolicy

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("fault", ["none", "rollback", "commit_unknown"])
@pytest.mark.mysql_check("search_handlers", "case_t1_t2")
def test_real_search_chain_usage_and_payload_survive_t1_replay(queue, monkeypatch, tmp_path, fault):
    case_id, hint_id = seed(queue, description="private description", terminal=False)
    hint = IntentHintExtraction(time_hint=None, vehicle_hint="흰 차", situation_hint=None, location_hint=None,
        correction_target=None, confidence="high", reasoning="private response")
    coarse = CoarseResponse.model_validate({"candidates": [{"event_type": "SIGNAL", "span": {"start_sec": 1, "end_sec": 3},
        "at_sec": 2, "observed": ["red signal"], "score": .9}]})
    fine = FineResponse.model_validate({"verification": "NOT_OBSERVED", "visual_event_type": None,
        "target": {"association_status": "NOT_FOUND", "described_as": None, "match_with_hint": None, "track_ref": None},
        "primitives": [], "temporal_facts": [], "uncertainties": []})
    calls = _Completions([hint, coarse, fine])
    provider = _provider(monkeypatch, calls)
    config = GeminiSearchConfig(max_retries=0)
    stream = StringIO()
    startup = SimpleNamespace(config=SimpleNamespace(media_root=tmp_path),
        modules={"search": SimpleNamespace(api_key=SecretStr("test")), "intent": config}, logger=None)

    class Media:
        @contextmanager
        def prepare_coarse(self, media, deadline):
            yield replace(_media(tmp_path), duration_sec=10.0, origin_end_sec=10.0)
        @contextmanager
        def prepare_fine(self, media, start, end, deadline): yield _media(tmp_path)

    @contextmanager
    def service(data):
        assert active.pool.checkedout() == 0
        ref = data.scope.time_ranges[0].timeline_ref
        source = ResolvedAnalysisSource(ContractRef(kind="analysis_source", ref="source"), 10, ref.timeline_id, ref.revision)
        resolver = OpenableResolver(StaticAnalysisSourceResolver({data.scope.scope_id: (source,)}, {source.source_id: source}))
        yield SearchService(resolver, provider, config, Media())
        assert active.pool.checkedout() == 0

    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        active = queue
        extra = None
        if fault == "commit_unknown":
            extra = active = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
                .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
        injected = []
        def after_write(conn, cursor, sql, *args):
            if not injected and sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"):
                injected.append(True)
                if fault == "rollback":
                    raise sa.exc.OperationalError("injected", {}, Exception(1213, "deadlock"))
                if fault == "commit_unknown": proxy.arm()
        sa.event.listen(active, "after_cursor_execute", after_write)
        try:
            registry = compose_search_registry(engine=active, startup=startup, service_factory=service,
                                                failures=SuccessfulSearchPolicy())
            def stored(conn):
                facade = store(conn)
                # NOT_OBSERVED must finish without any Recording fact read.
                facade.adapter_factory = stored_adapter_factory(reader=ProducedReader(),
                    executions=facade.executions, recording=object())
                return facade
            reflector = CaseReflector(reader=ProducedReader(), timelines=Timelines(), store_factory=stored)
            def once(kind):
                stop = Event()
                def invoke(ctx):
                    assert ctx.kind == kind
                    result = registry.dispatch(ctx)
                    stop.set()
                    return result
                composed(active, {kind: invoke}, stop=stop, reflector=reflector, stream=stream).run()
            once("HINT_EXTRACT")
            assert row(queue, hint_id)["case_applied_at"] is not None
            once("COARSE_SEARCH")
            with active.begin() as conn:
                facade = store(conn)
                case = facade.load_for_update(case_id)
                case.select_candidate(case.candidates[0].candidate_id)
                job = observation.issue_fine_for_selected(case)
                facade.save(case)
                from daesingo.common.jobs.repository import enqueue
                enqueue(conn, [job], "trace")
            once("FINE_VERIFY")
            assert calls.calls == 3  # T1 retry never repeats paid work
            assert proxy.commit_ok_dropped == (1 if fault == "commit_unknown" else 0)
        finally:
            sa.event.remove(active, "after_cursor_execute", after_write)
            if extra is not None: extra.dispose()
    trackers, finals = rows(queue)
    assert len(trackers) == len(finals) == 3
    assert len({f["usage_id"] for f in finals}) == len({f["execution_ref"] for f in finals}) == 3
    assert sorted(f["run_ref_reason"] or "RUN" for f in finals) == ["DIRECT_NO_RUN", "RUN", "RUN"]
    assert all(f["amount"] is None and f["currency"] == "KRW" for f in finals)
    with queue.connect() as conn:
        objects = list(conn.execute(sa.select(produced_objects)).mappings())
    assert len(objects) == 3 and len(snapshot(queue, case_id).processed_executions) == 3
    assert not any(word in stream.getvalue() for word in ("private", "reasoning", "claim_token", "usage_id"))
