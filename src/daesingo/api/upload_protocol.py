"""Supported API server transport for Baseline B-U3/B-U4's no-status abort.

ASGI has no HTTP close send event. This server-local extension implements the
existing policy; it never exposes a transport or request input to domain code.
"""
from uvicorn.protocols.http.h11_impl import H11Protocol


class UploadH11Protocol(H11Protocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        application = self.app

        async def app(scope, receive, send):
            # Capture this request, rather than a subsequent keep-alive cycle.
            cycle = self.cycle
            def close():
                cycle.disconnected = True
                cycle.keep_alive = False
                cycle.message_event.set()
                self.transport.close()
            scope.setdefault('extensions', {})['daesingo.close'] = close
            await application(scope, receive, send)
        self.app = app
