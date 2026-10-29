"""One public Readout call, with planned usage identity and T1-owned products."""
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from daesingo import readout
from daesingo.readout.contracts import InputRef
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.produced import ProducedObject
from daesingo.common.usage.port import UsageStateError
from daesingo.worker.registry import KindRegistry


@dataclass(frozen=True)
class ReadoutInput:
    case_id: str
    candidate_id: str
    generation_job_id: str
    incident_clip_ref: str


@dataclass(frozen=True)
class ReadoutSession:
    provider: object
    processed_duration_sec: float | None


def readout_registry(*, load, provider_factory=None):
    if provider_factory is None:
        return KindRegistry({})

    def invoke(context):
        context.checkpoint()
        data = load(context)
        context.checkpoint()
        if context.usage_sink is None:
            raise UsageStateError()
        with provider_factory(data) as session:
            context.checkpoint()
            # Never permit the public API's fixture fallback in production.
            if session.provider is None:
                raise ValueError("explicit Readout provider required")
            request = readout.ReadRequest(case_id=data.case_id, candidate_id=data.candidate_id,
                input_ref=InputRef(incident_clip_ref=data.incident_clip_ref, source_profile="readout-native",
                    provenance="SOURCE_DERIVED_INCIDENT_CLIP"))
            run_id = "rr_" + uuid4().hex
            plate = context.kind == "PLATE_READ"
            pricing = {"pricing_id": "local-2026-09", "unit": "per_second"}
            usage_id = context.usage_sink.begin("READOUT_PLATE" if plate else "READOUT_OVERLAY_TIME",
                "ocr-local", pricing, run_ref={"kind": "readout_run", "ref": run_id})
            context.checkpoint()
            # No Runtime/input/checkpoint/persistence error is classified as a
            # Readout failure. Only the returned Run carries that meaning.
            capability = readout.read_plate if plate else readout.read_overlay_time
            run, result = capability(request, provider=session.provider, run_id=run_id)
            if run.run_id != run_id or run.operation != context.kind:
                raise ValueError("Readout result binding mismatch")
            failed = run.outcome == "FAILED"
            latency = None if run.ended_at is None else round((
                datetime.fromisoformat(run.ended_at) - datetime.fromisoformat(run.started_at)).total_seconds() * 1000)
            context.usage_sink.finish(usage_id, token_usage=None,
                processed_duration_sec=session.processed_duration_sec, latency_ms=latency,
                pricing_context=pricing, cost={"amount": "0", "currency": "KRW"},
                outcome="FAILED" if failed else "SUCCEEDED", failure_kind="READOUT_INFRA" if failed else None)
            context.checkpoint()
            terminal = HandlerResult(status="FAILED" if failed else "SUCCEEDED",
                failure_kind="READOUT_INFRA" if failed else None,
                objects=(ProducedObject(kind="readout_run", ref=run_id, payload={
                    "readout_run": run.to_dict(),
                    "plate_readout" if plate else "overlay_time_readout": None if result is None else result.to_dict(),
                }),))
        context.checkpoint()
        # T1 persists the Run before existing reconciliation finalizes usage.
        return terminal

    return KindRegistry({"PLATE_READ": invoke, "OVERLAY_TIME_READ": invoke})
