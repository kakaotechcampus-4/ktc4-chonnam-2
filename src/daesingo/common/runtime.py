"""Canonical JobExecution and UsageRecord validation helpers.

This module owns contract enforcement only.  Queue claiming, leases, and
heartbeats remain with the runtime implementation owner.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence


class RuntimeContractError(ValueError):
    """Raised when a common/runtime value violates its canonical contract."""


def _offset_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise RuntimeContractError(f"{field} must be an offset-aware RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeContractError(f"{field} must be an offset-aware RFC3339 string") from exc
    if parsed.utcoffset() is None:
        raise RuntimeContractError(f"{field} must include a UTC offset")
    return parsed


def validate_job_execution(execution: Mapping[str, Any]) -> None:
    required = {
        "execution_id",
        "job_id",
        "status",
        "attempt",
        "queued_at",
        "started_at",
        "ended_at",
        "produced",
        "failure_kind",
        "usage_refs",
    }
    missing = required.difference(execution)
    if missing:
        raise RuntimeContractError(f"JobExecution missing fields: {sorted(missing)}")
    status = execution["status"]
    if status not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "STALE"}:
        raise RuntimeContractError(f"unsupported JobExecution.status: {status!r}")
    if not isinstance(execution["attempt"], int) or execution["attempt"] < 1:
        raise RuntimeContractError("JobExecution.attempt must be >= 1")
    _offset_datetime(execution["queued_at"], field="JobExecution.queued_at")
    if status == "QUEUED" and execution["started_at"] is not None:
        raise RuntimeContractError("QUEUED JobExecution.started_at must be null")
    if status in {"QUEUED", "RUNNING"} and execution["ended_at"] is not None:
        raise RuntimeContractError(f"{status} JobExecution.ended_at must be null")
    if execution["started_at"] is not None:
        _offset_datetime(execution["started_at"], field="JobExecution.started_at")
    if execution["ended_at"] is not None:
        _offset_datetime(execution["ended_at"], field="JobExecution.ended_at")
    if not isinstance(execution["produced"], list) or not isinstance(execution["usage_refs"], list):
        raise RuntimeContractError("JobExecution produced/usage_refs must be arrays")


def validate_usage_record(record: Mapping[str, Any]) -> None:
    required = {
        "usage_id",
        "execution_ref",
        "run_ref",
        "case_id",
        "occurred_at",
        "provider_label",
        "operation",
        "token_usage",
        "processed_duration_sec",
        "latency_ms",
        "pricing_context",
        "cost",
    }
    missing = required.difference(record)
    if missing:
        raise RuntimeContractError(f"UsageRecord missing fields: {sorted(missing)}")
    _offset_datetime(record["occurred_at"], field="UsageRecord.occurred_at")
    token_usage = record["token_usage"]
    if token_usage is not None:
        if not isinstance(token_usage, Mapping) or set(token_usage) != {
            "input_tokens",
            "output_tokens",
            "total_tokens",
        }:
            raise RuntimeContractError("UsageRecord.token_usage must be null or the complete token object")
        if token_usage["total_tokens"] != token_usage["input_tokens"] + token_usage["output_tokens"]:
            raise RuntimeContractError("UsageRecord.total_tokens must equal input_tokens + output_tokens")
    if record["processed_duration_sec"] is not None and not isinstance(
        record["processed_duration_sec"], (int, float)
    ):
        raise RuntimeContractError("UsageRecord.processed_duration_sec must be numeric or null")
    if record["latency_ms"] is not None and not isinstance(record["latency_ms"], int):
        raise RuntimeContractError("UsageRecord.latency_ms must be an integer or null")
    pricing = record["pricing_context"]
    cost = record["cost"]
    if not isinstance(pricing, Mapping) or not {"pricing_id", "unit"}.issubset(pricing):
        raise RuntimeContractError("UsageRecord.pricing_context is incomplete")
    if not isinstance(cost, Mapping) or not {"amount", "currency"}.issubset(cost):
        raise RuntimeContractError("UsageRecord.cost is incomplete")
    if cost["amount"] is not None:
        try:
            Decimal(cost["amount"])
        except Exception as exc:
            raise RuntimeContractError("UsageRecord.cost.amount must be a decimal string or null") from exc


def validate_execution_usage_links(
    executions: Sequence[Mapping[str, Any]], usage_records: Sequence[Mapping[str, Any]]
) -> None:
    execution_by_id = {execution.get("execution_id"): execution for execution in executions}
    usage_by_id = {record.get("usage_id"): record for record in usage_records}
    for execution in executions:
        validate_job_execution(execution)
        for usage_ref in execution["usage_refs"]:
            record = usage_by_id.get(usage_ref)
            if record is None:
                raise RuntimeContractError(f"JobExecution references missing UsageRecord: {usage_ref}")
            if record.get("execution_ref") != execution["execution_id"]:
                raise RuntimeContractError(f"UsageRecord {usage_ref} points to another execution")
    for record in usage_records:
        validate_usage_record(record)
        execution_ref = record["execution_ref"]
        if execution_ref is None:
            continue
        execution = execution_by_id.get(execution_ref)
        if execution is None:
            raise RuntimeContractError(f"UsageRecord points to missing JobExecution: {execution_ref}")
        if record["usage_id"] not in execution["usage_refs"]:
            raise RuntimeContractError(
                f"UsageRecord {record['usage_id']} is not linked back from JobExecution"
            )


def aggregate_usage(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate immutable usage rows without inventing unavailable token values."""

    for record in records:
        validate_usage_record(record)
    durations = [record["processed_duration_sec"] for record in records]
    duration_ms: int | float | None = None
    if durations and all(value is not None for value in durations):
        duration_decimal = sum(Decimal(str(value)) for value in durations) * 1000
        duration_ms = (
            int(duration_decimal)
            if duration_decimal == duration_decimal.to_integral_value()
            else float(duration_decimal)
        )

    latencies = [record["latency_ms"] for record in records]
    latency_ms = None
    if latencies and all(value is not None for value in latencies):
        latency_ms = sum(latencies)

    token_objects = [record["token_usage"] for record in records if record["token_usage"] is not None]
    token_usage = None
    if token_objects:
        token_usage = {
            key: sum(tokens[key] for tokens in token_objects)
            for key in ("input_tokens", "output_tokens", "total_tokens")
        }

    costs = [record["cost"] for record in records if record["cost"]["amount"] is not None]
    total_cost = None
    currencies = {cost["currency"] for cost in costs}
    if len(currencies) > 1:
        raise RuntimeContractError("usage rows with different currencies cannot be aggregated")
    if costs and len(currencies) == 1:
        total_cost = {
            "amount": format(sum(Decimal(cost["amount"]) for cost in costs), "f"),
            "currency": next(iter(currencies)),
        }
    return {
        "processed_duration_ms": duration_ms,
        "token_usage": token_usage,
        "latency_ms": latency_ms,
        "total_cost": total_cost,
    }
