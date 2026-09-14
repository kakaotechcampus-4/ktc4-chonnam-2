"""공용 recording Mock fixture를 canonical 모델로 읽는 adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .models import ContractModel, MediaStream, SourceAsset


_SCENARIO_ID = re.compile(r"scenario_[a-z0-9_]+")
_DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "mock" / "recording"


class RecordingFixture(ContractModel):
    """현재 구현 범위에서 소비하는 recording fixture view."""

    scenario_id: str = Field(min_length=1)
    module: Literal["recording"]
    source_assets: list[SourceAsset]
    media_streams: list[MediaStream]

    @model_validator(mode="after")
    def source_stream_references_are_consistent(self) -> RecordingFixture:
        assets = {asset.source_asset_ref: asset for asset in self.source_assets}
        streams = {stream.media_stream_ref: stream for stream in self.media_streams}

        if len(assets) != len(self.source_assets):
            raise ValueError("source_asset_ref는 fixture 안에서 중복될 수 없습니다")
        if len(streams) != len(self.media_streams):
            raise ValueError("media_stream_ref는 fixture 안에서 중복될 수 없습니다")

        for asset in self.source_assets:
            if len(set(asset.media_stream_refs)) != len(asset.media_stream_refs):
                raise ValueError(f"{asset.source_asset_ref}의 media_stream_refs가 중복되었습니다")
            for stream_ref in asset.media_stream_refs:
                stream = streams.get(stream_ref)
                if stream is None:
                    raise ValueError(f"{stream_ref}를 가리키는 MediaStream이 없습니다")
                if stream.source_asset_ref != asset.source_asset_ref:
                    raise ValueError(f"{stream_ref}의 SourceAsset 역참조가 일치하지 않습니다")

        for stream in self.media_streams:
            asset = assets.get(stream.source_asset_ref)
            if asset is None:
                raise ValueError(f"{stream.source_asset_ref}를 가리키는 SourceAsset이 없습니다")
            if stream.media_stream_ref not in asset.media_stream_refs:
                raise ValueError(f"{stream.media_stream_ref}가 SourceAsset에 등재되지 않았습니다")

        return self


def load_recording_fixture(
    scenario_id: str,
    *,
    fixture_dir: Path | None = None,
) -> RecordingFixture:
    """시나리오 fixture를 읽고 현재 recording 계약 경계를 검증한다."""

    if _SCENARIO_ID.fullmatch(scenario_id) is None:
        raise ValueError("scenario_id 형식이 올바르지 않습니다")

    source_dir = fixture_dir if fixture_dir is not None else _DEFAULT_FIXTURE_DIR
    fixture_path = source_dir / f"{scenario_id}.json"
    with fixture_path.open(encoding="utf-8") as fixture_file:
        payload: Any = json.load(fixture_file)

    return RecordingFixture.model_validate(payload)
