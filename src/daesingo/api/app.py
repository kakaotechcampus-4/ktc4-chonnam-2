"""HTTP application factory: startup validation, composition, envelope, health."""
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI
from starlette.responses import JSONResponse
from daesingo.common.bootstrap import Startup
from daesingo.common.logging import bind_context, new_trace_id, safe_correlation
from .bootstrap import bootstrap
from .composition import compose_api
from .errors import error_response, install_error_handlers
from .events import ApiEvents
from .routes_cases import cases_router
from .routes_view import view_router
from .routes_commands import commands_router


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
            yield
        finally:
            composition.close()
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False, debug=False)
    app.state.composition = composition
    install_error_handlers(app, composition.readiness.events)
    app.include_router(cases_router(composition))
    app.include_router(view_router(composition))
    app.include_router(commands_router(composition))

    @app.middleware("http")
    async def access(request, call_next):
        started = monotonic()
        request.state.trace_id = new_trace_id()
        with bind_context(trace_id=request.state.trace_id, module="api"):
            try:
                response = await call_next(request)
            except Exception:
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
    return app
