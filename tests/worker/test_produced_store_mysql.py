"""RT-10(a): real T1, immutable storage, lost COMMIT and process boundaries."""

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import json
import os
import subprocess
import sys
from threading import Barrier

import pytest
import sqlalchemy as sa

from daesingo.common.config import DbSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.jobs.repository import claim_one
from daesingo.common.jobs.schema import job_execution
from mysql_fault_proxy import CommitResponseProxy
from test_worker_mysql import queue, seed, row, composed

pytestmark = pytest.mark.mysql


def module():
    return import_module("daesingo.common.jobs.produced")


def params(scenario, modes):
    return [pytest.param(p, marks=pytest.mark.mysql_check("produced_store", scenario, parameter=p)) for p in modes]


def result(status="SUCCEEDED", payload=None):
    return HandlerResult(status=status, failure_kind="TEST_FAILURE" if status == "FAILED" else None,
        objects=(module().ProducedObject(kind="opaque", payload=payload or {"status": "ABSTAINED", "x": [1, "한글"]}),))


def all_objects(engine):
    with engine.connect() as conn:
        return list(conn.execute(sa.select(module().produced_objects)).mappings())


@pytest.mark.parametrize("status", params("terminal", ("SUCCEEDED", "FAILED")))
def test_worker_terminal_and_payload_share_connection_and_commit(queue, status):
    execution_id, = seed(queue)
    calls, connections = [], []
    def handler(ctx):
        calls.append(ctx.execution_id)
        assert queue.pool.checkedout() == 0
        return result(status)
    def observe(conn, cursor, sql, *args):
        if sql.upper().startswith(("UPDATE JOB_EXECUTION SET STATUS", "INSERT INTO PRODUCED_OBJECTS")):
            connections.append(conn)
    sa.event.listen(queue, "before_cursor_execute", observe)
    try:
        composed(queue, {"TEST": handler}).run()
    finally:
        sa.event.remove(queue, "before_cursor_execute", observe)
    stored = row(queue, execution_id)
    assert stored["status"] == status
    assert stored["produced"] == [{"kind": "opaque", "ref": f"runtime:{execution_id}:0"}]
    assert len(calls) == 1 and len(all_objects(queue)) == 1
    assert len(connections) == 2 and connections[0] is connections[1]
    with queue.connect() as conn:
        assert module().ProducedReader()(conn, "TEST", tuple(stored["produced"])) == result().objects[0].payload


@pytest.mark.parametrize("fault", params("atomicity", ("payload", "terminal")))
def test_either_t1_write_failure_rolls_back_both(queue, fault):
    execution_id, = seed(queue)
    def fail(conn, cursor, sql, *args):
        target = "INSERT INTO PRODUCED_OBJECTS" if fault == "payload" else "UPDATE JOB_EXECUTION SET STATUS"
        if sql.upper().startswith(target):
            raise RuntimeError("injected persistence failure")
    worker = composed(queue, {"TEST": lambda ctx: result()})
    sa.event.listen(queue, "after_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            worker.run()
    finally:
        sa.event.remove(queue, "after_cursor_execute", fail)
    assert row(queue, execution_id)["status"] == "RUNNING"
    assert row(queue, execution_id)["produced"] == [] and all_objects(queue) == []


@pytest.mark.parametrize("mode", params("replay", ("identical", "payload", "binding")))
def test_append_replay_requires_identical_payload_and_binding(queue, mode):
    m = module()
    objects = m.prepare_objects("exec_test", result().objects)
    with queue.begin() as conn:
        m.append_objects(conn, case_id="case", execution_id="exec_test", job_kind="TEST", objects=objects)
    changed = m.prepare_objects("exec_test", result(payload={"x": "different"}).objects) if mode == "payload" else objects
    with queue.begin() as conn:
        if mode == "identical":
            m.append_objects(conn, case_id="case", execution_id="exec_test", job_kind="TEST", objects=changed)
        else:
            with pytest.raises(m.ProducedConflict):
                m.append_objects(conn, case_id="different" if mode == "binding" else "case",
                    execution_id="exec_test", job_kind="TEST", objects=changed)
    assert len(all_objects(queue)) == 1 and all_objects(queue)[0]["payload"] == result().objects[0].payload


@pytest.mark.parametrize("mode", params("concurrent", ("same", "conflict")))
def test_concurrent_append_never_overwrites(queue, mode):
    m, barrier = module(), Barrier(2)
    def writer(index):
        objects = m.prepare_objects("exec_test", result(payload={"value": index if mode == "conflict" else 0}).objects)
        barrier.wait(10)
        try:
            run_worker_transaction(queue, lambda conn: m.append_objects(conn, case_id="case",
                execution_id="exec_test", job_kind="TEST", objects=objects), sleep=lambda _: None)
            return "OK"
        except m.ProducedConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(writer, (0, 1)))
    assert sorted(outcomes) == (["OK", "OK"] if mode == "same" else ["CONFLICT", "OK"])
    assert len(all_objects(queue)) == 1


@pytest.mark.mysql_check("produced_store", "ownership", parameter="stolen")
def test_stolen_lease_cannot_leave_payload(queue):
    execution_id, = seed(queue)
    def handler(ctx):
        with queue.begin() as conn:
            conn.execute(job_execution.update().values(lease_owner="other"))
        return result()
    composed(queue, {"TEST": handler}).run()
    assert row(queue, execution_id)["status"] == "RUNNING" and all_objects(queue) == []


@pytest.mark.parametrize("status", params("commit_unknown", ("SUCCEEDED", "FAILED")))
def test_real_lost_commit_ack_recovers_payload_without_reinvocation(queue, status):
    execution_id, = seed(queue)
    calls, sleeps = [], []
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        url = queue.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        engine = create_worker_engine(DbSettings(url=url.render_as_string(hide_password=False)))
        def handler(ctx):
            calls.append(ctx.execution_id)
            return result(status)
        def arm(conn, cursor, sql, *args):
            if sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"):
                proxy.arm()
        sa.event.listen(engine, "after_cursor_execute", arm)
        try:
            composed(engine, {"TEST": handler}, sleep=sleeps.append).run()
            assert proxy.commit_ok_dropped == 1
        finally:
            sa.event.remove(engine, "after_cursor_execute", arm)
            engine.dispose()
    assert calls == [execution_id] and sleeps == [1]
    assert row(queue, execution_id)["status"] == status and len(all_objects(queue)) == 1


@pytest.mark.parametrize("mode", params("reader", ("single", "multiple", "missing", "wrong_kind", "mixed_execution", "empty")))
def test_existing_reader_callable_is_opaque_and_fail_closed(queue, mode):
    m = module()
    objects = m.prepare_objects("exec_test", (m.ProducedObject(kind="first", payload={"a": 1}),
        m.ProducedObject(kind="second", payload={"b": 2})))
    with queue.begin() as conn:
        m.append_objects(conn, case_id="case", execution_id="exec_test", job_kind="TEST", objects=objects)
        other = m.prepare_objects("exec_other", (m.ProducedObject(kind="third", payload={"c": 3}),))
        m.append_objects(conn, case_id="case", execution_id="exec_other", job_kind="TEST", objects=other)
    refs = tuple(o.reference.model_dump() for o in objects)
    with queue.begin() as conn:
        if mode == "single":
            assert m.ProducedReader()(conn, "TEST", refs[:1]) == {"a": 1}
        elif mode == "multiple":
            reader = m.ProducedReader(assemble=lambda kind, values: {"kind": kind, "values": values})
            assert reader(conn, "TEST", refs) == {"kind": "TEST", "values": ({"a": 1}, {"b": 2})}
            with pytest.raises(ValueError):
                m.ProducedReader()(conn, "TEST", refs)
        else:
            selected = () if mode == "empty" else ({"kind": "first", "ref": "absent"},) if mode == "missing" else refs[:1]
            if mode == "mixed_execution":
                selected = refs[:1] + (other[0].reference.model_dump(),)
            with pytest.raises(ValueError):
                m.ProducedReader()(conn, "OTHER" if mode == "wrong_kind" else "TEST", selected)


@pytest.mark.mysql_check("produced_store", "process", parameter="fresh_read")
def test_fresh_process_reads_durable_payload_with_existing_callable(queue):
    execution_id, = seed(queue)
    composed(queue, {"TEST": lambda ctx: result()}).run()
    code = """
import json, os
from sqlalchemy import create_engine, select
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.schema import job_execution
engine = create_engine(os.environ['PRODUCED_TEST_URL'])
try:
    with engine.begin() as conn:
        row = conn.execute(select(job_execution)).mappings().one()
        print(json.dumps(ProducedReader()(conn, row['kind'], tuple(row['produced']))))
finally:
    engine.dispose()
"""
    completed = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code],
        env=dict(os.environ, PRODUCED_TEST_URL=queue.url.render_as_string(hide_password=False),
                 PYTHONPATH=os.path.abspath("src")), capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == result().objects[0].payload


@pytest.mark.mysql_check("produced_store", "redelivery", parameter="stored_hint")
def test_actual_case_redelivery_uses_stored_reader_once(queue):
    from redelivery_support import seed as seed_case, Timelines, snapshot
    from daesingo.worker.case_reflector import CaseReflector
    from daesingo.common.jobs.redelivery import redeliver_once
    case_id, execution_id = seed_case(queue, description="description", terminal=False)
    # Stop after T1 by leaving the composed reflector absent.
    composed(queue, {"HINT_EXTRACT": lambda ctx: result(payload={"status": "ABSTAINED"})}).run()
    reader = module().ProducedReader()
    for _ in range(2):
        redeliver_once(queue, CaseReflector(reader=reader, timelines=Timelines()), sleep=lambda _: None)
    case = snapshot(queue, case_id)
    assert execution_id in case.processed_executions
    assert len(case.job_records) == 2 and len(all_objects(queue)) == 1
    assert row(queue, execution_id)["case_applied_at"] is not None


@pytest.mark.mysql_check("produced_store", "migration", parameter="upgrade")
def test_migration_metadata_and_forward_only_revision(queue):
    from daesingo.common.db.migrate import upgrade_all
    m = module()
    upgrade_all(queue.url)
    with queue.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0006"
        assert {c["name"] for c in sa.inspect(conn).get_columns("produced_objects")} == set(m.produced_objects.c.keys())
        assert sa.inspect(conn).get_foreign_keys("produced_objects") == []


@pytest.mark.mysql_check("produced_store", "transaction", parameter="caller_rollback")
def test_store_never_owns_commit_and_reader_sees_caller_transaction(queue):
    m = module()
    objects = m.prepare_objects("exec_test", result().objects)
    with queue.connect() as conn:
        with pytest.raises(ValueError):
            m.append_objects(conn, case_id="case", execution_id="exec_test", job_kind="TEST", objects=objects)
        tx = conn.begin()
        m.append_objects(conn, case_id="case", execution_id="exec_test", job_kind="TEST", objects=objects)
        assert m.ProducedReader()(conn, "TEST", tuple(o.reference.model_dump() for o in objects)) == result().objects[0].payload
        assert all_objects(queue) == []
        tx.rollback()
    assert all_objects(queue) == []


@pytest.mark.parametrize("mode", params("receipt", ("intact", "missing", "changed")))
def test_direct_t1_receipt_includes_refs_and_never_repairs_corrupt_payload(queue, mode):
    execution_id, = seed(queue)
    claimed = claim_one(queue, "worker")
    context = ExecutionContext(claimed.execution_id, claimed.job_id, claimed.case_id,
                               claimed.kind, claimed.attempt, claimed.trace_id)
    worker, terminal = composed(queue, {}), result()
    assert worker.record(context, terminal)
    stored = row(queue, execution_id)
    assert stored["produced"] == [{"kind": "opaque", "ref": f"runtime:{execution_id}:0"}]
    if mode != "intact":
        with queue.begin() as conn:
            table = module().produced_objects
            conn.execute(table.delete() if mode == "missing" else table.update().values(payload={"changed": True}))
        with pytest.raises(module().ProducedConflict):
            worker.record(context, terminal)
        assert (all_objects(queue) == []) if mode == "missing" else all_objects(queue)[0]["payload"] == {"changed": True}
    else:
        assert worker.record(context, terminal)
        assert row(queue, execution_id)["ended_at"] == stored["ended_at"]
        assert len(all_objects(queue)) == 1


@pytest.mark.mysql_check("produced_store", "replay", parameter="batch_conflict")
def test_late_batch_conflict_does_not_leave_prefix_even_if_caller_commits(queue):
    m = module()
    first = m.prepare_objects("exec_a", (m.ProducedObject(kind="kind", ref="existing", payload={"v": 1}),))
    with queue.begin() as conn:
        m.append_objects(conn, case_id="case", execution_id="exec_a", job_kind="TEST", objects=first)
    batch = m.prepare_objects("exec_b", (m.ProducedObject(kind="kind", ref="new", payload={}),
        m.ProducedObject(kind="kind", ref="existing", payload={"v": 2})))
    with queue.begin() as conn:
        with pytest.raises(m.ProducedConflict):
            m.append_objects(conn, case_id="case", execution_id="exec_b", job_kind="TEST", objects=batch)
    assert len(all_objects(queue)) == 1 and all_objects(queue)[0]["ref"] == "existing"


@pytest.mark.parametrize("number", [pytest.param(n, marks=pytest.mark.mysql_check(
    "produced_store", "json", parameter=p)) for p, n in (
        ("large_uint", 18446744073709551616), ("large_int", -123456789012345678901234567890))])
def test_opaque_json_numbers_roundtrip_and_exact_t1_replay_without_coercion(queue, number):
    execution_id, = seed(queue)
    claimed = claim_one(queue, "worker")
    context = ExecutionContext(claimed.execution_id, claimed.job_id, claimed.case_id,
                               claimed.kind, claimed.attempt, claimed.trace_id)
    payload = {"number": number, "nested": [True, 1, 1.0, None, -0.0, "한글"]}
    worker, terminal = composed(queue, {}), result(payload=payload)
    assert worker.record(context, terminal)
    refs = tuple(row(queue, execution_id)["produced"])
    with queue.connect() as conn:
        actual = module().ProducedReader()(conn, "TEST", refs)
    assert type(actual["number"]) is int and actual["number"] == number
    assert module()._json(actual) == module()._json(payload)
    assert worker.record(context, terminal)
    assert len(all_objects(queue)) == 1
