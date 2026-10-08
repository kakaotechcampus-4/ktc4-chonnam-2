"""Fail-closed harness/report behavior, independent of a MySQL server."""

import importlib.util
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]

# Independent role/scenario acceptance inventory, deliberately not imported
# from the implementation being tested. Test function names are irrelevant.
REQUIRED_CHECKS = (
    ("api", "sessions"), ("worker", "sessions"),
    ("api", "idle_recycle"), ("worker", "idle_recycle"),
    ("api", "disconnect_replacement"), ("worker", "disconnect_replacement"),
    ("api", "wait_timeout"), ("worker", "wait_timeout"),
    ("api", "pool_exhaustion"), ("heartbeat", "sessions"),
    ("heartbeat", "dedicated_connections"), ("ready", "dedicated_connections"),
    ("migration", "migration_policy"), ("api", "connect_failure"),
    ("worker", "worker_1205"), ("worker", "worker_1213"),
    ("worker", "worker_disconnect"), ("worker", "worker_exhaustion"),
    ("worker", "capability_boundary"), ("worker", "worker_unknown_commit"),
    ("api", "precommit_1205"), ("api", "precommit_disconnect"),
    ("api", "precommit_proxy_disconnect"), ("api", "commit_response_loss"),
    ("api", "commit_response_loss_context_exit"), ("api", "commit_response_loss_pool_checkin"),
    ("harness", "require_privileges"), ("case", "case_compatibility"),
    ("harness", "schema_identity"), ("harness", "schema_override_database"),
    ("harness", "schema_override_db"), ("harness", "schema_override_init_command"),
)


def checker():
    path = ROOT / "scripts" / "check_mysql_test_report.py"
    spec = importlib.util.spec_from_file_location("mysql_report_checker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_report():
    nodes = [{"nodeid": f"tests/common/db/integration/test_required.py::test_{name}",
              "scenarios": [name]} for name in (
        "sessions", "session_replacements", "worker_1205", "worker_1213", "worker_disconnect",
        "worker_exhaustion", "capability_boundary", "api_precommit", "commit_response_loss",
        "worker_unknown_commit", "pool_exhaustion", "dedicated_connections", "idle_recycle",
        "wait_timeout", "case_compatibility", "migration_policy", "require_privileges")]
    # Explicit baseline inventory: do not derive expectations from the gate.
    nodes += [{"nodeid": "tests/case/test_store_mysql.py::" + name, "scenarios": []} for name in (
        "test_migration_creates_case_tables_with_ascii_bin_ids", "test_rollback_leaves_nothing",
        "test_update_lock_makes_second_writer_wait", "test_repository_never_commits",
        "test_append_only_violation_writes_nothing_even_if_caller_commits")]
    nodes += [{"nodeid": "tests/case/test_case_repository_contract.py::" + name + "[mysql]", "scenarios": []} for name in (
        "test_insert_then_load_round_trips", "test_load_returns_a_new_object_each_time",
        "test_save_persists_changes_and_appended_records", "test_save_refuses_changed_prefix",
        "test_save_refuses_removed_record", "test_load_missing_case_is_key_error", "test_insert_twice_is_refused",
        "test_case_ids_differ_by_case_only_are_distinct", "test_tuple_in_state_round_trips_as_list",
        "test_non_json_value_in_state_is_refused")]
    nodes += [{"nodeid": "tests/case/test_case_repository_contract.py::test_invalid_case_id_is_refused_before_insert[mysql-" + name + "]",
               "scenarios": []} for name in ("empty", "long", "unicode")]
    nodes += [{"nodeid": f"tests/common/db/integration/test_checks.py::test_check_{index}",
               "scenarios": [], "checks": [{"role": role, "scenario": scenario}]}
              for index, (role, scenario) in enumerate(REQUIRED_CHECKS)]
    return {"server_version": "8.4.7", "collected": nodes,
            "selected": [n["nodeid"] for n in nodes], "collection_errors": [],
            "reports": [{"nodeid": n["nodeid"], "when": when, "outcome": "passed", "xfail": False}
                        for n in nodes for when in ("setup", "call", "teardown")]}


def test_report_accepts_complete_real_mysql_evidence():
    checker().validate_report(good_report())


@pytest.mark.parametrize("broken", ["empty", "skip", "xfail", "deselected", "missing_call", "missing_scenario", "collection", "wrong_server", "missing_case"])
def test_report_rejects_bypasses(broken):
    report = good_report()
    if broken == "empty":
        report["collected"] = []
    elif broken == "skip":
        report["reports"][0]["outcome"] = "skipped"
    elif broken == "xfail":
        report["reports"][1]["xfail"] = True
    elif broken == "deselected":
        report["selected"].pop()
    elif broken == "missing_call":
        report["reports"].pop(1)
    elif broken == "missing_scenario":
        report["collected"][0]["scenarios"] = []
    elif broken == "collection":
        report["collection_errors"] = ["test_store_mysql.py"]
    elif broken == "wrong_server":
        report["server_version"] = "8.0.40"
    elif broken == "missing_case":
        report["collected"] = [n for n in report["collected"] if "/case/" not in n["nodeid"]]
    with pytest.raises(ValueError):
        checker().validate_report(report)


def test_require_missing_url_fails_before_collection(tmp_path):
    env = dict(os.environ, DAESINGO_REQUIRE_MYSQL="1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("DAESINGO_MYSQL_URL", None)
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "pytest",
                             "tests/common/db/test_engines.py", "--collect-only", "-q", "-p", "no:cacheprovider"],
                            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "DAESINGO_MYSQL_URL" in result.stdout + result.stderr
    assert "skipped" not in result.stdout


def test_require_missing_dependency_fails_without_skip(tmp_path):
    # A startup import blocker simulates an unavailable dependency in a child
    # process without uninstalling anything from the user's environment.
    (tmp_path / "sitecustomize.py").write_text(
        "import sys\nclass Block:\n def find_spec(self, fullname, *args):\n"
        "  if fullname == 'pymysql': raise ModuleNotFoundError('blocked dependency')\n"
        "sys.meta_path.insert(0, Block())\n", encoding="utf-8")
    env = dict(os.environ, DAESINGO_REQUIRE_MYSQL="1", DAESINGO_MYSQL_URL="mysql+pymysql://t:p@127.0.0.1/test_db",
               PYTHONPATH=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "pytest",
                             "tests/common/db/test_engines.py", "--collect-only", "-q", "-p", "no:cacheprovider"],
                            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "MySQL required dependency unavailable" in result.stdout + result.stderr
    assert "skipped" not in result.stdout


def test_require_connection_failure_is_an_error_not_skip():
    env = dict(os.environ, DAESINGO_REQUIRE_MYSQL="1", PYTHONDONTWRITEBYTECODE="1",
               DAESINGO_MYSQL_URL="mysql+pymysql://t:p@127.0.0.1:1/test_db")
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "pytest",
                             "tests/common/db/test_engines.py", "--collect-only", "-q", "-p", "no:cacheprovider"],
                            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "MySQL preflight failed" in result.stdout + result.stderr
    assert "skipped" not in result.stdout


def test_require_url_option_failure_is_sanitized_before_connect():
    secret = "private-timeout-value"
    env = dict(os.environ, DAESINGO_REQUIRE_MYSQL="1", PYTHONDONTWRITEBYTECODE="1",
               DAESINGO_MYSQL_URL="mysql+pymysql://t:p@127.0.0.1/test_db?connect_timeout=" + secret)
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "pytest",
                             "tests/common/db/test_engines.py", "--collect-only", "-q", "-p", "no:cacheprovider"],
                            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "MySQL preflight failed" in result.stdout + result.stderr
    assert secret not in result.stdout + result.stderr
    assert "skipped" not in result.stdout


def test_report_cli_fails_on_missing_artifact(tmp_path):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/check_mysql_test_report.py"),
                             str(tmp_path / "missing.json")], text=True, capture_output=True, timeout=15)
    assert result.returncode != 0


def test_gate_rejects_partial_case_file_even_when_every_selected_test_passes():
    report = good_report()
    removed = next(item["nodeid"] for item in report["collected"]
                   if "test_invalid_case_id_is_refused_before_insert[mysql-unicode]" in item["nodeid"])
    report["collected"] = [item for item in report["collected"] if item["nodeid"] != removed]
    report["selected"].remove(removed)
    report["reports"] = [item for item in report["reports"] if item["nodeid"] != removed]
    with pytest.raises(ValueError, match="Case"):
        checker().validate_report(report)


@pytest.mark.parametrize("role,scenario", REQUIRED_CHECKS)
def test_each_required_role_check_is_mandatory_even_with_same_scenario_elsewhere(role, scenario):
    report = deepcopy(good_report())
    removed = {item["nodeid"] for item in report["collected"]
               if {"role": role, "scenario": scenario} in item.get("checks", [])}
    assert len(removed) == 1
    report["collected"] = [item for item in report["collected"] if item["nodeid"] not in removed]
    report["selected"] = [node for node in report["selected"] if node not in removed]
    report["reports"] = [item for item in report["reports"] if item["nodeid"] not in removed]
    with pytest.raises(ValueError, match="role/scenario"):
        checker().validate_report(report)


@pytest.mark.parametrize("tag", ["skipped", "failure", "error", "missing"])
def test_junit_cross_check_rejects_missing_or_unsuccessful_execution(tmp_path, tag):
    report = {"collected": [{"junit": ["tests.common.db.test_example", "test_mysql"]}]}
    case = "" if tag == "missing" else f'<testcase classname="tests.common.db.test_example" name="test_mysql"><{tag}/></testcase>'
    path = tmp_path / "junit.xml"
    path.write_text("<testsuite>" + case + "</testsuite>", encoding="utf-8")
    with pytest.raises(ValueError):
        checker().validate_junit(path, report)
