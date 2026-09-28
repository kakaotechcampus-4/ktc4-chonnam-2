"""Non-canonical stream provenance for the Monday Real E2E boundary.

The public CandidateEvent and VisualVerificationResult serializations remain
unchanged.  This module carries the one VIDEO stream used by a Search
execution so Case can pass the same stream to Recording.resolve_span().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .errors import VideoStreamSelectionError
from .runs import ContractRef
from .visual import VisualVerificationResult

MediaType = Literal["VIDEO", "AUDIO"]


@dataclass(frozen=True, slots=True)
class AnalysisSourceStream:
    """Explicit MediaStream fact supplied alongside an AnalysisSource.

    ``media_type`` must come from Recording's MediaStream metadata.  Search
    must not infer it from the opaque ref string or list position.
    """

    media_stream_ref: str
    media_type: MediaType

    def __post_init__(self) -> None:
        if not self.media_stream_ref:
            raise ValueError("media_stream_ref는 비어 있을 수 없습니다")
        if self.media_type not in {"VIDEO", "AUDIO"}:
            raise ValueError("media_type은 VIDEO 또는 AUDIO여야 합니다")


@dataclass(frozen=True, slots=True)
class SelectedVideoStream:
    """The single VIDEO stream selected for one Search execution."""

    analysis_source_ref: ContractRef
    media_stream_ref: str


@dataclass(frozen=True, slots=True)
class VisualVerificationExecution:
    """Fine result plus non-canonical stream provenance for Case."""

    result: VisualVerificationResult
    selected_video_stream: SelectedVideoStream


def select_single_video_stream(
    analysis_source_ref: ContractRef,
    streams: tuple[AnalysisSourceStream, ...],
) -> SelectedVideoStream:
    """Select exactly one explicit VIDEO stream or fail visibly.

    Monday's baseline deliberately has no default/front/rear policy.  Multiple
    VIDEO streams therefore require a future selector decision rather than an
    arbitrary first-element choice.
    """
    refs = [stream.media_stream_ref for stream in streams]
    if len(set(refs)) != len(refs):
        raise VideoStreamSelectionError(
            analysis_source_ref=analysis_source_ref,
            code="DUPLICATE_MEDIA_STREAM_REF",
            stream_refs=tuple(refs),
        )
    video_refs = tuple(
        stream.media_stream_ref for stream in streams if stream.media_type == "VIDEO"
    )
    if len(video_refs) != 1:
        raise VideoStreamSelectionError(
            analysis_source_ref=analysis_source_ref,
            code=("VIDEO_STREAM_NOT_FOUND" if not video_refs else "AMBIGUOUS_VIDEO_STREAM"),
            stream_refs=video_refs,
        )
    return SelectedVideoStream(
        analysis_source_ref=analysis_source_ref,
        media_stream_ref=video_refs[0],
    )
