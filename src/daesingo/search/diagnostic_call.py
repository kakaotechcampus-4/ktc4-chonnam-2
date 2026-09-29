"""Structured diagnostic calls and p3/observation profile routing."""

import time
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, assert_never

from pydantic import BaseModel

from .config import GeminiSearchConfig
from .decision_trace import (
    DiagnosticCoarseResponse,
    DiagnosticFineResponse,
)
from .diagnostic_models import (
    DiagnosticCall,
    DiagnosticCase,
    DiagnosticProfile,
)
from .diagnostic_prompts import (
    checklist_instruction,
    diagnostic_coarse_prompt,
    diagnostic_fine_prompt,
    handoff_fine_prompt,
    uncertain_fine_prompt,
    window_instruction,
)
from .execution import DeadlineExceededError, RunDeadline
from .media import (
    PreparedMedia,
)
from .media_contract import CoarseMediaPreparer
from .prompts import COARSE_PROMPT, PromptTemplate, fine_prompt_for
from .provider import (
    MediaSizeError,
    ProviderResult,
    RequestSizeError,
    StructuredInvocation,
)
from .schemas import CoarseCandidate, CoarseResponse, FineResponse
from .scope import VisualEventType
from .smoke_errors import ProviderApiError, ProviderPayloadError


class StructuredInvoker(Protocol):
    def invoke_structured[T: BaseModel](
        self, request: StructuredInvocation[T]
    ) -> ProviderResult[T]: ...


@dataclass(frozen=True, slots=True)
class DiagnosticDependencies:
    provider: StructuredInvoker
    media: CoarseMediaPreparer
    config: GeminiSearchConfig
    profile: DiagnosticProfile
    timeout_sec: float = 180.0
    clock: Callable[[], float] = time.monotonic


@dataclass(frozen=True, slots=True)
class DiagnosticSession:
    case: DiagnosticCase
    dependencies: DiagnosticDependencies
    deadline: RunDeadline


@dataclass(frozen=True, slots=True)
class FineInput:
    candidate: CoarseCandidate
    index: int
    prepared: PreparedMedia


@dataclass(frozen=True, slots=True)
class CallSpec[T: BaseModel]:
    template: PromptTemplate
    prompt: str
    response_model: type[T]
    stage: Literal["COARSE", "FINE"]
    candidate_index: int | None = None
    event_type: VisualEventType | None = None


def _call[T: BaseModel](
    spec: CallSpec[T],
    prepared: PreparedMedia,
    session: DiagnosticSession,
) -> DiagnosticCall:
    deps, deadline = session.dependencies, session.deadline
    metadata = {
        "stage": spec.stage,
        "candidate_index": spec.candidate_index,
        "event_type": spec.event_type,
        "prompt_version": spec.template.version,
        "prompt_fingerprint": spec.template.fingerprint,
        "prepared_origin_start_sec": prepared.origin_start_sec,
        "prepared_origin_end_sec": prepared.origin_end_sec,
        "prepared_duration_sec": prepared.duration_sec,
        "prepared_media_bytes": prepared.byte_size,
    }
    started = False
    try:
        deadline.check()
        with prepared.path.open("rb") as stream:
            metadata["prepared_media_sha256"] = hashlib.file_digest(
                stream, "sha256"
            ).hexdigest()
        deadline.check()
        started = True
        result = deps.provider.invoke_structured(
            StructuredInvocation(
                prepared,
                spec.prompt,
                spec.response_model,
                deadline.remaining_sec(),
            )
        )
    except (
        ProviderPayloadError,
        ProviderApiError,
        DeadlineExceededError,
        MediaSizeError,
        RequestSizeError,
    ) as error:
        match error:
            case ProviderPayloadError():
                code = "PROVIDER_PAYLOAD"
            case ProviderApiError():
                code = "PROVIDER_API"
            case DeadlineExceededError():
                code = "RUN_DEADLINE_EXCEEDED"
            case MediaSizeError() | RequestSizeError():
                code = "REQUEST_SIZE"
                started = False
            case unreachable:
                assert_never(unreachable)
        return DiagnosticCall.model_validate(
            dict(
                metadata,
                invocation_started=started,
                status="FAILED",
                issue_codes=(code,),
            )
        )
    rates = deps.config
    cost = None
    if rates.input_usd_per_million > 0 and rates.output_usd_per_million > 0:
        cost = result.usage.cost_with_rates(
            rates.input_usd_per_million, rates.output_usd_per_million
        )
    return DiagnosticCall.model_validate(
        dict(
            metadata,
            invocation_started=True,
            status="SUCCEEDED",
            response=result.response,
            usage=result.usage,
            latency_ms=result.latency_ms,
            cost_usd=str(cost) if cost is not None else None,
        )
    )


def _coarse_spec(case: DiagnosticCase, profile: DiagnosticProfile) -> CallSpec:
    values = {
        "event_types": ", ".join(event.value for event in case.event_types),
        "duration_sec": case.duration_sec,
    }
    match profile:
        case DiagnosticProfile.P3:
            return CallSpec(
                COARSE_PROMPT, COARSE_PROMPT.render(**values), CoarseResponse, "COARSE"
            )
        case (
            DiagnosticProfile.DIAGNOSTIC
            | DiagnosticProfile.DIAGNOSTIC_UNCERTAIN
            | DiagnosticProfile.DIAGNOSTIC_HANDOFF
        ):
            template = diagnostic_coarse_prompt()
            return CallSpec(
                template,
                template.render(
                    **values, review_windows=window_instruction(case.duration_sec)
                ),
                DiagnosticCoarseResponse,
                "COARSE",
            )
        case unreachable:
            assert_never(unreachable)


def _fine_spec(probe: FineInput, profile: DiagnosticProfile) -> CallSpec:
    candidate, index, prepared = probe.candidate, probe.index, probe.prepared
    event = candidate.event_type
    values: dict[str, object] = {
        "event_type": event.value,
        "target_hint": "없음",
        "start_sec": prepared.origin_start_sec,
        "end_sec": prepared.origin_end_sec,
    }
    match profile:
        case DiagnosticProfile.P3:
            template = fine_prompt_for(event)
            return CallSpec(
                template, template.render(**values), FineResponse, "FINE", index, event
            )
        case DiagnosticProfile.DIAGNOSTIC:
            return _diagnostic_fine(diagnostic_fine_prompt(event), values, index, event)
        case DiagnosticProfile.DIAGNOSTIC_UNCERTAIN:
            return _diagnostic_fine(uncertain_fine_prompt(event), values, index, event)
        case DiagnosticProfile.DIAGNOSTIC_HANDOFF:
            # 운영 CandidateEvent.summary와 같은 문자열을 넘긴다(coarse._candidate).
            handoff = {
                "coarse_observation": "; ".join(candidate.observed) or "관찰 사실 없음",
                "coarse_at_offset_sec": max(
                    0.0, candidate.at_sec - prepared.origin_start_sec
                ),
            }
            return _diagnostic_fine(
                handoff_fine_prompt(event), values | handoff, index, event
            )
        case unreachable:
            assert_never(unreachable)


def _diagnostic_fine(
    template: PromptTemplate,
    values: dict[str, object],
    index: int,
    event: VisualEventType,
) -> CallSpec:
    return CallSpec(
        template,
        template.render(**values, criteria=checklist_instruction(event)),
        DiagnosticFineResponse,
        "FINE",
        index,
        event,
    )
