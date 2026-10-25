"""Stored FrameRef HTTP reads, per Issue #298 Owner-approved DB boundary."""
import asyncio
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from daesingo.case.store import CaseNotFound, InvalidCaseId
from daesingo.recording import RecordingCapabilityError
from .errors import FrameUnavailable


def frames_router(composition):
    router = APIRouter()
    settings = composition.startup.config.frame

    def completed(task):
        # A disconnected/cancelled request can leave the shielded read finishing.
        # Consume its exception without ever rendering the diagnostic text.
        if not task.cancelled():
            task.exception()

    @router.get('/cases/{case_id}/frames/{frame_ref}')
    async def frame(case_id: str, frame_ref: str, request: Request):
        task = asyncio.create_task(run_in_threadpool(composition.load_frame, case_id, frame_ref))
        request.state.frame_read_task = task
        task.add_done_callback(completed)
        try:
            image = await asyncio.shield(task)
        except (CaseNotFound, InvalidCaseId):
            raise HTTPException(404) from None
        except RecordingCapabilityError as error:
            if error.code in ('FRAME_NOT_FOUND', 'STREAM_UNAVAILABLE', 'OUT_OF_RANGE'):
                raise FrameUnavailable() from None
            raise HTTPException({'UNKNOWN_REF': 404, 'TEMPORARY_FAILURE': 503}.get(error.code, 500)) from None
        return Response(image.content, media_type=image.content_type,
                        headers={'Cache-Control': f'private, max-age={settings.max_age_sec}'})
    return router
