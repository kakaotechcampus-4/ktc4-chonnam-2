"""HTTP application factory: startup validation, composition, envelope, health."""
from contextlib import asynccontextmanager
import sys
from time import monotonic

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from daesingo.common.bootstrap import Startup
from daesingo.common.logging import bind_context, new_trace_id, safe_correlation
from .bootstrap import bootstrap
from .composition import compose_api
from .errors import error_response, install_error_handlers
from .events import ApiEvents
from .routes_cases import cases_router
from .routes_view import view_router
from .routes_commands import commands_router
from .routes_sources import sources_router
from .routes_frames import frames_router
from .routes_assets import assets_router
from .frame_lifetime import FrameLifetimeMiddleware
from .asset_lifetime import AssetLifetimeMiddleware
from .upload import NoUploadResponse, SourceBodyLimitMiddleware


def create_app(*, revision: str | None = None, startup: Startup | None = None) -> FastAPI:
    if startup is None:
        if revision is None:
            raise ValueError("revision is required for bootstrap")
        startup = bootstrap(revision=revision)
    try:
        composition = compose_api(startup)
    except Exception:
        events = ApiEvents(startup.logger)
        try:
            events.emit("api.composition.failed", status="INVALID")
            # Startup already failed. Keep the diagnostic opportunity without
            # spending the normal shutdown drain budget on a stalled sink.
            events.close(drain=False)
        except BaseException:
            # The established startup failure outranks even fatal diagnostics.
            # No synchronous sink call may postpone exit or disclose input.
            pass
        raise SystemExit(1) from None
    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(composition.cleanup.start)
            yield
        finally:
            primary = sys.exc_info()[1]
            try:
                composition.close()
            except BaseException:
                if primary is None:
                    raise
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False, debug=False)
    app.state.composition = composition
    install_error_handlers(app, composition.readiness.events)
    app.include_router(cases_router(composition))
    app.include_router(view_router(composition))
    app.include_router(commands_router(composition))
    app.include_router(sources_router(composition))
    app.include_router(frames_router(composition))
    app.include_router(assets_router(composition))
    # Keep the byte-limit receiver inside the access receive proxy: exceptions
    # then reach the normal HTTP handler without an AnyIO ExceptionGroup wrapper.
    app.add_middleware(SourceBodyLimitMiddleware, composition=composition)

    @app.middleware("http")
    async def access(request, call_next):
        started = monotonic()
        request.state.trace_id = (getattr(request.state, 'frame_trace_id', None)
                                  or getattr(request.state, 'asset_trace_id', None) or new_trace_id())
        with bind_context(trace_id=request.state.trace_id, module="api"):
            try:
                response = await call_next(request)
            except Exception:
                reason = getattr(request.state, 'upload_aborted', None)
                if reason in ('idle', 'duration', 'disconnect'):
                    composition.readiness.events.emit('api.upload.aborted_count', status=reason, count=1)
                    return NoUploadResponse()
                # Catch inside correlation scope; ServerErrorMiddleware would
                # otherwise log after context reset and return an unsafe default.
                composition.readiness.events.emit("api.request.failed", status="500")
                response = error_response(500)
            # Only a Case-returned identity is trusted; never log raw path IDs.
            case_id = getattr(request.state, "case_id", None)
            correlation = safe_correlation(case_id=case_id) if case_id is not None else {}
            composition.readiness.events.emit("api.request.completed", **correlation,
                                 status=str(response.status_code), duration_ms=(monotonic() - started) * 1000)
            return response

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        available = composition.readiness.check()
        return JSONResponse({"status": "ok" if available else "unavailable"},
                            status_code=200 if available else 503)
    # This must surround access/BaseHTTPMiddleware's real outer body send.
    app.add_middleware(FrameLifetimeMiddleware, composition=composition)
    app.add_middleware(AssetLifetimeMiddleware, composition=composition)
    return app
