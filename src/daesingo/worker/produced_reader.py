"""Worker consumer schemas, outside common's opaque append-only storage."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from daesingo.common.jobs.produced import ProducedReader


Ref = Annotated[str, Field(min_length=1)]


class IncidentClipResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    incident_clip_ref: Ref
    preview_frame_ref: Ref | None = None
    candidate_frame_refs: dict[Ref, Ref | None] = Field(default_factory=dict, max_length=3)

    @field_validator("candidate_frame_refs", mode="before")
    @classmethod
    def nullable_candidates(cls, value):
        return {} if value is None else value


def assemble_produced(kind, values):
    if len(values) != 1:
        raise ValueError("produced assembly required")
    if kind == "INCIDENT_CLIP_BUILD":
        return IncidentClipResult.model_validate(values[0]).model_dump()
    return values[0]


def worker_produced_reader():
    return ProducedReader(assemble=assemble_produced)
