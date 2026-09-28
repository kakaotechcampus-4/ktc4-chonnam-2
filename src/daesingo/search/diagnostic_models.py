"""Local experiment artifacts; not exported by the Search public facade."""

from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from .decision_trace import DiagnosticCoarseResponse, DiagnosticFineResponse
from .schemas import CoarseResponse, FineResponse, WireModel
from .scope import VisualEventType
from .usage import ProviderUsage


class DiagnosticProfile(StrEnum):
    P3 = "p3"
    DIAGNOSTIC = "diagnostic-v1"
    DIAGNOSTIC_UNCERTAIN = "diagnostic-uncertain-v1"
    DIAGNOSTIC_HANDOFF = "diagnostic-handoff-v1"


class DiagnosticCase(WireModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source: Path
    duration_sec: float = Field(gt=0, le=60, allow_inf_nan=False)
    event_types: tuple[VisualEventType, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_events(self) -> Self:
        if len(set(self.event_types)) != len(self.event_types):
            raise ValueError("duplicate event types")
        return self


class DiagnosticManifest(WireModel):
    cases: tuple[DiagnosticCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> Self:
        keys = [case.case_id for case in self.cases]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate case ids")
        return self


type ModelResponse = (
    DiagnosticCoarseResponse | DiagnosticFineResponse | CoarseResponse | FineResponse
)


class DiagnosticCall(WireModel):
    stage: Literal["COARSE", "FINE"]
    candidate_index: int | None = None
    event_type: VisualEventType | None = None
    invocation_started: bool
    status: Literal["SUCCEEDED", "FAILED"]
    issue_codes: tuple[str, ...] = ()
    prompt_version: str
    prompt_fingerprint: str
    prepared_origin_start_sec: float | None = None
    prepared_origin_end_sec: float | None = None
    prepared_duration_sec: float | None = None
    prepared_media_bytes: int | None = None
    prepared_media_sha256: str | None = None
    latency_ms: int | None = None
    usage: ProviderUsage | None = None
    cost_usd: str | None = None
    response: ModelResponse | None = None


class DiagnosticCaseResult(WireModel):
    case_id: str
    input_sha256: str
    duration_sec: float
    input_issue_code: str | None = None
    calls: tuple[DiagnosticCall, ...]


class DiagnosticContext(WireModel):
    run_id: str
    created_at: str
    mode: Literal["LIVE", "FIXTURE"]
    profile: DiagnosticProfile
    git_sha: str
    implementation_fingerprint: str
    model: str
    config_fingerprint: str
    coarse_fps: float
    fine_fps: float
    coarse_max_height: int = 360
    fine_max_height: int = 720
    fine_padding_sec: float
    reasoning_effort: str
    max_retries: Literal[0] = 0
    timeout_sec: float
    input_usd_per_million: float
    output_usd_per_million: float


class DiagnosticRunResult(WireModel):
    schema_version: Literal["search-decision-trace/v1"] = "search-decision-trace/v1"
    context: DiagnosticContext
    cases: tuple[DiagnosticCaseResult, ...]
