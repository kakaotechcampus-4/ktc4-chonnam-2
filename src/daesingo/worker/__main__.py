"""Run a single Worker: python -m daesingo.worker."""

import logging
import os
import signal
from threading import Event

from daesingo.common.db import create_worker_engine
from daesingo.common.logging import log_event_best_effort
from daesingo.worker.bootstrap import bootstrap
from daesingo.recording.factory import RecordingSettings
from daesingo.worker.composition import compose_worker
from daesingo.worker.composition_root import compose_registry
from daesingo.worker.readout_composition import production_readout_factory
from daesingo.worker.case_composition import StoredCaseReflector, StoredCaseExhaustionReceiver


def _failure(logger, event):
    # The process boundary must remain safe even if the sink raises a fatal.
    # Never serialize the original exception or ask stdlib to print a traceback.
    try:
        log_event_best_effort(logger, event, level=logging.ERROR)
    except BaseException:
        pass


def main(*, readout_provider_factory=None) -> int:
    revision = os.environ.get("DAESINGO_REVISION", "unknown")
    startup = bootstrap(revision=revision)
    deployment = os.environ.get("DAESINGO_DEPLOYMENT_CHECK") == "1"
    stop = Event()
    engine = None
    previous = {}
    code = 0

    def request_stop(signum, frame):
        # Handler and T1 continue; only the next idle point sees this event.
        stop.set()

    try:
        if deployment:
            from daesingo.worker.deployment_status import clear
            clear()
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, request_stop)
        engine = create_worker_engine(startup.config.db)
        if readout_provider_factory is None:
            readout_provider_factory = production_readout_factory(engine=engine, startup=startup)
        # Native OCR initialization may replace OS signal handlers. Reassert the
        # Worker's graceful-stop ownership before any execution can be claimed.
        for sig in previous:
            signal.signal(sig, request_stop)
        registry = compose_registry(engine=engine, startup=startup,
                                    readout_provider_factory=readout_provider_factory)
        worker = compose_worker(engine=engine, startup=startup, registry=registry, stop=stop,
                       reflector=StoredCaseReflector(startup=startup),
                       exhaustion_receiver=StoredCaseExhaustionReceiver(startup=startup))
        if deployment:
            from daesingo.worker.deployment_status import publish
            settings = startup.modules["recording"]
            if not isinstance(settings, RecordingSettings):
                raise ValueError("deployment_recording_incomplete")
            if settings.profile is None or settings.analysis_limits is None or settings.incident_encoding is None:
                raise ValueError("deployment_recording_incomplete")
            publish(registry, revision)
        worker.run()
    except BaseException:
        stop.set()
        _failure(startup.logger, "runtime.worker.failed")
        code = 1
    finally:
        if deployment:
            try:
                from daesingo.worker.deployment_status import clear
                clear()
            except BaseException:
                _failure(startup.logger, "runtime.worker.cleanup_failed")
                code = 1
        try:
            if engine is not None:
                engine.dispose()
        except BaseException:
            _failure(startup.logger, "runtime.worker.cleanup_failed")
            code = 1
        finally:
            for sig, handler in previous.items():
                try:
                    signal.signal(sig, handler)
                except BaseException:
                    _failure(startup.logger, "runtime.worker.cleanup_failed")
                    code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
