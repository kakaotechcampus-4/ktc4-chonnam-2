"""Contract §5.2 upload; receive/publish precede caller-owned registration."""
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from daesingo.case.domain import SourceNotAccepted
from daesingo.case.store import CaseNotFound, InvalidCaseId
from daesingo.recording import RecordingCapabilityError
from .upload import leased_source, _storage_call
from .errors import SourceHTTPException


def sources_router(composition):
    router = APIRouter()

    @router.post('/cases/{case_id}/sources')
    async def source(case_id: str, request: Request):
        try:
            async with leased_source(request, composition) as (path, filename):
                body = await _storage_call(composition.register_source, case_id, path, filename)
        except (CaseNotFound, InvalidCaseId):
            raise HTTPException(404) from None
        except SourceNotAccepted:
            raise SourceHTTPException(409) from None
        except RecordingCapabilityError as error:
            status = {'UNSUPPORTED_MEDIA': 422, 'TEMPORARY_FAILURE': 503}.get(error.code, 500)
            raise SourceHTTPException(status) from None
        request.state.case_id = body['case_id']
        return JSONResponse(body, status_code=201)
    return router
