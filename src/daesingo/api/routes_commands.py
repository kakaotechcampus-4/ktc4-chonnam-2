"""HTTP Contract §5.3: bounded JSON transport and table-only response mapping."""
import json

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse


def _invalid_constant(value):
    raise ValueError("invalid JSON constant")


def commands_router(composition):
    router = APIRouter()

    @router.post("/cases/{case_id}/commands")
    async def command(case_id: str, request: Request):
        media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            raise HTTPException(415)
        limit = composition.startup.config.upload.json_max_bytes
        body = bytearray()
        async for chunk in request.stream():
            # Content-Length may be absent or false; bound actual received bytes.
            if len(body) + len(chunk) > limit:
                composition.readiness.events.emit("api.request.rejected_413_count", count=1)
                raise HTTPException(413)
            body.extend(chunk)
        try:
            payload = json.loads(body.decode("utf-8"), parse_constant=_invalid_constant)
        except (ValueError, RecursionError):
            raise HTTPException(400) from None
        if isinstance(payload, dict) and isinstance(payload.get("case_id"), str) and payload["case_id"] != case_id:
            raise HTTPException(400)
        # Case owns shape/kind/payload validation. No HTTP request schema copy.
        result = await run_in_threadpool(composition.execute_command, payload, request.state.trace_id)
        response = result.response
        view = response["case_view"]
        if view is not None:
            request.state.case_id = view["case_id"]
        if response["ok"]:
            status = 202 if result.appended_job_records else 200
        elif response["error"]["code"] == "case.command.invalid_payload":
            status = 422
        elif response["error"]["code"] == "case.command.unknown_target" and view is None:
            status = 404
        else:
            status = 409
        headers = {"Location": f"/cases/{case_id}/view"} if status == 202 else None
        return JSONResponse(response, status_code=status, headers=headers)

    return router
