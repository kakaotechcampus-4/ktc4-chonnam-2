"""Bounded local Coarse/Fine probe, with no public VisualEvidence construction."""

import hashlib
from typing import Literal


from .decision_trace import (
    DiagnosticCoarseResponse,
    DiagnosticFineResponse,
    coarse_trace_issues,
    fine_trace_issues,
)
from .diagnostic_models import (
    DiagnosticCall,
    DiagnosticCase,
    DiagnosticCaseResult,
)
from .execution import DeadlineExceededError, RunDeadline
from .media import (
    ByteSizeMismatchError,
    FfmpegError,
    FfprobeError,
    MediaInput,
    MediaTooLargeError,
    MissingFfmpegError,
    SourceTooLargeError,
)
from .schemas import CoarseCandidate, CoarseResponse, FineResponse
from .scope import VisualEventType


from .diagnostic_call import (
    DiagnosticDependencies,
    DiagnosticSession,
    FineInput,
    _call,
    _coarse_spec,
    _fine_spec,
)


def _coarse(session: DiagnosticSession) -> DiagnosticCall:
    case, deps, deadline = session.case, session.dependencies, session.deadline
    with case.source.open("rb") as stream:
        media = MediaInput(stream, "video/mp4", case.source.stat().st_size)
        with deps.media.prepare_coarse(media, deadline) as prepared:
            if abs(prepared.origin_end_sec - case.duration_sec) > 0.25:
                return DiagnosticCall(
                    stage="COARSE",
                    invocation_started=False,
                    status="FAILED",
                    issue_codes=("DURATION_MISMATCH",),
                    prompt_version="",
                    prompt_fingerprint="",
                )
            call = _call(_coarse_spec(case, deps.profile), prepared, session)
            if isinstance(call.response, DiagnosticCoarseResponse):
                call = call.model_copy(
                    update={
                        "issue_codes": coarse_trace_issues(
                            call.response, case.event_types, case.duration_sec
                        )
                    }
                )
            return call


def _fine(
    candidate: CoarseCandidate, index: int, session: DiagnosticSession
) -> DiagnosticCall:
    case, deps, deadline = session.case, session.dependencies, session.deadline
    if (
        not (
            0 <= candidate.span.start_sec < candidate.span.end_sec <= case.duration_sec
        )
        or candidate.event_type not in case.event_types
    ):
        return DiagnosticCall(
            stage="FINE",
            candidate_index=index,
            event_type=candidate.event_type,
            invocation_started=False,
            status="FAILED",
            issue_codes=("CANDIDATE_OUT_OF_BOUNDS",),
            prompt_version="",
            prompt_fingerprint="",
        )
    start = max(0.0, candidate.span.start_sec - deps.config.fine_padding_sec)
    end = min(case.duration_sec, candidate.span.end_sec + deps.config.fine_padding_sec)
    with case.source.open("rb") as stream:
        media = MediaInput(stream, "video/mp4", case.source.stat().st_size)
        with deps.media.prepare_fine(media, start, end, deadline) as prepared:
            call = _call(
                _fine_spec(FineInput(candidate, index, prepared), deps.profile),
                prepared,
                session,
            )
            issues: list[str] = []
            response = call.response
            if isinstance(response, FineResponse):
                bound_ms = round(
                    min(
                        prepared.duration_sec,
                        prepared.origin_end_sec - prepared.origin_start_sec,
                    )
                    * 1000
                )
                if any(
                    fact.at_offset_ms is not None and fact.at_offset_ms > bound_ms
                    for fact in response.temporal_facts
                ):
                    issues.append("RESPONSE_TIME_OUT_OF_BOUNDS")
                if (
                    response.visual_event_type is not None
                    and response.visual_event_type is not candidate.event_type
                ):
                    issues.append("RESPONSE_EVENT_TYPE_MISMATCH")
                if isinstance(response, DiagnosticFineResponse):
                    issues.extend(
                        fine_trace_issues(response, candidate.event_type, bound_ms)
                    )
            return call.model_copy(
                update={"issue_codes": call.issue_codes + tuple(issues)}
            )


def run_case(
    case: DiagnosticCase, deps: DiagnosticDependencies
) -> DiagnosticCaseResult:
    deadline = RunDeadline(deps.clock, round(deps.timeout_sec * 1000))
    hasher = hashlib.sha256()
    try:
        with case.source.open("rb") as stream:
            while chunk := stream.read(65536):
                deadline.check()
                hasher.update(chunk)
    except (OSError, DeadlineExceededError):
        return DiagnosticCaseResult(
            case_id=case.case_id,
            input_sha256="",
            duration_sec=case.duration_sec,
            input_issue_code="SOURCE_UNAVAILABLE_OR_DEADLINE",
            calls=(),
        )
    session = DiagnosticSession(case, deps, deadline)
    try:
        calls = [_coarse(session)]
    except DeadlineExceededError:
        calls = [_failed_media_call("COARSE", "RUN_DEADLINE_EXCEEDED")]
    except MEDIA_ERRORS:
        calls = [_failed_media_call("COARSE", "MEDIA_PREPARATION")]
    response = calls[0].response
    if isinstance(response, (CoarseResponse, DiagnosticCoarseResponse)):
        candidates = sorted(
            response.candidates, key=lambda item: (-item.score, item.at_sec)
        )
        for index, candidate in enumerate(candidates):
            try:
                calls.append(_fine(candidate, index, session))
            except DeadlineExceededError:
                calls.append(
                    _failed_media_call(
                        "FINE",
                        "RUN_DEADLINE_EXCEEDED",
                        candidate=(index, candidate.event_type),
                    )
                )
            except MEDIA_ERRORS:
                calls.append(
                    _failed_media_call(
                        "FINE",
                        "MEDIA_PREPARATION",
                        candidate=(index, candidate.event_type),
                    )
                )
    return DiagnosticCaseResult(
        case_id=case.case_id,
        input_sha256=hasher.hexdigest(),
        duration_sec=case.duration_sec,
        calls=tuple(calls),
    )


MEDIA_ERRORS = (
    OSError,
    ByteSizeMismatchError,
    FfmpegError,
    FfprobeError,
    MediaTooLargeError,
    MissingFfmpegError,
    SourceTooLargeError,
)


def _failed_media_call(
    stage: Literal["COARSE", "FINE"],
    code: str,
    *,
    candidate: tuple[int, VisualEventType] | None = None,
) -> DiagnosticCall:
    return DiagnosticCall(
        stage=stage,
        candidate_index=candidate[0] if candidate else None,
        event_type=candidate[1] if candidate else None,
        invocation_started=False,
        status="FAILED",
        issue_codes=(code,),
        prompt_version="",
        prompt_fingerprint="",
    )
