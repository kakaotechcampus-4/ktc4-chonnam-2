"""Offline controls for the isolated capacity measurement harness."""
import importlib.util
from pathlib import Path

import pytest


def module():
    spec = importlib.util.spec_from_file_location("capacity_probe", Path(__file__).parents[2] / "scripts/recording_capacity_probe.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_failure_propagates_and_records_only_safe_diagnostics():
    probe = module()
    events = []
    with pytest.raises(ValueError):
        with probe.measure(events, "negative_control"):
            raise ValueError("private filename credential SQL")
    assert events[0]["status"] == "FAIL"
    assert events[0]["error_type"] == "ValueError"
    assert "private" not in str(events)
    assert events[0]["elapsed_sec"] >= 0


def test_stop_before_sdk_is_distinct_from_success():
    probe = module()
    events = []
    with pytest.raises(probe.StopBeforeSend):
        with probe.measure(events, "request"):
            raise probe.StopBeforeSend()
    assert events[0]["status"] == "STOP_BEFORE_SEND"


def test_input_identity_rejects_changed_size_without_full_hash(tmp_path):
    probe = module()
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="INPUT_IDENTITY_MISMATCH"):
        probe.verify_stat(source, {"bytes": 1, "mtime_ns": source.stat().st_mtime_ns})


def test_actual_driver_byte_hooks_restore_and_do_not_log_sql():
    probe = module()
    class Driver:
        encoding = "utf8"
        def _execute_command(self, command, sql):
            self._write_bytes(b"header" + sql.encode())
        def _write_bytes(self, data):
            return len(data)
    driver = Driver()
    original = driver._execute_command
    events = []
    with probe.driver_bytes(driver, events):
        driver._execute_command(3, "secret SQL")
    assert driver._execute_command == original
    assert events == [{"command": 3, "sql_bytes": 10}, {"write_buffer_bytes": 16}]
    assert "secret" not in str(events)


def test_sdk_normal_return_cannot_claim_stop_before_send():
    probe = module()
    with pytest.raises(RuntimeError, match="SDK_STOP_NOT_OBSERVED"):
        probe.require_sdk_stop({"request_guard": "FAIL"})
    probe.require_sdk_stop({"request_guard": "PASS_STOP_BEFORE_SEND"})


def test_sampler_stop_is_visible_to_host_supervisor(tmp_path):
    probe = module()
    marker = tmp_path / "abort"
    sampler = probe.Sampler(tmp_path, marker)
    sampler.trigger_stop("RESOURCE_BUDGET_STOP")
    assert marker.read_text() == "RESOURCE_BUDGET_STOP"
    with pytest.raises(RuntimeError, match="SAMPLER_OR_RESOURCE_STOP"):
        sampler.check()


def test_frame_diagnostics_count_coverage_gaps_without_payload_or_path():
    probe = module()
    summary = probe.frame_summary({"streams": [{"time_base": "1/30000"}], "frames": [
        {"best_effort_timestamp": 0, "duration": 1000},
        {"best_effort_timestamp": 2000, "duration": 1000}]})
    assert summary["frame_count"] == 2
    assert summary["coverage_discontinuities"] == 1
    assert summary["max_abs_gap_ticks"] == 1000
    assert summary["pts_strictly_increasing"] is True


def test_phase_journal_survives_failure_without_exception_message(tmp_path):
    import json
    probe = module()
    path = tmp_path / "events.jsonl"
    probe.JOURNAL = probe.Journal(path)
    with pytest.raises(ValueError):
        with probe.measure([], "negative_control"):
            raise ValueError("private payload credential SQL")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["kind"] == "phase_start"
    assert rows[-1]["kind"] == "phase_end"
    assert rows[-1]["event"]["status"] == "FAIL"
    assert "private" not in path.read_text()
