"""Frame admission surrounds the outer ASGI send, including BaseHTTPMiddleware."""
import asyncio
import re
from time import monotonic

from daesingo.common.logging import bind_context, new_trace_id


class FrameLifetimeMiddleware:
    def __init__(self, app, *, composition):
        self.app = app
        self.permits = asyncio.Semaphore(composition.startup.config.frame.concurrency)
        self.events = composition.readiness.events

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        root = scope.get('root_path', '')
        if root and path.startswith(root + '/'):
            path = path[len(root):]
        if (scope['type'] != 'http' or scope['method'] != 'GET'
                or re.fullmatch(r'/cases/[^/]+/frames/[^/]+', path) is None):
            return await self.app(scope, receive, send)
        state = scope.setdefault('state', {})
        state['frame_trace_id'] = new_trace_id()
        started = monotonic()
        acquired = False
        status = 'CANCELLED'
        complete = False

        async def transmit(message):
            nonlocal status, complete
            if message['type'] == 'http.response.start':
                status = str(message['status'])
            await send(message)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                complete = True

        with bind_context(trace_id=state['frame_trace_id'], module='api'):
            self.events.emit('api.frame.request_rate', count=1)
            try:
                try:
                    await self.permits.acquire()
                    acquired = True
                finally:
                    self.events.emit('api.frame.wait_ms', duration_ms=(monotonic() - started) * 1000)
                await self.app(scope, receive, transmit)
                if not complete:
                    status = 'CANCELLED'
            except asyncio.CancelledError:
                status = 'CANCELLED'
                raise
            except Exception:
                status = 'FAILED'
                raise
            finally:
                if acquired:
                    read = state.get('frame_read_task')
                    if read is not None and not read.done():
                        # A cancelled HTTP request cannot abandon a DB thread and
                        # admit another read before that thread's cleanup ends.
                        read.add_done_callback(lambda task: self.permits.release())
                    else:
                        self.permits.release()
                self.events.emit('api.frame.latency_ms', status=status,
                                 duration_ms=(monotonic() - started) * 1000)
