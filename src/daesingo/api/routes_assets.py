"""Stored DerivedAsset downloads, HTTP Contract §3.5 and §5.6."""
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from daesingo.case.store import CaseNotFound, InvalidCaseId
from daesingo.recording import RecordingCapabilityError
from .errors import AssetUnavailable


# Match the formats supported by Recording's stored-content adapter. Never use
# an opaque ref, original filename or private locator in an attachment name.
_FILENAMES = {'video/mp4': 'daesingo_asset.mp4', 'image/png': 'daesingo_asset.png'}


def assets_router(composition):
    router = APIRouter()

    @router.get('/cases/{case_id}/assets/{asset_ref}')
    async def asset(case_id: str, asset_ref: str):
        try:
            content, content_type = await run_in_threadpool(composition.load_asset, case_id, asset_ref)
        except (CaseNotFound, InvalidCaseId):
            raise HTTPException(404) from None
        except RecordingCapabilityError as error:
            if error.code == 'UNAVAILABLE':
                raise AssetUnavailable() from None
            raise HTTPException({'UNKNOWN_REF': 404, 'INVALID_REF_KIND': 404,
                                 'TEMPORARY_FAILURE': 503}.get(error.code, 500)) from None
        # No stream/transaction/connection survives into header construction or
        # the Response's ASGI lifetime. Range does not change the stored body.
        filename = _FILENAMES[content_type]
        return Response(content, media_type=content_type, headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'private, no-store'})

    return router
