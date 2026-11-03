import re

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from daesingo.case.store import CaseNotFound, InvalidCaseId
from daesingo.recording import RecordingCapabilityError
from .errors import AssetUnavailable


def _offset(value: str, size: int) -> int:
    normalized = value.lstrip('0') or '0'
    return size if len(normalized) > len(str(size)) else min(int(normalized), size)


def video_response(content: bytes, range_header: str | None) -> Response:
    size = len(content)
    headers = {'Content-Disposition': 'inline', 'Cache-Control': 'private, no-store', 'Accept-Ranges': 'bytes'}
    matched = re.fullmatch(r'bytes=([0-9]*)-([0-9]*)', range_header.strip()) if range_header else None
    if matched is None or matched.groups() == ('', ''):
        return Response(content, media_type='video/mp4', headers=headers)
    first, last = matched.groups()
    if first:
        start = _offset(first, size)
        end = min(_offset(last, size), size - 1) if last else size - 1
    else:
        suffix = _offset(last, size)
        start, end = size - suffix, size - 1
    if start >= size or start > end:
        return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{size}'})
    headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    return Response(content[start:end + 1], status_code=206, media_type='video/mp4', headers=headers)


def candidate_videos_router(composition) -> APIRouter:
    router = APIRouter()

    @router.get('/cases/{case_id}/candidate-videos/{clip_ref}')
    async def video(case_id: str, clip_ref: str, request: Request) -> Response:
        try:
            content, content_type = await run_in_threadpool(composition.load_candidate_video, case_id, clip_ref)
        except (CaseNotFound, InvalidCaseId):
            raise HTTPException(404) from None
        except RecordingCapabilityError as error:
            if error.code == 'UNAVAILABLE':
                raise AssetUnavailable() from None
            raise HTTPException({'UNKNOWN_REF': 404, 'INVALID_REF_KIND': 404,
                                 'TEMPORARY_FAILURE': 503}.get(error.code, 500)) from None
        if content_type != 'video/mp4' or not content:
            raise RuntimeError('invalid stored candidate video')
        return video_response(content, None if 'if-range' in request.headers else request.headers.get('range'))

    return router
