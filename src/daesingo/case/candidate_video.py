"""후보 영상 미리보기(`CANDIDATE_VIDEO_PREVIEW`) — 후보 카드에서 볼 짧은 clip의 상태 계산과 발주.

rank 1~3의 현재 세대 후보만 대상이다. 상태는 JobRecord · 고정 입력 · 반영 결과로 계산한다
(`NOT_REQUESTED` · `PREPARING` · `READY` · `FAILED` · `UNAVAILABLE`). 결정은
`docs/modules/case/decisions/candidate-video-preview.md`.
"""
from typing import Final, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from daesingo.case import jobs
from daesingo.case.analysis_start import fingerprint
from daesingo.case.domain import CANDIDATE_VIDEO_PREVIEW, Candidate, CaseAggregate

PREVIEW_KIND: Final = CANDIDATE_VIDEO_PREVIEW
MAX_PREVIEW_RANK: Final = 3
# Intermediate release identity: readers/workers stay enabled; no env override.
# Fixed final bb29d750 retains its original enabled issuance path.
# (bb29d750 = 고정 최종 배포 후보 커밋. 이 중간 호환 release에서는 신규 발주를 끈다 —
#  `docs/runtime/rt14-preview-bridge.md`)
PREVIEW_REQUESTS_ENABLED: Final = False


class PreviewRequestsDisabled(ValueError):
    """A bridge release must not persist a fresh preview job."""


class PreviewState(TypedDict):
    status: Literal["NOT_REQUESTED", "PREPARING", "READY", "FAILED", "UNAVAILABLE"]
    clip_ref: str | None


class PreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    incident_clip_ref: str = Field(min_length=1)


def eligible(case: CaseAggregate, candidate: Candidate) -> bool:
    return (case.current_generation_job_id() is not None
            and not case.search_awaited
            and candidate.rank is not None and 1 <= candidate.rank <= MAX_PREVIEW_RANK
            and not candidate.stale_revision and candidate.span is not None)


def preview_state(case: CaseAggregate, candidate: Candidate) -> PreviewState:
    if not eligible(case, candidate):
        return {"status": "UNAVAILABLE", "clip_ref": None}
    generation = case.current_generation_job_id()
    for record in reversed(case.job_records):
        source = case.observation_inputs.get(record["job_id"])
        if (record["kind"] != PREVIEW_KIND or source is None
                or source["candidate_id"] != candidate.candidate_id
                or source["generation_job_id"] != generation or source["span"] != candidate.span):
            continue
        if case.awaits_result(record["job_id"]):
            return {"status": "PREPARING", "clip_ref": None}
        outcome = case.observation_outcomes.get(record["job_id"], {})
        if outcome.get("status") == "SUCCEEDED":
            return {"status": "READY", "clip_ref": outcome["incident_clip_ref"]}
        return {"status": "FAILED", "clip_ref": None}
    return {"status": "NOT_REQUESTED" if PREVIEW_REQUESTS_ENABLED else "UNAVAILABLE", "clip_ref": None}


def request_preview(case: CaseAggregate, candidate: Candidate) -> None:
    if preview_state(case, candidate)["status"] in {"PREPARING", "READY"}:
        return
    if not PREVIEW_REQUESTS_ENABLED:
        raise PreviewRequestsDisabled("preview issuance disabled in compatibility release")
    span = candidate.span
    if span is None:
        raise ValueError("preview candidate span required")
    generation = case.current_generation_job_id()
    record = next(r for r in case.job_records if r["job_id"] == generation)
    source = {"candidate_id": candidate.candidate_id, "generation_job_id": generation,
              "span": span.copy(),
              "video_stream_refs": [s["video_stream_ref"] for s in case.sources if s.get("video_stream_ref")]}
    case.bump_revision()
    jobs.issue_job(case, PREVIEW_KIND, scope_ref=record["scope_ref"],
                   input_fingerprint=fingerprint(source), observation_input=source)


def contains_clip(case: CaseAggregate, clip_ref: str) -> bool:
    return any(preview_state(case, c)["clip_ref"] == clip_ref for c in case.candidates)
