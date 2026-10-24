"""Asset observations at the outer ASGI send boundary (Issue #298 Owner)."""
import asyncio
import re
from time import monotonic

from daesingo.common.logging import bind_context, new_trace_id


class AssetLifetimeMiddleware:
    def __init__(self, app, *, composition):
        self.app = app
        self.events = composition.readiness.events

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        root = scope.get('root_path', '')
        if root and path.startswith(root + '/'):
            path = path[len(root):]
        if (scope['type'] != 'http' or scope['method'] != 'GET'
                or re.fullmatch(r'/cases/[^/]+/assets/[^/]+', path) is None):
            return await self.app(scope, receive, send)

        state = scope.setdefault('state', {})
        state['asset_trace_id'] = new_trace_id()
        started = monotonic()
        status, count, finished = 'CANCELLED', 0, None

        async def transmit(message):
            nonlocal status, count, finished
            if message['type'] == 'http.response.start':
                status = str(message['status'])
            await send(message)
            if message['type'] == 'http.response.body':
                # Successfully returned downstream send bytes, not
                # client-received bytes. Never include a failed send's chunk.
                count += len(message.get('body', b''))
                if not message.get('more_body', False):
                    finished = monotonic()

        with bind_context(trace_id=state['asset_trace_id'], module='api'):
            try:
                await self.app(scope, receive, transmit)
                if finished is None:
                    status = 'CANCELLED'
            except asyncio.CancelledError:
                status, finished = 'CANCELLED', None
                raise
            except BaseException:
                status, finished = 'FAILED', None
                raise
            finally:
                ended = monotonic() if finished is None else finished
                self.events.emit('api.asset.download_latency_ms', status=status,
                                 duration_ms=(ended - started) * 1000)
                self.events.emit('api.asset.bytes', status=status, count=count)
