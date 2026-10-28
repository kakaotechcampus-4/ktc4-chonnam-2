from dataclasses import replace
from copy import deepcopy

import pytest

from daesingo.case.domain import CaseAggregate
from daesingo.case.exports import issue_missing_exports
from daesingo.case.store import CaseStore
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.worker.export_inputs import ExportInputs
from types import SimpleNamespace


@pytest.mark.parametrize("kind", ["REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"])
@pytest.mark.parametrize("bad", [None, "job", "case", "kind", "fingerprint", "request"])
def test_export_input_is_detached_and_bound_to_job(kind, bad):
    from tests.case.test_export_ordering import eligible, requests
    case = CaseAggregate.empty("case")
    issue_missing_exports(case, SimpleNamespace(get_export_requests=requests), eligible())
    job = next(r for r in case.job_records if r["kind"] == kind)
    ctx = ExecutionContext("execution", job["job_id"], "case", kind, 1, "trace")
    if bad == "job": ctx = replace(ctx, job_id="absent")
    if bad == "case": job["case_id"] = "foreign"
    if bad == "kind": job["kind"] = "OTHER"
    if bad == "fingerprint": job["input_fingerprint"] = "different"
    if bad == "request": case.export_inputs[job["job_id"]]["incident_clip_ref"] = "different"
    conn = object(); store = CaseStore(conn=conn); store.register(case)
    active = []
    def tx(callback):
        active.append(True)
        try: return callback(conn)
        finally: active.pop()
    inputs = ExportInputs(transaction=tx, store_factory=lambda connection: store)
    if bad:
        with pytest.raises((ValueError, KeyError)): inputs(ctx)
    else:
        data = inputs(ctx)
        assert not active and data.request == requests()[kind]
        data.request["incident_clip_ref"] = "mutated"
        assert store.export_input("case", job["job_id"]) == requests()[kind]
