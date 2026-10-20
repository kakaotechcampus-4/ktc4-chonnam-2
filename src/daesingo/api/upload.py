"""Bounded streaming multipart reception into the shared mount, without DB I/O."""
import asyncio
from email.message import Message
import logging
import os
from pathlib import Path
import tempfile
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.requests import ClientDisconnect

from .errors import error_response


class UploadAborted(Exception):
    """Trusted internal unwinding signal; no request data or diagnostic text."""


class NoUploadResponse:
    async def __call__(self, scope, receive, send):
        # The transport is already closed (or the client disconnected).
        return


def _source_request(scope):
    parts = scope.get('path', '').split('/')
    return (scope['type'] == 'http' and scope.get('method') == 'POST'
            and len(parts) == 4 and parts[1] == 'cases' and bool(parts[2]) and parts[3] == 'sources')


class SourceBodyLimitMiddleware:
    def __init__(self, app, composition):
        self.app, self.composition = app, composition

    async def __call__(self, scope, receive, send):
        if not _source_request(scope):
            return await self.app(scope, receive, send)
        limit = self.composition.startup.config.upload.max_bytes
        # Starlette's early response override is plain text. Handle this early
        # rejection here so every 413 retains the Contract envelope.
        headers = dict(scope['headers'])
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = 0
        if declared > limit:
            self.composition.readiness.events.emit('api.upload.rejected_413_count', count=1)
            self.composition.readiness.events.emit('api.request.failed', status='413')
            return await error_response(413)(scope, receive, send)
        # Enforce actual bytes, including multipart overhead and absent/lying CL.
        await RequestBodyLimitMiddleware(self.app, max_body_size=limit)(scope, receive, send)


def _text(value):
    try:
        return value.decode('utf-8')
    except UnicodeDecodeError:
        return value.decode('latin-1')


class _MultipartFile:
    def __init__(self, content_type, target):
        _, options = parse_options_header(content_type)
        boundary = options.get(b'boundary')
        if not boundary:
            raise HTTPException(400)
        self.target = target
        self.parts = 0
        self.filename = None
        self.finished = False
        self.header_name = bytearray()
        self.header_value = bytearray()
        self.disposition = None
        callbacks = {name: getattr(self, name) for name in (
            'on_part_begin', 'on_header_field', 'on_header_value', 'on_header_end',
            'on_headers_finished', 'on_part_data', 'on_end')}
        try:
            self.parser = MultipartParser(boundary, callbacks)
        except (ValueError, MultipartParseError):
            raise HTTPException(400) from None
        # Third-party diagnostic wording is never part of API logging. Avoid
        # changing any shared logger/handler and suppress its lastResort output.
        self.parser.logger = logging.Logger('api.multipart.silent')
        self.parser.logger.addHandler(logging.NullHandler())
        self.parser.logger.propagate = False

    def on_part_begin(self):
        self.parts += 1
        if self.parts != 1:
            raise HTTPException(400)

    def on_header_field(self, data, start, end):
        self.header_name.extend(data[start:end])

    def on_header_value(self, data, start, end):
        self.header_value.extend(data[start:end])

    def on_header_end(self):
        if self.header_name.lower() == b'content-disposition':
            if self.disposition is not None:
                raise HTTPException(400)
            self.disposition = bytes(self.header_value)
        self.header_name.clear()
        self.header_value.clear()

    def on_headers_finished(self):
        # Multipart's convenience File/options APIs strip Windows path prefixes.
        # Use MIME quoted-string decoding only; filename remains opaque metadata.
        message = Message()
        message['content-disposition'] = (self.disposition or b'').decode('latin-1')
        params = message.get_params(header='content-disposition', unquote=True) or []
        values = {}
        for key, value in params[1:]:
            if key in values:
                raise HTTPException(400)
            values[key] = value
        filename = values.get('filename')
        if (not params or params[0][0].lower() != 'form-data' or values.get('name') != 'file'
                or not isinstance(filename, str) or filename == ''):
            raise HTTPException(400)
        self.filename = _text(filename.encode('latin-1'))

    def on_part_data(self, data, start, end):
        self.target.write(memoryview(data)[start:end])

    def on_end(self):
        self.finished = True

    def write(self, chunk):
        try:
            self.parser.write(chunk)
        except MultipartParseError:
            raise HTTPException(400) from None

    def finish(self):
        self.parser.finalize()
        if self.parts != 1 or self.filename is None or not self.finished:
            raise HTTPException(400)
        self.target.flush()
        os.fsync(self.target.fileno())


def _open_staging(root):
    staging = root / 'staging'
    final = root / 'source'
    staging.mkdir(exist_ok=True)
    final.mkdir(exist_ok=True)
    return tempfile.NamedTemporaryFile(mode='w+b', prefix='upload-', dir=staging, delete=False)


def publish(staging: Path, root: Path) -> Path:
    final = root / 'source' / uuid4().hex
    if staging.stat().st_dev != final.parent.stat().st_dev:
        raise OSError('upload storage device mismatch')
    os.replace(staging, final)
    # POSIX rename is atomic but the directory entry needs its own durability
    # barrier before rows may commit. Windows has no directory fsync primitive.
    if os.name != 'nt':
        for directory in (final.parent, staging.parent, root):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    return final


async def receive_source(request, composition):
    content_type = request.headers.get('content-type', '')
    if content_type.split(';', 1)[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(415)
    settings = composition.startup.config.upload
    root = composition.startup.config.media_root
    target = None
    started, last_byte = monotonic(), monotonic()
    total_bytes = 0
    try:
        target = await run_in_threadpool(_open_staging, root)
        parser = _MultipartFile(content_type, target)
        stream = request.stream().__aiter__()
        while True:
            now = monotonic()
            idle = settings.idle_timeout_sec - (now-last_byte)
            total = settings.max_duration_sec - (now-started)
            reason = 'duration' if total <= idle else 'idle'
            try:
                if min(idle, total) <= 0:
                    raise TimeoutError
                chunk = await asyncio.wait_for(anext(stream), timeout=min(idle, total))
            except StopAsyncIteration:
                break
            except TimeoutError:
                _abort(request, reason)
            except ClientDisconnect:
                _abort(request, 'disconnect')
            # Empty ASGI messages must not refresh the idle byte clock.
            if chunk:
                last_byte = monotonic()
                total_bytes += len(chunk)
                await run_in_threadpool(parser.write, chunk)
        await run_in_threadpool(parser.finish)
        path = Path(target.name)
        await run_in_threadpool(target.close)
        target = None
        final = await run_in_threadpool(publish, path, root)
        events = composition.readiness.events
        events.emit('api.upload.bytes', count=total_bytes)
        events.emit('api.upload.duration_ms', duration_ms=(monotonic()-started)*1000)
        return final, parser.filename
    except OSError:
        raise HTTPException(503) from None
    finally:
        if target is not None:
            # No open descriptor survives abort; a rowless named staging file
            # may remain per B-C1. Cleanup policy belongs to RT-12.
            target.close()


def _abort(request, reason):
    request.state.upload_aborted = reason
    if reason != 'disconnect':
        close = request.scope.get('extensions', {}).get('daesingo.close')
        if close is None:
            # Only the supported server entrypoint supplies no-status abort.
            raise RuntimeError('upload transport close capability required') from None
        close()
    raise UploadAborted() from None
