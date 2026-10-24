"""HTTP Contract §3.3 envelope and §3.4 status mapping, without exception detail."""
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from daesingo.common.db.errors import BeforeCommitFailure, CommitOutcomeUnknown

_HTTP_CODES = {
    400: "http.malformed_request", 404: "http.not_found", 405: "http.method_not_allowed",
    413: "http.payload_too_large", 415: "http.unsupported_media_type",
    409: "http.source_not_allowed", 422: "http.source_rejected",
    500: "http.internal_error", 503: "http.dependency_unavailable",
}


class SourceHTTPException(HTTPException):
    """Source-only statuses must not change unrelated framework error mapping."""


class FrameUnavailable(HTTPException):
    def __init__(self):
        super().__init__(404)


class AssetUnavailable(HTTPException):
    def __init__(self):
        super().__init__(404)


def error_response(status: int, *, headers=None, ref_unavailable=False) -> JSONResponse:
    code = "http.ref_unavailable" if status == 404 and ref_unavailable else _HTTP_CODES[status]
    if status == 413:
        # The unconsumed request must not keep its connection alive after the
        # application stops receiving; do not drain an oversized upload.
        headers = dict(headers or {}, Connection='close')
    return JSONResponse({"ok": False, "error": {"code": code, "message_key": code},
                         "case_view": None}, status_code=status, headers=headers)


def install_error_handlers(app, events):
    def failure(status, *, headers=None, ref_unavailable=False):
        events.emit("api.request.failed", status=str(status))
        return error_response(status, headers=headers, ref_unavailable=ref_unavailable)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        status = error.status_code if error.status_code in _HTTP_CODES else 500
        if status in (409, 422) and not isinstance(error, SourceHTTPException):
            status = 500
        if status == 413 and getattr(request.scope.get('route'), 'path', None) == '/cases/{case_id}/sources':
            events.emit('api.upload.rejected_413_count', count=1)
        # Framework-generated Allow is protocol metadata; arbitrary exception
        # headers can contain internal details and are deliberately not echoed.
        headers = None
        if status == 405:
            route = request.scope.get("route")
            methods = getattr(route, "methods", None)
            if methods:
                headers = {"Allow": ", ".join(sorted(methods))}
        return failure(status, headers=headers, ref_unavailable=isinstance(error, (FrameUnavailable, AssetUnavailable)))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Transport conversion failures, never domain invalid_payload. Command
        # handlers in (c) pass opaque JSON through to Case's own validation.
        return failure(400)

    @app.exception_handler(BeforeCommitFailure)
    async def before_commit(request, error):
        return failure(503)

    @app.exception_handler(CommitOutcomeUnknown)
    async def unknown_commit(request, error):
        return failure(500)

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        return failure(500)
