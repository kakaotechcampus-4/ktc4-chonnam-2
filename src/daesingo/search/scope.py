from enum import StrEnum, unique
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator
from pydantic_core import PydanticCustomError

from ._base import ContractModel


@unique
class TimeRangeKind(StrEnum):
    ABSOLUTE = "ABSOLUTE"
    TIMELINE_RELATIVE = "TIMELINE_RELATIVE"


@unique
class VisualEventType(StrEnum):
    SIGNAL = "SIGNAL"
    CENTER_LINE_CROSSING = "CENTER_LINE_CROSSING"
    SOLID_LINE_LANE_CHANGE = "SOLID_LINE_LANE_CHANGE"
    MOTORCYCLE_HELMET_NON_USE = "MOTORCYCLE_HELMET_NON_USE"


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class TimelineRef(ContractModel):
    timeline_id: str = Field(min_length=1)
    revision: PositiveInt


class AbsoluteTimeRange(ContractModel):
    kind: Literal[TimeRangeKind.ABSOLUTE] = TimeRangeKind.ABSOLUTE
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end < self.start:
            raise PydanticCustomError(
                "absolute_range_order", "end must not precede start"
            )
        return self


class TimelineRelativeTimeRange(ContractModel):
    kind: Literal[TimeRangeKind.TIMELINE_RELATIVE]
    timeline_ref: TimelineRef
    start_ms: NonNegativeInt
    end_ms: NonNegativeInt

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end_ms < self.start_ms:
            raise PydanticCustomError(
                "relative_range_order", "end_ms must not precede start_ms"
            )
        return self


type TimeRange = AbsoluteTimeRange | TimelineRelativeTimeRange


class SearchHint(ContractModel):
    vehicle: str | None
    free_text: str | None


class SearchBudget(ContractModel):
    max_cost_krw: NonNegativeInt
    max_latency_sec: PositiveInt


class AnalysisScope(ContractModel):
    scope_id: str = Field(min_length=1)
    time_ranges: tuple[TimeRange, ...] = Field(min_length=1)
    target_event_types: tuple[VisualEventType, ...] = Field(min_length=1)
    hint: SearchHint
    budget: SearchBudget
    contract_version: Literal["1.1.0"]

    @model_validator(mode="after")
    def check_coordinate_kind(self) -> Self:
        kinds = {time_range.kind for time_range in self.time_ranges}
        if len(kinds) != 1:
            raise PydanticCustomError(
                "mixed_time_range_kinds", "one scope cannot mix coordinate kinds"
            )
        return self
