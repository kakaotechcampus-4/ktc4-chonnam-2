"""Real schema/data/source recovery, separate from image or operating approval."""
import json

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa

from daesingo.api.app import create_app
from daesingo.api.public_access import COOKIE
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.repository import now
from tests.api.conftest import api_startup  # noqa: F401
from tests.api.test_public_mysql import public_api, public_db, register  # noqa: F401
from test_compatible_revisions_mysql import releases, invoke  # noqa: F401

pytestmark = pytest.mark.mysql


def env_file(tmp_path, url, root):
    path = tmp_path / "test-runtime.private.env"
    path.write_text("DAESINGO_RUNTIME_DB_URL=" + url.render_as_string(hide_password=False)
        + "\nDAESINGO_RUNTIME_MEDIA_ROOT=" + str(root) + "\nDAESINGO_RUNTIME_API_TEMP_ROOT=" + str(root) + "\n",
        encoding="utf-8")
    path.chmod(0o600)
    return str(path)


@pytest.mark.mysql_check("public_a1", "recovery")
@pytest.mark.parametrize("old", ["preview_final", "preview_bridge"], ids=["bb29", "b915"])
def test_real_head6_to7_keeps_old_jobs_and_readiness_but_old_migrator_refuses_unknown_head(
        mysql_schema_url, releases, tmp_path, old):
    root = tmp_path / "media"
    root.mkdir()
    assert invoke(releases, old, mysql_schema_url, root, "migrate")["ok"]
    seeded = invoke(releases, old, mysql_schema_url, root, "job_seed", case_id="retained")
    assert seeded["ok"] and seeded["result"]["budget"] == 600
    upgrade_all(mysql_schema_url)
    engine = sa.create_engine(mysql_schema_url, hide_parameters=True)
    try:
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0008"
            assert conn.execute(sa.select(t.control.c.accepting)).scalar_one() is False
        assert invoke(releases, old, mysql_schema_url, root, "job_finish", case_id="retained")["ok"]
        assert invoke(releases, old, mysql_schema_url, root, "job_reflect", case_id="retained")["ok"]
        read = invoke(releases, old, mysql_schema_url, root, "case_roundtrip", case_id="retained")
        assert read["ok"] and read["result"]["budget"] == 600
        assert read["result"]["future_key"] == {"kept": [1, 2]}
        path = env_file(tmp_path, mysql_schema_url, root)
        health = invoke(releases, old, mysql_schema_url, root, "preview_api", operation="health", env_file=path)
        assert health["ok"] and health["result"] == {"live": 200, "ready": 200}
        # Existing rollback skips migrate. Re-running an old migrator is a
        # different operation and must not stamp/downgrade the unknown head.
        refused = invoke(releases, old, mysql_schema_url, root, "migrate")
        assert not refused["ok"] and refused["error"] == "MigrationFailure"
        upgrade_all(mysql_schema_url)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0008"
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM cases WHERE case_id='retained'").scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.mysql_check("public_a1", "recovery")
@pytest.mark.parametrize("old", ["preview_final", "preview_bridge"], ids=["bb29", "b915"])
def test_old_source_serves_head7_data_without_session_and_is_not_public_safe(public_api, releases, tmp_path, old):
    client, composition, engine, _ = public_api
    cid, _ = register(client)
    with engine.begin() as conn:
        composition.public.store.set_open(conn, False)
    # New gate remains closed; authorized reads remain available. An unowned
    # browser is denied even though the old source can read the same SQL data.
    current = client.get(f"/cases/{cid}/view", headers={"Cookie": ""})
    assert current.status_code == 404
    path = env_file(tmp_path, engine.url, composition.startup.config.media_root)
    old_read = invoke(releases, old, engine.url, composition.startup.config.media_root, "preview_api",
                      env_file=path, case_id=cid)
    assert old_read["ok"] and old_read["result"]["status"] == 200
    assert old_read["result"]["body"]["case_id"] == cid
    with engine.connect() as conn:
        assert conn.execute(sa.select(t.control.c.accepting)).scalar_one() is False
        assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0008"
    # This is a negative compatibility control, not approval of this target.
    # DB CLOSED alone cannot protect an old API; closed public ingress would
    # have to be independently proved before any maintenance-only rollback.


@pytest.mark.mysql_check("public_a1", "recovery")
def test_existing_controller_can_restart_current_guarded_tuple_without_schema_or_ledger_rollback(public_api, tmp_path):
    from tests.deploy.test_ec2_deploy import Host, module, seed_current
    client, composition, engine, _ = public_api
    cid, revision = register(client)
    cookie = client.cookies.get(COOKIE)
    with engine.begin() as conn:
        composition.public.store.set_open(conn, False)
        conn.execute(t.reservations.insert().values(usage_id="TEST_ONLY_HELD", execution_ref="TEST_ONLY_PAST",
            case_id=cid, operation="SEARCH_COARSE", provider_label="fake:test", amount_micros=10, created_at=now(conn)))
        before = dict(conn.execute(sa.select(t.reservations)).mappings().one())
    root = tmp_path / "owned-controller"
    root.mkdir()
    controller = module()
    # Synthetic state-machine identity only. No actual image/release approval,
    # publication, AWS, service stop or root-host files are involved.
    guarded = {"revision": "1" * 40, "image": "TEST_ONLY@sha256:" + "a" * 64,
               "config_id": "TEST_ONLY_GUARDED", "rollback_targets": ["1" * 40]}
    seed_current(controller, root, guarded)
    controller.atomic_json(root / "schema.json", {**guarded, "phase": "migration_complete"})
    host = Host(root)
    with controller.operation_lock(root):
        controller.transition(root, guarded, "rollback", host)
    assert "migrate" not in host.calls
    assert not (root / "dirty.json").exists() and not (root / "operation.lock").exists()
    assert json.loads((root / "schema.json").read_text())["revision"] == guarded["revision"]
    # Cold API composition on the unchanged actual MySQL validates restored
    # process state, ownership and stopped admission; Worker restart is covered
    # by the actual loop/ledger test in test_public_lifecycle_mysql.
    with TestClient(create_app(startup=composition.startup), base_url="https://testserver") as restarted:
        assert restarted.get("/health/ready").status_code == 200
        assert restarted.get(f"/cases/{cid}/view").status_code == 404
        headers = {"Origin": "https://testserver", "Cookie": COOKIE + "=" + cookie}
        assert restarted.get(f"/cases/{cid}/view", headers=headers).status_code == 200
        # Reach stopped admission with a valid command, rather than failing
        # Case's payload validation before any new job can be proposed.
        stopped = restarted.post(f"/cases/{cid}/commands", headers=headers,
            json={"case_id": cid, "expected_case_rev": revision, "kind": "START_ANALYSIS",
                  "payload": {"description": "Test"}})
        assert stopped.status_code == 503
        assert stopped.json()["error"]["code"] == "public.jobs_stopped"
    with engine.connect() as conn:
        assert dict(conn.execute(sa.select(t.reservations)).mappings().one()) == before
        assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0008"
    refused = Host(root)
    with pytest.raises(controller.HostError):
        controller.transition(root, {**guarded, "config_id": "NOT_APPROVED"}, "rollback", refused)
    assert refused.calls == []
