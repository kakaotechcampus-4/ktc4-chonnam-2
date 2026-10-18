"""HTTP Contract §5.1: no request body, server-issued identity."""
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse


def cases_router(composition):
    router = APIRouter()

    @router.post("/cases")
    def create(request: Request):
        body = composition.create_case()
        request.state.case_id = body["case_id"]
        return JSONResponse(body, status_code=201,
                            headers={"Location": f'/cases/{body["case_id"]}/view'})

    return router
