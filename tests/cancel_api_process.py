"""Spawned HTTP caller: IPC pins interruption to a real transaction boundary."""

from dataclasses import replace
from io import StringIO
from types import MappingProxyType


def interrupted_request(config, payload, boundary, pipe):
    from fastapi.testclient import TestClient
    from daesingo.api import composition
    from daesingo.api.app import create_app
    from daesingo.common.bootstrap import Startup
    from daesingo.common.logging import configure_logging

    def pause(conn=None):
        pipe.send((boundary, None if conn is None else conn.exec_driver_sql(
            "SELECT CONNECTION_ID()").scalar_one()))
        pipe.recv()  # Parent terminates the process; no timer chooses the cut.

    try:
        original_cancel = composition.request_cancel
        def cancel(conn, ids):
            if boundary == "before_cancel":
                pause(conn)
            original_cancel(conn, ids)
            if boundary == "after_cancel":
                pause(conn)
        composition.request_cancel = cancel
        if boundary == "after_commit":
            original_tx = composition.run_api_transaction
            def transaction(engine, operation):
                result = original_tx(engine, operation)
                pause()
                return result
            composition.run_api_transaction = transaction
        startup = Startup(replace(config), MappingProxyType({}),
                          configure_logging("api", stream=StringIO()))
        with TestClient(create_app(startup=startup)) as client:
            response = client.post(f"/cases/{payload['case_id']}/commands", json=payload)
            pipe.send(("unexpected_response", response.status_code))
    except BaseException as error:
        # Never send exception text, SQL, credentials or traceback over IPC.
        pipe.send(("unexpected_error", type(error).__name__))
    finally:
        pipe.close()
