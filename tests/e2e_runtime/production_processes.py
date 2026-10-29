"""Spawned acceptance peers; domain and transaction composition stays real."""
import io
import os
from dataclasses import replace
from types import MappingProxyType
from threading import Event
from unittest.mock import patch


def api_peer(pipe, env_file):
    from fastapi.testclient import TestClient
    from daesingo.api.bootstrap import bootstrap
    from daesingo.api.app import create_app
    os.environ["DAESINGO_ENV_FILE"] = env_file
    try:
        startup = bootstrap(revision="test", stream=io.StringIO())
        with TestClient(create_app(startup=startup)) as client:
            pipe.send({"ready": True, "pid": os.getpid()})
            while True:
                message = pipe.recv()
                if message[0] == "stop": break
                method, path, payload = message
                if method == "upload":
                    from pathlib import Path
                    source = Path(payload)
                    response = client.post(path, files={"file": ("20260620_141956_EVT_1" + source.suffix,
                        source.read_bytes(), "video/x-msvideo")})
                else:
                    response = client.request(method, path, json=payload) if payload is not None else client.request(method, path)
                pipe.send({"status": response.status_code, "body": response.json()})
    except BaseException:
        import traceback
        pipe.send({"error": traceback.format_exc()})
    finally: pipe.close()


def worker_peer(pipe, env_file, scenario, kind, interrupt_reflection=False):
    import httpx
    import openai
    from daesingo.worker.bootstrap import bootstrap
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.composition_root import compose_registry
    from daesingo.worker.case_composition import StoredCaseReflector
    from daesingo.common.db import create_worker_engine
    from daesingo.recording import RecordingService, LocalIncidentMaterializer
    os.environ["DAESINGO_ENV_FILE"] = env_file
    engine = None
    try:
        startup = bootstrap(revision="test", stream=io.StringIO())
        settings = startup.modules["search"]
        startup = replace(startup, modules=MappingProxyType({**startup.modules,
            "search": replace(settings, config=replace(settings.config, max_retries=0))}))
        engine = create_worker_engine(startup.config.db)
        calls = []
        readout_calls = []
        builds, encodes, exports = [], [], []
        original_build = RecordingService.build_incident_clip
        original_encode = LocalIncidentMaterializer.materialize
        def build(service, resolution, options=None):
            assert engine.pool.checkedout() == 0
            builds.append(True)
            return original_build(service, resolution, options)
        def encode(materializer, *args):
            assert engine.pool.checkedout() == 0
            encodes.append(True)
            return original_encode(materializer, *args)
        def respond(request):
            assert engine.pool.checkedout() == 0
            calls.append(request)
            if scenario == "failed" or scenario == "fine_failed" and kind == "FINE_VERIFY":
                return httpx.Response(500, json={"error": {"message": "offline failure"}})
            if kind == "HINT_EXTRACT":
                content = {"time_hint": None, "vehicle_hint": "white car", "situation_hint": "red signal",
                    "location_hint": None, "correction_target": None, "confidence": "high", "reasoning": "offline"}
            elif kind == "COARSE_SEARCH":
                fractional = scenario == "clip_fractional"
                candidates = [{"event_type": "SIGNAL", "span": {
                    "start_sec": 1 / 30 if fractional else .1, "end_sec": 20 / 30 if fractional else .8},
                    "at_sec": .5, "observed": ["red signal"], "score": .9}]
                if scenario == "partial":
                    candidates.append({"event_type": "SIGNAL", "span": {"start_sec": 8, "end_sec": 9},
                        "at_sec": 8.5, "observed": ["outside source"], "score": .5})
                content = {"candidates": candidates}
            else:
                content = {"verification": "OBSERVED" if scenario.startswith("clip") else "NOT_OBSERVED",
                    "visual_event_type": "SIGNAL" if scenario.startswith("clip") else None,
                    "target": {"association_status": "NOT_FOUND", "described_as": None,
                               "match_with_hint": None, "track_ref": None},
                    "primitives": [], "temporal_facts": [], "uncertainties": []}
            import json
            return httpx.Response(200, json={"id": "completion", "object": "chat.completion", "created": 0,
                "model": "offline", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}})
        original = openai.OpenAI
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            with patch.object(openai, "OpenAI", lambda **kw: original(http_client=client, **kw)), \
                 patch.object(RecordingService, "build_incident_clip", build), \
                 patch.object(LocalIncidentMaterializer, "materialize", encode):
                readout_factory = None
                if kind in {"PLATE_READ", "OVERLAY_TIME_READ"}:
                    from daesingo.worker.readout_composition import recording_ocr_factory
                    from daesingo.common.db.transactions import run_worker_transaction
                    from tests.worker.readout_support import OfflineOcr
                    from daesingo import readout
                    provider = OfflineOcr(scenario.removeprefix("clip_readout_"),
                        observe=lambda: (_ for _ in ()).throw(AssertionError("connection held"))
                            if engine.pool.checkedout() else None)
                    readout_factory = recording_ocr_factory(
                        transaction=lambda callback: run_worker_transaction(engine, callback),
                        storage_root=startup.config.media_root, ocr_factory=(lambda recording: __import__("tests.worker.export_support", fromlist=["ExportOcr"]).ExportOcr(recording))
                            if scenario.startswith("clip_export") else lambda recording: provider)
                    function = "read_plate" if kind == "PLATE_READ" else "read_overlay_time"
                    actual = getattr(readout, function)
                    def invoke_readout(request, **kw):
                        readout_calls.append((kind, request.input_ref.incident_clip_ref, kw["run_id"]))
                        return actual(request, **kw)
                    stack = __import__("contextlib").ExitStack()
                    stack.enter_context(patch.object(readout, function, invoke_readout))
                else:
                    stack = __import__("contextlib").ExitStack()
                for export_name in ("export_report_video", "export_plate_image"):
                    actual_export = getattr(RecordingService, export_name)
                    def export(service, _actual=actual_export, _name=export_name, **kw):
                        assert engine.pool.checkedout() == 0
                        exports.append(_name)
                        from sqlalchemy import event
                        def checkout(*args):
                            raise AssertionError("checkout inside export capability")
                        event.listen(engine, "checkout", checkout)
                        try: return _actual(service, **kw)
                        finally: event.remove(engine, "checkout", checkout)
                    stack.enter_context(patch.object(RecordingService, export_name, export))
                with stack:
                    registry = compose_registry(engine=engine, startup=startup, readout_provider_factory=readout_factory)
                    stop = Event()
                    terminals = []
                    def invoke(ctx):
                        assert ctx.kind == kind
                        result = registry.dispatch(ctx)
                        terminals.append({"status": result.status, "failure_kind": result.failure_kind})
                        stop.set()
                        return result
                    reflector = StoredCaseReflector(startup=startup)
                    if interrupt_reflection:
                        original_reflect = reflector.reflect
                        def rollback_t2(conn, incoming):
                            original_reflect(conn, incoming)
                            raise ValueError("offline interruption after Case reflection writes")
                        reflector.reflect = rollback_t2
                    loop = compose_worker(engine=engine, startup=startup, registry=type("Dispatch", (),
                        {"dispatch": staticmethod(invoke)})(), stop=stop, reflector=reflector)
                    loop.run()
        pipe.send({"pid": os.getpid(), "http_calls": len(calls), "pool_checkedout": engine.pool.checkedout(),
                   "terminals": terminals, "clip_calls": len(builds), "encodes": len(encodes), "readout_calls": readout_calls, "export_calls": exports, "registered_kinds": sorted(registry._handlers)})
    except BaseException:
        import traceback
        pipe.send({"error": traceback.format_exc()})
    finally:
        if engine is not None: engine.dispose()
        pipe.close()
