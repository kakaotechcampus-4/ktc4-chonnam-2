"""HTTP Contract §5.4: preserve the public CaseView, map only missing Case."""
from fastapi import APIRouter, HTTPException, Request
from time import monotonic
from daesingo.case.store import CaseNotFound


def view_router(composition):
    router = APIRouter()

    @router.get("/cases/{case_id}/view")
    def view(case_id: str, request: Request):
        started = monotonic()
        composition.readiness.events.emit('api.view.request_rate', count=1)
        try:
            body = composition.get_view(case_id)
        except CaseNotFound:
            raise HTTPException(404) from None
        finally:
            composition.readiness.events.emit('api.view.latency_ms', duration_ms=(monotonic()-started)*1000)
        request.state.case_id = body["case_id"]
        return body

    return router
