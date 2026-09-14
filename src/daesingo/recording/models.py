"""Recording이 생산하는 canonical data contract 모델."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CONTRACT_VERSION = "source-asset-media-stream/v1"


class ContractModel(BaseModel):
    """Canonical JSON 경계에서 공통으로 사용하는 모델 설정."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


class ExternalSourceRef(ContractModel):
    kind: Literal["external_source"]
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
