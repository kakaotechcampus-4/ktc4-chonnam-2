"""Recording이 생산하는 canonical data contract 모델."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


CONTRACT_VERSION = "source-asset-media-stream/v1"


class ContractModel(BaseModel):
    """Canonical JSON 경계에서 공통으로 사용하는 모델 설정."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


class ExternalSourceRef(ContractModel):
    kind: Literal["external_source"]
    ref: str = Field(min_length=1)


AssetRefKind = Literal[
    "external_source",
    "source_asset",
    "media_stream",
    "frame",
    "analysis_source",
    "remote_copy",
    "incident_clip",
    "derived_asset",
]


class ContractRef(ContractModel):
    kind: AssetRefKind
    ref: str = Field(min_length=1)


class SourceAsset(ContractModel):
    contract: Literal["SourceAsset"]
    contract_version: Literal[CONTRACT_VERSION]
    source_asset_ref: str = Field(min_length=1)
    asset_kind: Literal["SOURCE_ASSET"]
    external_source_ref: ExternalSourceRef | None
    media_stream_refs: list[str]
    byte_size: int | None = Field(ge=0)
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]
    duration_sec: float | None = Field(ge=0)

    @model_validator(mode="after")
    def available_asset_has_known_size(self) -> SourceAsset:
        if self.availability == "AVAILABLE" and self.byte_size is None:
            raise ValueError("AVAILABLE SourceAsset의 byte_size는 null일 수 없습니다")
        return self


class MediaStream(ContractModel):
    contract: Literal["MediaStream"]
    contract_version: Literal[CONTRACT_VERSION]
    media_stream_ref: str = Field(min_length=1)
    source_asset_ref: str = Field(min_length=1)
    media_type: Literal["VIDEO", "AUDIO"]
    role: Literal["FRONT", "REAR", "UNKNOWN"] | None
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]
    duration_sec: float | None = Field(ge=0)

    @model_validator(mode="after")
    def role_matches_media_type(self) -> MediaStream:
        if self.media_type == "AUDIO" and self.role is not None:
            raise ValueError("AUDIO MediaStream에는 camera role을 지정할 수 없습니다")
        if self.media_type == "VIDEO" and self.role is None:
            raise ValueError("VIDEO MediaStream의 role은 FRONT, REAR, UNKNOWN 중 하나여야 합니다")
        return self


class FrameRef(ContractModel):
    contract: Literal["FrameRef"]
    contract_version: Literal[CONTRACT_VERSION]
    frame_ref: str = Field(min_length=1)
    media_stream_ref: str = Field(min_length=1)
    source_offset_sec: float = Field(ge=0)


class TimelineRef(ContractModel):
    timeline_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


class TimeRange(ContractModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)

    @model_validator(mode="after")
    def end_is_after_start(self) -> TimeRange:
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec는 start_sec보다 커야 합니다")
        return self


class AssetFacts(ContractModel):
    contract: Literal["AssetFacts"]
    contract_version: Literal[CONTRACT_VERSION]
    asset_ref: ContractRef
    asset_kind: Literal["SOURCE_ASSET", "ANALYSIS_SOURCE", "INCIDENT_CLIP", "DERIVED_ASSET"]
    derived_role: Literal["REPORT_VIDEO", "PLATE_IMAGE"] | None
    byte_size: int | None = Field(ge=0)
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]
    checked_at: AwareDatetime
    lineage: list[ContractRef]
    duration_sec: float | None = Field(ge=0)
    timeline_ref: TimelineRef | None
    timeline_range: TimeRange | None

    @model_validator(mode="after")
    def facts_are_consistent(self) -> AssetFacts:
        expected_ref_kind = {
            "SOURCE_ASSET": "source_asset",
            "ANALYSIS_SOURCE": "analysis_source",
            "INCIDENT_CLIP": "incident_clip",
            "DERIVED_ASSET": "derived_asset",
        }[self.asset_kind]
        if self.asset_ref.kind != expected_ref_kind:
            raise ValueError("asset_ref.kind와 asset_kind의 의미가 일치하지 않습니다")
        if self.availability == "AVAILABLE" and self.byte_size is None:
            raise ValueError("AVAILABLE AssetFacts의 byte_size는 null일 수 없습니다")
        if (self.timeline_ref is None) != (self.timeline_range is None):
            raise ValueError("timeline_ref와 timeline_range는 함께 존재하거나 함께 null이어야 합니다")
        if self.asset_kind != "DERIVED_ASSET" and self.derived_role is not None:
            raise ValueError("DERIVED_ASSET가 아닌 자산에는 derived_role을 지정할 수 없습니다")
        if self.asset_kind != "SOURCE_ASSET" and not any(
            item.kind in {"source_asset", "external_source"} for item in self.lineage
        ):
            raise ValueError("파생 자산 lineage에는 원본 자산 참조가 필요합니다")
        return self


class LocatorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TimelinePositionLocator(LocatorModel):
    kind: Literal["TIMELINE_POSITION"]
    timeline_ref: TimelineRef
    at_sec: float = Field(ge=0)
    stream_selector: object | None


class StreamPositionLocator(LocatorModel):
    kind: Literal["STREAM_POSITION"]
    media_stream_ref: str = Field(min_length=1)
    source_offset_sec: float = Field(ge=0)


FrameLocator = Annotated[
    TimelinePositionLocator | StreamPositionLocator,
    Field(discriminator="kind"),
]
