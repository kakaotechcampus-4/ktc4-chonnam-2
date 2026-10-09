"""Check omissions against an actual complete MySQL report, not fabricated evidence."""

from copy import deepcopy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from migration_support import ROOT

pytestmark = pytest.mark.mysql

# Independent acceptance inventory, not imported from the gate under test.
MIGRATION_CHECKS = (
    "case_external_transaction", "case_url_precedence", "case_offline_precedence",
    "empty_schema", "idempotency", "explicit_target", "first_runtime_revision",
    "partial_failure", "revision_preflight", "process_guard", "cli_stdin",
)


def test_actual_report_rejects_each_missing_migration_check(mysql_schema_url, tmp_path):
    report_path = tmp_path / "mysql.json"
    junit_path = tmp_path / "mysql.xml"
    env = dict(os.environ, DAESINGO_MYSQL_URL=mysql_schema_url.render_as_string(hide_password=False),
               DAESINGO_REQUIRE_MYSQL="1", PYTHONDONTWRITEBYTECODE="1")
    # Exclude this test to avoid recursion. Use a separate disposable base schema
    # so legacy Case initialization cannot alter the parent suite's database.
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-m", "pytest", "tests/common/db/integration",
         "tests/case/test_store_mysql.py", "tests/case/test_case_repository_contract.py",
         "--ignore=tests/common/db/integration/test_migration_gate.py", "-m", "mysql", "-q",
         "-p", "no:cacheprovider", f"--basetemp={tmp_path / 'child'}",
         f"--mysql-report={report_path}", f"--junitxml={junit_path}"],
        env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("real_report_gate", ROOT / "scripts/check_mysql_test_report.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    gate.validate_report(report)
    gate.validate_junit(junit_path, report)
    for scenario in MIGRATION_CHECKS:
        broken = deepcopy(report)
        removed = {item["nodeid"] for item in broken["collected"]
                   if {"role": "migration", "scenario": scenario} in item.get("checks", [])}
        assert removed, scenario
        broken["collected"] = [item for item in broken["collected"] if item["nodeid"] not in removed]
        broken["selected"] = [node for node in broken["selected"] if node not in removed]
        broken["reports"] = [item for item in broken["reports"] if item["nodeid"] not in removed]
        with pytest.raises(ValueError, match="role/scenario"):
            gate.validate_report(broken)
