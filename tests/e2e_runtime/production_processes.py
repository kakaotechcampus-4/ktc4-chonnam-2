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


def worker_peer(pipe, env_file, scenario, kind):
    import httpx
    import openai
    from daesingo.worker.bootstrap import bootstrap
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.search_composition import compose_search_registry
    from daesingo.worker.case_composition import StoredCaseReflector
    from daesingo.common.db import create_worker_engine
    os.environ["DAESINGO_ENV_FILE"] = env_file
    engine = None
    try:
        startup = bootstrap(revision="test", stream=io.StringIO())
        settings = startup.modules["search"]
        startup = replace(startup, modules=MappingProxyType({**startup.modules,
            "search": replace(settings, config=replace(settings.config, max_retries=0))}))
        engine = create_worker_engine(startup.config.db)
        calls = []
        def respond(request):
            assert engine.pool.checkedout() == 0
            calls.append(request)
            if scenario == "failed" or scenario == "fine_failed" and kind == "FINE_VERIFY":
                return httpx.Response(500, json={"error": {"message": "offline failure"}})
            if kind == "HINT_EXTRACT":
                content = {"time_hint": None, "vehicle_hint": "white car", "situation_hint": "red signal",
                    "location_hint": None, "correction_target": None, "confidence": "high", "reasoning": "offline"}
            elif kind == "COARSE_SEARCH":
                candidates = [{"event_type": "SIGNAL", "span": {"start_sec": .1, "end_sec": .8},
                    "at_sec": .5, "observed": ["red signal"], "score": .9}]
                if scenario == "partial":
                    candidates.append({"event_type": "SIGNAL", "span": {"start_sec": 8, "end_sec": 9},
                        "at_sec": 8.5, "observed": ["outside source"], "score": .5})
                content = {"candidates": candidates}
            else:
                content = {"verification": "NOT_OBSERVED", "visual_event_type": None,
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
            with patch.object(openai, "OpenAI", lambda **kw: original(http_client=client, **kw)):
                registry = compose_search_registry(engine=engine, startup=startup)
                stop = Event()
                terminals = []
                def invoke(ctx):
                    assert ctx.kind == kind
                    result = registry.dispatch(ctx)
                    terminals.append({"status": result.status, "failure_kind": result.failure_kind})
                    stop.set()
                    return result
                loop = compose_worker(engine=engine, startup=startup, registry=type("Dispatch", (),
                    {"dispatch": staticmethod(invoke)})(), stop=stop, reflector=StoredCaseReflector(startup=startup))
                loop.run()
        pipe.send({"pid": os.getpid(), "http_calls": len(calls), "pool_checkedout": engine.pool.checkedout(),
                   "terminals": terminals})
    except BaseException:
        import traceback
        pipe.send({"error": traceback.format_exc()})
    finally:
        if engine is not None: engine.dispose()
        pipe.close()
