import shutil
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.media import MediaInput, MediaPreparer, PreparedMedia
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import ContractRef
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.sources import ResolvedAnalysisSource
from daesingo.search.usage import ProviderUsage


@dataclass(frozen=True, slots=True)
class BaselineProvider:
    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        _ = request
        return ProviderResult(
            CoarseResponse.model_validate(
                {
                    "candidates": [
                        {
                            "event_type": "SIGNAL",
                            "span": {"start_sec": 1.0, "end_sec": 2.0},
                            "at_sec": 1.5,
                            "observed": ["signal visible"],
                            "score": 0.8,
                        }
                    ]
                }
            ),
            ProviderUsage(10, 2, 0, 12),
            15,
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        _ = request
        raise NotImplementedError


class ControllableClock:
    _now: float

    def __init__(self) -> None:
        self._now = 0.0

    def __call__(self) -> float:
        return self._now

    def expire(self) -> None:
        self._now = 31.0


class ExpiringMediaPreparer:
    _delegate: MediaPreparer
    _clock: ControllableClock

    def __init__(self, config: GeminiSearchConfig, clock: ControllableClock) -> None:
        self._delegate = MediaPreparer(config)
        self._clock = clock

    @contextmanager
    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> Generator[PreparedMedia]:
        with self._delegate.prepare_coarse(media_input, deadline) as prepared:
            self._clock.expire()
            yield prepared


def make_mp4(path: Path, duration_sec: float = 2.0) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AssertionError("ffmpeg is required for Todo 8 verification")
    _ = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=640x480:rate=12:duration={duration_sec}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration_sec}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return path.read_bytes()


def make_source(duration_sec: float = 2.0) -> ResolvedAnalysisSource:
    return ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="source-exact"),
        duration_sec,
        "timeline-coarse-flow",
        3,
    )


def capture_temp_dirs(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    paths: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = Path(real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
        paths.append(path)
        return str(path)

    monkeypatch.setattr("daesingo.search.media.tempfile.mkdtemp", recording_mkdtemp)
    return paths
