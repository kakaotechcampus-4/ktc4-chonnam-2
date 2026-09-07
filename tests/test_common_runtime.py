from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daesingo.common import (  # noqa: E402
    RuntimeContractError,
    aggregate_usage,
    sanitize_log_event,
    validate_execution_usage_links,
    validate_job_execution,
    validate_usage_record,
)


def load(path: str):
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


class CommonRuntimeContractTests(unittest.TestCase):
    def test_mock_execution_usage_links_are_bidirectional(self) -> None:
        for tag in ("happy_001", "partial_001"):
            with self.subTest(tag=tag):
                validate_execution_usage_links(
                    load(f"data/mock/case/job_executions.{tag}.json"),
                    load(f"data/mock/case/usage_records.{tag}.json"),
                )

    def test_search_usage_aggregate_matches_analysis_run(self) -> None:
        for tag in ("happy_001", "partial_001"):
            with self.subTest(tag=tag):
                usage = load(f"data/mock/case/usage_records.{tag}.json")
                run = load(f"data/mock/search/analysis_run.{tag}.json")
                rows = [row for row in usage if row["usage_id"] in run["usage_refs"]]
                self.assertEqual(aggregate_usage(rows), run["usage_summary"])

    def test_incomplete_token_usage_is_rejected(self) -> None:
        record = deepcopy(load("data/mock/case/usage_records.happy_001.json")[0])
        record["token_usage"].pop("output_tokens")
        with self.assertRaises(RuntimeContractError):
            validate_usage_record(record)

    def test_queued_execution_has_null_timestamps(self) -> None:
        execution = {
            "execution_id": "exec_q1",
            "job_id": "job_q1",
            "status": "QUEUED",
            "attempt": 1,
            "queued_at": "2026-09-07T10:00:00+09:00",
            "started_at": None,
            "ended_at": None,
            "produced": [],
            "failure_kind": None,
            "usage_refs": [],
        }
        validate_job_execution(execution)
        execution["started_at"] = "2026-09-07T10:00:01+09:00"
        with self.assertRaises(RuntimeContractError):
            validate_job_execution(execution)

    def test_mixed_currency_aggregate_fails_closed(self) -> None:
        records = deepcopy(load("data/mock/case/usage_records.happy_001.json")[:2])
        records[1]["cost"] = {"amount": "1.00", "currency": "USD"}
        with self.assertRaises(RuntimeContractError):
            aggregate_usage(records)

    def test_masked_log_does_not_retain_sensitive_values(self) -> None:
        event = {
            "event": "evidence.assembled",
            "vehicle_number": "12가 3476",
            "gps": {"lat": 37.3595, "lon": 127.1052},
            "user_hint": "미금역 3번 출구에서 본 차량",
            "message": "plate 12가3476 near 37.3595, 127.1052",
            "case_id": "case_happy_001",
        }
        sanitized = sanitize_log_event(event)
        text = json.dumps(sanitized, ensure_ascii=False)
        self.assertNotIn("12가 3476", text)
        self.assertNotIn("12가3476", text)
        self.assertNotIn("37.3595", text)
        self.assertNotIn("127.1052", text)
        self.assertNotIn("미금역 3번 출구", text)
        self.assertEqual(sanitized["case_id"], "case_happy_001")


if __name__ == "__main__":
    unittest.main()
