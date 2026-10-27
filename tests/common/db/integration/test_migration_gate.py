"""Check omissions against an actual complete MySQL report, not fabricated evidence."""

import importlib.util
import json
import os
import subprocess
import sys
from xml.etree import ElementTree

import pytest

from mysql_report_mutations import copy_parameter_evidence, omit_evidence_nodes

from migration_support import ROOT
from usage_acceptance import USAGE_CHECKS, USAGE_PARAMETERS
from redelivery_acceptance import REDELIVERY_CHECKS, REDELIVERY_PARAMETERS
from timestamp_acceptance import TIMESTAMP_CHECKS, TIMESTAMP_PARAMETERS
from commands_acceptance import COMMAND_CHECKS, COMMAND_PARAMETERS
from cancel_api_acceptance import CANCEL_API_CHECKS, CANCEL_API_PARAMETERS
from async_e2e_acceptance import ASYNC_E2E_CHECKS, ASYNC_E2E_PARAMETERS
from start_analysis_acceptance import START_ANALYSIS_CHECKS, START_ANALYSIS_PARAMETERS
from recording_acceptance import RECORDING_CHECKS, RECORDING_PARAMETERS
from upload_acceptance import UPLOAD_CHECKS, UPLOAD_PARAMETERS
from produced_acceptance import PRODUCED_CHECKS, PRODUCED_PARAMETERS
from frame_acceptance import FRAME_CHECKS, FRAME_PARAMETERS
from asset_acceptance import ASSET_CHECKS, ASSET_PARAMETERS
from observability_acceptance import OBSERVABILITY_CHECKS, OBSERVABILITY_PARAMETERS

pytestmark = pytest.mark.mysql

# Independent acceptance inventory, not imported from the gate under test.
API_CASES_VIEW_PARAMETERS = tuple((role, scenario, parameter) for role, scenario, parameter in (
    ("api_view", "transaction", "uncommitted_scope"), ("api_view", "read", "latest_attempt"),
    ("api_cases", "failure", "unrelated_sql"),
    ("api_cases", "create", "contract"), ("api_cases", "create", "body_unread"),
    ("api_view", "read", "missing"), ("api_view", "read", "queued"),
    ("api_view", "read", "running"), ("api_view", "read", "terminal_gap"),
    ("api_view", "transaction", "lock_order"), ("api_cases", "transaction", "rollback"),
    ("api_cases", "failure", "pool_exhausted"), ("api_view", "failure", "pool_exhausted"),
    ("api_view", "failure", "lock_timeout"), ("api_cases", "failure", "disconnect"),
    ("api_view", "failure", "disconnect"), ("api_cases", "failure", "postcommit_read"),
    ("api_cases", "failure", "commit_unknown"), ("api_view", "failure", "commit_unknown"),
    ("api_cases", "failure", "deadlock"), ("api_cases", "logging", "correlation")))

API_HEALTH_PARAMETERS = tuple(("api_health", scenario, parameter) for scenario, parameter in (
    ("ready", "normal"), ("ready", "pool_exhausted"), ("ready", "connection_lost"),
    ("ready", "server_stopped"), ("storage", "readonly"), ("process", "single_worker")))

MIGRATION_CHECKS = (
    "case_external_transaction", "case_url_precedence", "case_offline_precedence",
    "empty_schema", "idempotency", "explicit_target", "first_runtime_revision",
    "partial_failure", "revision_preflight", "process_guard", "cli_stdin",
)

LIFECYCLE_CHECKS = (
    ("jobs", "token_migration"),
    ("jobs", "claim_basic"),
    ("jobs", "claim_eligibility"),
    ("jobs", "claim_empty"),
    ("jobs", "claim_concurrent"),
    ("jobs", "claim_skip_locked"),
    ("jobs", "claim_commit_boundary"),
    ("jobs", "claim_no_insert"),
    ("jobs", "claim_index"),
    ("jobs", "finish_targets"),
    ("jobs", "finish_guard"),
    ("jobs", "finish_rollback"),
    ("jobs", "finish_rejection"),
    ("jobs", "finish_validation"),
    ("jobs", "claim_unknown_commit"),
    ("jobs", "claim_token_identity"),
    ("jobs", "claim_disconnect"),
    ("jobs", "finish_race"),
    ("jobs", "claim_rc_finish"),
    ("jobs", "finish_deadlock"),
    ("jobs", "claim_lock_timeout"),
    ("jobs", "claim_latency"),
    ("api", "utc_session"), ("worker", "utc_session"),
)

WORKER_CHECKS = (
    *REDELIVERY_CHECKS,
    *(("sweep", scenario) for scenario in ("detect_latency", "detect_boundary", "detect_fault")),
    ("sweep_worker", "hook_fatal"), ("sweep_worker", "hook_exception"),
    *(("sweep", scenario) for scenario in (
        "atomicity", "eligibility", "cap_cancel", "backoff", "concurrent", "recheck",
        "rollback_retry", "unknown_commit", "cancel_race", "expiry", "metrics")),
    *(("sweep_worker", scenario) for scenario in (
        "startup", "independent", "heartbeat", "queue_wait", "slow_queue_logger")),
    ("cancel_worker", "terminal_ack"),
    ("cancel_worker", "observe_commit"), ("cancel_worker", "queued_no_usage"),
    *(("cancel", scenario) for scenario in (
        "states", "transaction", "claim_race", "sweep_race", "finish_race", "lock_order", "validation", "sweep_pending")),
    *(("cancel_worker", scenario) for scenario in (
        "observe", "late_success", "ownership", "heartbeat_error", "cleanup", "db_clock", "observation_fault")),
    ("heartbeat_lifecycle", "owned_cleanup"),
    *(("heartbeat_lifecycle", scenario) for scenario in (
        "renewal", "zero_rows", "commit_race", "retry_fence", "cleanup", "slow_attempt", "error_isolation", "connection_fault", "zero_commit_failure")),
    # RT-04(b): T2 delivery, atomicity, retry and fake E2E-0.
    *(("worker_t2", scenario) for scenario in (
        "delivery", "rollback", "t1_gap", "commit_recovery", "metric",
        "zero_guard", "sink_isolation", "e2e0", "recovery")),
    ("worker_core", "success"), ("worker_core", "failure"),
    ("worker_core", "claim_db_recovery"), ("worker_core", "terminal_db_recovery"),
    ("worker_core", "terminal_unknown_commit"), ("worker_core", "finish_rejected"),
    ("worker_core", "correlation"),
    ("worker_core", "logger_isolation"),
)

WORKER_PARAMETERS = (
    *REDELIVERY_PARAMETERS,
    *(("sweep", "detect_latency", f"{lease}_{reason}") for lease in (60, 7)
      for reason in ("RETRIED", "EXHAUSTED", "CANCELLED")),
    *(("sweep", "detect_boundary", mode) for mode in ("transition_clock", "null", "future")),
    *(("sweep", "detect_fault", mode) for mode in ("calculation", "logger", "filter", "handler")),
    *(("sweep_worker", "hook_fatal", f"{phase}_{kind}_{sink}") for phase in ("startup", "periodic")
      for kind in ("exit", "interrupt", "base") for sink in ("healthy", "logger", "filter", "handler")),
    ("sweep_worker", "hook_exception", "startup_periodic"),
    *(("sweep", "atomicity", mode) for mode in ("commit", "rollback")),
    *(("sweep", "cap_cancel", mode) for mode in ("cancel", "exhausted", "disabled")),
    *(("sweep", "recheck", mode) for mode in ("heartbeat", "finish", "cancel")),
    *(("sweep", "cancel_race", mode) for mode in ("sweep", "cancel")),
    *(("sweep_worker", "queue_wait", mode) for mode in ("1", "2")),
    *(("cancel_worker", "terminal_ack", mode) for mode in
      ("commit_delay", "slow_logger", "lock_wait", "unknown_commit", "retry",
       "logger", "filter", "handler", "calculation", "zero_rows")),
    *(("cancel", "states", state) for state in
      ("QUEUED", "RUNNING", "STALE", "SUCCEEDED", "FAILED", "CANCELLED")),
    *(("cancel", "transaction", mode) for mode in ("commit", "rollback")),
    *(("cancel", "claim_race", mode) for mode in ("cancel", "claim", "concurrent")),
    *(("cancel", "sweep_race", mode) for mode in ("sweep", "cancel")),
    *(("cancel", "finish_race", mode) for mode in ("SUCCEEDED", "CANCELLED", "marker")),
    *(("cancel_worker", "observe", sink) for sink in
      ("healthy", "logger", "filter", "handler", "observer")),
    *(("cancel_worker", "ownership", mode) for mode in ("ownership", "cancel")),
    *(("cancel_worker", "cleanup", mode) for mode in
      ("success", "failure", "exception", "interrupt", "exit", "cancel")),
    *(("cancel_worker", "observation_fault", fault) for fault in ("read", "commit")),
    *(("heartbeat_lifecycle", "retry_fence", mode) for mode in ("transaction", "loop")),
    *(("heartbeat_lifecycle", "owned_cleanup", mode) for mode in
      ("success", "heartbeat_interrupt", "handler_interrupt")),
    *(("heartbeat_lifecycle", "zero_rows", sink) for sink in
      ("healthy", "logger", "filter", "handler", "observer")),
    *(("heartbeat_lifecycle", "connection_fault", fault) for fault in ("disconnect", "timeout")),
    *(("heartbeat_lifecycle", "commit_race", mode) for mode in ("local_loss", "db_transfer")),
    *(("heartbeat_lifecycle", "cleanup", mode) for mode in
      ("success", "failure", "exception", "interrupt", "exit", "signal")),
    *(("heartbeat_lifecycle", "error_isolation", sink) for sink in
      ("healthy", "logger", "filter", "handler", "observer")),
    *(("worker_t2", "delivery", outcome) for outcome in
      ("APPLIED", "ALREADY_APPLIED", "STOPPED_WAITING", "CANCELLED", "SUPERSEDED")),
    *(("worker_t2", "rollback", fault) for fault in
      ("reflector", "enqueue", "extra", "tampered_reason", "non_applied_jobs", "cross_case", "commit", "rollback")),
    *(("worker_t2", "t1_gap", status) for status in ("SUCCEEDED", "FAILED")),
    *(("worker_t2", "commit_recovery", outcome) for outcome in ("APPLIED", "STOPPED_WAITING")),
    *(("worker_t2", "metric", mode) for mode in
      ("first_stopped", "retry_stopped", "third_stopped", "cancelled", "superseded", "already", "applied", "exception")),
    *(("worker_t2", "zero_guard", mode) for mode in ("missing", "mismatch", "zero", "already", "insert_then_marker_failure")),
    *(("worker_t2", "sink_isolation", mode + "_" + sink)
      for mode in ("metric", "failure", "db_retry") for sink in ("filter", "handler")),
    *(("worker_t2", "recovery", mode) for mode in ("exhausted", "next_job", "concurrent", "exhausted_next_job")),
    *(("worker_core", "logger_isolation", scenario + "_" + sink)
      for scenario in ("started", "completed", "claim_db", "terminal_db") for sink in ("filter", "handler")),
    *(("worker_core", "failure", mode) for mode in ("unknown", "module", "exception", "invalid")),
    *(("worker_core", "terminal_unknown_commit", status) for status in ("SUCCEEDED", "FAILED")),
    *(("worker_core", "correlation", mode) for mode in ("max_job_id", "path_id")),
)

JOB_PARAMETERS = (
    *(("jobs", "read_states", state) for state in
      ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "STALE", "CANCELLED")),
    ("jobs", "enqueue_duplicate", "separate_batch"),
    ("jobs", "enqueue_duplicate", "same_batch"),
    ("jobs", "claim_eligibility", "past"),
    ("jobs", "claim_eligibility", "equal"),
    ("jobs", "claim_eligibility", "future"),
    ("jobs", "claim_empty", "empty"),
    ("jobs", "claim_empty", "all_locked"),
    ("jobs", "finish_targets", "SUCCEEDED"),
    ("jobs", "finish_targets", "FAILED"),
    ("jobs", "finish_targets", "CANCELLED"),
    ("jobs", "finish_guard", "missing"),
    ("jobs", "finish_guard", "other_owner"),
    ("jobs", "finish_guard", "QUEUED"),
    ("jobs", "finish_guard", "SUCCEEDED"),
    ("jobs", "finish_guard", "FAILED"),
    ("jobs", "finish_guard", "CANCELLED"),
    ("jobs", "finish_guard", "STALE"),
    ("jobs", "finish_rejection", "STALE"),
    ("jobs", "finish_rejection", "QUEUED"),
    ("jobs", "finish_rejection", "RUNNING"),
    ("jobs", "finish_rejection", "UNKNOWN"),
    ("jobs", "claim_unknown_commit", "recovered"),
    ("jobs", "claim_unknown_commit", "token"),
    ("jobs", "claim_unknown_commit", "owner"),
    ("jobs", "claim_unknown_commit", "terminal"),
    ("jobs", "claim_unknown_commit", "expired"),
    ("jobs", "claim_unknown_commit", "missing"),
    ("jobs", "finish_race", "SUCCEEDED_commit"),
    ("jobs", "finish_race", "SUCCEEDED_rollback"),
    ("jobs", "finish_race", "FAILED_commit"),
    ("jobs", "finish_race", "FAILED_rollback"),
    ("jobs", "finish_race", "CANCELLED_commit"),
    ("jobs", "finish_race", "CANCELLED_rollback"),
    ("jobs", "claim_rc_finish", "FAILED"),
    ("jobs", "claim_rc_finish", "CANCELLED"),
    ("api", "utc_session", "fresh"),
    ("api", "utc_session", "reused"),
    ("api", "utc_session", "replacement"),
    ("worker", "utc_session", "fresh"),
    ("worker", "utc_session", "reused"),
    ("worker", "utc_session", "replacement"),
)


def test_actual_report_rejects_each_missing_migration_check(mysql_schema_url, tmp_path):
    report_path = tmp_path / "mysql.json"
    junit_path = tmp_path / "mysql.xml"
    env = dict(os.environ, DAESINGO_MYSQL_URL=mysql_schema_url.render_as_string(hide_password=False),
               DAESINGO_REQUIRE_MYSQL="1", PYTHONDONTWRITEBYTECODE="1",
               RT12_CATALOG_EVIDENCE=str(tmp_path / 'event-catalog.json'))
    # Exclude this test to avoid recursion. Use a separate disposable base schema
    # so legacy Case initialization cannot alter the parent suite's database.
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-m", "pytest", "tests/e2e_runtime", "tests/api", "tests/recording/test_recording_repository_mysql.py", "tests/recording/test_recording_repository_compatibility_mysql.py", "tests/common/db/integration", "tests/common/jobs", "tests/common/usage",
         "tests/worker/test_worker_mysql.py", "tests/worker/test_produced_store_mysql.py", "tests/worker/test_reflection_mysql.py",
         "tests/worker/test_heartbeat_mysql.py",
         "tests/worker/test_cancel_checkpoint_mysql.py",
         "tests/worker/test_sweep_worker_mysql.py",
         "tests/worker/test_redelivery_mysql.py",
         "tests/worker/test_usage_worker_mysql.py",
         "tests/worker/test_usage_reconciliation_worker_mysql.py",
         "tests/case/test_store_mysql.py", "tests/case/test_case_repository_contract.py",
         "--ignore=tests/common/db/integration/test_migration_gate.py", "-m", "mysql", "-q",
          "-p", "no:cacheprovider", "-p", "tests.observability_capture", f"--basetemp={tmp_path / 'child'}",
         f"--mysql-report={report_path}", f"--junitxml={junit_path}"],
        # This repeats the complete MySQL inventory, including migrations for
        # each fixture. Allow slower local servers without relaxing the gate.
        env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=900,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("real_report_gate", ROOT / "scripts/check_mysql_test_report.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    gate.validate_report(report)
    gate.validate_junit(junit_path, report)
    from daesingo.common.logging.catalog import EVENTS
    catalog = json.loads((tmp_path / 'event-catalog.json').read_text(encoding='utf-8'))
    assert catalog['violations'] == 0
    assert set(EVENTS) <= set(catalog['events']), 'catalog events not exercised by actual emitters'
    for role, scenario in [*( ("migration", scenario) for scenario in MIGRATION_CHECKS),
                           ("jobs", "schema"), ("jobs", "enqueue_rollback"),
                           ("jobs", "enqueue_duplicate"), ("jobs", "read_contract"), ("jobs", "read_states"),
                           *LIFECYCLE_CHECKS, *WORKER_CHECKS, *USAGE_CHECKS, *TIMESTAMP_CHECKS, *COMMAND_CHECKS, *CANCEL_API_CHECKS, *ASYNC_E2E_CHECKS, *START_ANALYSIS_CHECKS, *RECORDING_CHECKS, *UPLOAD_CHECKS, *PRODUCED_CHECKS, *FRAME_CHECKS, *ASSET_CHECKS, *OBSERVABILITY_CHECKS,
                           *((role, scenario) for role, scenario, parameter in (*API_HEALTH_PARAMETERS, *API_CASES_VIEW_PARAMETERS))]:
        removed = {item["nodeid"] for item in report["collected"]
                   if any(c["role"] == role and c["scenario"] == scenario for c in item.get("checks", []))}
        assert removed, scenario
        broken = omit_evidence_nodes(report, removed)
        with pytest.raises(ValueError, match="role/scenario"):
            gate.validate_report(broken)

    # Keep every other parameter in place. A family-level set check would
    # incorrectly accept the "all" mutation, including deletion from JUnit.
    mutations = []
    for role, scenario, parameter in (*JOB_PARAMETERS, *WORKER_PARAMETERS, *USAGE_PARAMETERS, *API_HEALTH_PARAMETERS, *API_CASES_VIEW_PARAMETERS, *TIMESTAMP_PARAMETERS, *COMMAND_PARAMETERS, *CANCEL_API_PARAMETERS, *ASYNC_E2E_PARAMETERS, *START_ANALYSIS_PARAMETERS, *RECORDING_PARAMETERS, *UPLOAD_PARAMETERS, *PRODUCED_PARAMETERS, *FRAME_PARAMETERS, *ASSET_PARAMETERS, *OBSERVABILITY_PARAMETERS):
        check = {"role": role, "scenario": scenario, "parameter": parameter}
        entry, = (n for n in report["collected"] if check in n.get("checks", []))
        node = entry["nodeid"]
        layers = ("collection", "selection", "setup", "call", "teardown", "all", "junit")
        if role in ("timestamp_order", "api_cancel", "async_e2e", "api_start_analysis", "recording", "api_upload", "produced_store", "api_frame", "api_asset", "observability"):
            layers += ("skip", "xfail", "failure", "junit_skip", "junit_failure", "junit_error")
        for layer in layers:
            broken = copy_parameter_evidence(report, node)
            if layer in {"collection", "all"}:
                broken["collected"] = [n for n in broken["collected"] if n["nodeid"] != node]
            if layer in {"selection", "all"}:
                broken["selected"].remove(node)
            if layer in {"setup", "call", "teardown", "all"}:
                broken["reports"] = [r for r in broken["reports"]
                                     if r["nodeid"] != node or (layer != "all" and r["when"] != layer)]
            if layer in {"skip", "xfail", "failure"}:
                phase, = (r for r in broken["reports"] if r["nodeid"] == node and r["when"] == "call")
                if layer == "xfail":
                    phase["xfail"] = True
                else:
                    phase["outcome"] = "skipped" if layer == "skip" else "failed"
            def write_mutation_junit():
                xml = ElementTree.parse(junit_path)
                if layer in {"junit", "all"}:
                    matches = 0
                    for parent in xml.iter():
                        for case in list(parent):
                            if case.tag == "testcase" and (case.get("classname"), case.get("name")) == tuple(entry["junit"]):
                                parent.remove(case)
                                matches += 1
                    assert matches == 1
                if layer.startswith("junit_"):
                    matches = [c for c in xml.findall(".//testcase")
                               if (c.get("classname"), c.get("name")) == tuple(entry["junit"])]
                    assert len(matches) == 1
                    ElementTree.SubElement(matches[0], {"junit_skip": "skipped",
                        "junit_failure": "failure", "junit_error": "error"}[layer])
                path = tmp_path / f"{scenario}-{parameter}-{layer}.xml"
                xml.write(path, encoding="utf-8")
                return path

            # Materialize every mutated XML (including combined "all") and
            # retain its matching assertions. Passing XML is only needed if
            # JSON unexpectedly survives validation; keep that fallback strict.
            mutation_junit = (write_mutation_junit()
                if layer in {"junit", "all"} or layer.startswith("junit_") else None)
            with pytest.raises(ValueError):
                gate.validate_report(broken)
                if mutation_junit is None:
                    mutation_junit = write_mutation_junit()
                gate.validate_junit(mutation_junit, broken)
            mutations.append({"role": role, "scenario": scenario, "parameter": parameter,
                              "layer": layer, "rejected": True})
    assert len(mutations) == (len(JOB_PARAMETERS) + len(WORKER_PARAMETERS) + len(USAGE_PARAMETERS) + len(API_HEALTH_PARAMETERS) + len(API_CASES_VIEW_PARAMETERS) + len(COMMAND_PARAMETERS)) * 7 + (len(TIMESTAMP_PARAMETERS) + len(CANCEL_API_PARAMETERS) + len(ASYNC_E2E_PARAMETERS) + len(START_ANALYSIS_PARAMETERS) + len(RECORDING_PARAMETERS) + len(UPLOAD_PARAMETERS) + len(PRODUCED_PARAMETERS) + len(FRAME_PARAMETERS) + len(ASSET_PARAMETERS) + len(OBSERVABILITY_PARAMETERS)) * 13
    (tmp_path / "parameter-mutations.json").write_text(json.dumps(mutations, indent=2), encoding="utf-8")

    # Complete passing nodes with absent RT-08(d)/RT-09/START_ANALYSIS metadata must also fail.
    # Mutate the actual report, retaining its original JSON/JUnit untouched.
    omissions = []
    for role, scenario, parameter in (*CANCEL_API_PARAMETERS, *ASYNC_E2E_PARAMETERS, *START_ANALYSIS_PARAMETERS, *RECORDING_PARAMETERS, *UPLOAD_PARAMETERS, *PRODUCED_PARAMETERS, *FRAME_PARAMETERS, *ASSET_PARAMETERS, *OBSERVABILITY_PARAMETERS):
        expected = {"role": role, "scenario": scenario, "parameter": parameter}
        original_entry, = (n for n in report["collected"] if expected in n.get("checks", []))
        for field in ("role", "scenario", "parameter", "all_metadata"):
            broken = copy_parameter_evidence(report, original_entry["nodeid"])
            entry, = (n for n in broken["collected"] if expected in n.get("checks", []))
            if field == "all_metadata":
                entry["checks"] = []
            else:
                check, = (c for c in entry["checks"] if c == expected)
                del check[field]
            with pytest.raises(ValueError):
                gate.validate_report(broken)
            omissions.append({"identity": [role, scenario, parameter], "field": field, "rejected": True})
    for role, scenario in (*CANCEL_API_CHECKS, *ASYNC_E2E_CHECKS, *START_ANALYSIS_CHECKS, *RECORDING_CHECKS, *UPLOAD_CHECKS, *PRODUCED_CHECKS, *FRAME_CHECKS, *ASSET_CHECKS, *OBSERVABILITY_CHECKS):
        removed = {n["nodeid"] for n in report["collected"] if any(
            c.get("role") == role and c.get("scenario") == scenario for c in n.get("checks", []))}
        assert removed
        identities = {tuple(n["junit"]) for n in report["collected"] if n["nodeid"] in removed}
        broken = omit_evidence_nodes(report, removed)
        xml = ElementTree.parse(junit_path)
        count = 0
        for parent in xml.iter():
            for case in list(parent):
                if case.tag == "testcase" and (case.get("classname"), case.get("name")) in identities:
                    parent.remove(case)
                    count += 1
        assert count == len(removed)
        mutation_junit = tmp_path / f"{role}-family-{scenario}.xml"
        xml.write(mutation_junit, encoding="utf-8")
        with pytest.raises(ValueError):
            gate.validate_report(broken)
            gate.validate_junit(mutation_junit, broken)
        omissions.append({"identity": [role, scenario], "field": "all_family_evidence", "rejected": True})
    assert len(omissions) == (len(CANCEL_API_PARAMETERS) + len(ASYNC_E2E_PARAMETERS) + len(START_ANALYSIS_PARAMETERS) + len(RECORDING_PARAMETERS) + len(UPLOAD_PARAMETERS) + len(PRODUCED_PARAMETERS) + len(FRAME_PARAMETERS) + len(ASSET_PARAMETERS) + len(OBSERVABILITY_PARAMETERS)) * 4 + len(CANCEL_API_CHECKS) + len(ASYNC_E2E_CHECKS) + len(START_ANALYSIS_CHECKS) + len(RECORDING_CHECKS) + len(UPLOAD_CHECKS) + len(PRODUCED_CHECKS) + len(FRAME_CHECKS) + len(ASSET_CHECKS) + len(OBSERVABILITY_CHECKS)
    for role, filename in (("api_cancel", "cancel-omissions.json"), ("async_e2e", "async-e2e-omissions.json"),
                           ("api_start_analysis", "start-analysis-omissions.json"), ("recording", "recording-omissions.json"), ("api_upload", "upload-omissions.json"), ("produced_store", "produced-omissions.json"), ("api_frame", "frame-omissions.json"), ("api_asset", "asset-omissions.json"), ("observability", "observability-omissions.json")):
        subset = [item for item in omissions if item["identity"][0] == role]
        (tmp_path / filename).write_text(json.dumps(subset, indent=2), encoding="utf-8")
