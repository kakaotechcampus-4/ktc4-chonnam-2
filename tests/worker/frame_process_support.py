"""Spawn targets for real DB/media/HTTP; Case frame helpers remain test-only."""
import os


def frame_worker_peer(pipe, env_file):
    from io import StringIO
    from threading import Event
    import sqlalchemy as sa
    from daesingo.common.db import create_worker_engine
    from daesingo.common.jobs.redelivery import redeliver_once
    from daesingo.common.jobs.schema import job_execution
    from daesingo.recording.frames import FfmpegFrameExtractor
    from daesingo.worker.bootstrap import bootstrap
    from daesingo.worker.case_composition import StoredCaseReflector
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.produced_reader import worker_produced_reader
    from daesingo.worker.registry import KindRegistry
    from incident_frame_support import test_registry
    os.environ["DAESINGO_ENV_FILE"] = env_file
    engine = None
    try:
        startup = bootstrap(revision="test", stream=StringIO())
        engine = create_worker_engine(startup.config.db)
        original, calls = FfmpegFrameExtractor.extract, []
        def extract(self, *args):
            assert engine.pool.checkedout() == 0
            calls.append(True)
            return original(self, *args)
        FfmpegFrameExtractor.extract = extract
        stop, registry = Event(), test_registry(engine, startup)
        def invoke(ctx):
            try: return registry.dispatch(ctx)
            finally: stop.set()
        reflector = StoredCaseReflector(storage_root=startup.config.media_root)
        compose_worker(engine=engine, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
            stop=stop, reflector=reflector).run()
        redeliver_once(engine, reflector, sleep=lambda seconds: None)
        with engine.begin() as conn:
            row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
            assert row["status"] == "SUCCEEDED" and row["case_applied_at"] is not None
            payload = worker_produced_reader()(conn, row["kind"], tuple(row["produced"]))
        pipe.send({"pid": os.getpid(), "decodes": len(calls), "payload": payload, "checkedout": engine.pool.checkedout()})
    except BaseException:
        import traceback
        pipe.send({"error": traceback.format_exc()})
    finally:
        if engine is not None: engine.dispose()
        pipe.close()


def frame_api_peer(pipe, env_file, case_id, frame_ref):
    from io import StringIO
    import hashlib
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap
    from daesingo.recording.frames import FfmpegFrameExtractor
    os.environ["DAESINGO_ENV_FILE"] = env_file
    try:
        # API/View/HTTP frame reads must use durable bytes, never decode.
        def forbidden(*args, **kwargs): raise AssertionError("HTTP decoded a frame")
        FfmpegFrameExtractor.extract = forbidden
        with TestClient(create_app(startup=bootstrap(revision="test", stream=StringIO()))) as client:
            response = client.get(f"/cases/{case_id}/frames/{frame_ref}")
            assert response.status_code == 200 and response.headers["content-type"] == "image/png"
            assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
            other = client.post("/cases").json()["case_id"]
            foreign = client.get(f"/cases/{other}/frames/{frame_ref}")
            exact = client.get(f"/cases/{case_id}%20/frames/{frame_ref}")
            view = client.get(f"/cases/{case_id}/view")
            assert view.status_code == 200
            pipe.send({"pid": os.getpid(), "sha256": hashlib.sha256(response.content).hexdigest(),
                "foreign": foreign.status_code, "exact": exact.status_code,
                "thumbs": [c["thumb_ref"] for c in view.json()["candidates"]]})
    except BaseException:
        import traceback
        pipe.send({"error": traceback.format_exc()})
    finally: pipe.close()
