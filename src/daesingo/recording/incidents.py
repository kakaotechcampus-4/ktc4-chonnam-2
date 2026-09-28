"""IncidentClip 생성 설정. Readout source_profile/AnalysisSource ref와 독립이다."""

from dataclasses import dataclass
from pathlib import Path

from .materialization import AnalysisProfile, LocalAnalysisMaterializer, MaterializedVideo
from .models import AssetSpan
from .probe import LocalSource


@dataclass(frozen=True)
class IncidentClipEncoding:
    height: int
    preset: str
    crf: int


class LocalIncidentMaterializer:
    def __init__(self, encoding: IncidentClipEncoding, *, ffmpeg="ffmpeg", ffprobe="ffprobe",
                 timeout_sec=120.0, temp_root: Path | None = None):
        # 기존 엔진의 설정 검증·frame cut·출력 probe·cleanup만 재사용한다.
        # 이 내부 설정 key는 AnalysisSource.profile_ref로 발행되지 않는다.
        configuration = AnalysisProfile(encoding.height, encoding.preset, encoding.crf)
        self._engine = LocalAnalysisMaterializer({"incident-encoding": configuration},
            ffmpeg=ffmpeg, ffprobe=ffprobe, timeout_sec=timeout_sec, temp_root=temp_root)
        self._identity = ("incident-materialization/v1", encoding.height, encoding.preset, encoding.crf)

    @property
    def generation_conditions(self) -> tuple:
        return self._identity

    def materialize(self, source: LocalSource, index: int, span: AssetSpan) -> MaterializedVideo:
        return self._engine.materialize(source, index, span, "incident-encoding")
