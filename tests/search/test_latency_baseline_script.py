"""examples/search_latency_baseline.py의 측정 루프를 유료 호출 없이 확인한다."""

import importlib.util
from itertools import count
from pathlib import Path

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.service import SearchService
from daesingo.search.sources import LocalAnalysisSourceResolver
from daesingo.search.usage import ProviderUsage
from tests.search._search_service_support import FixtureMediaPreparer

_spec = importlib.util.spec_from_file_location(
    "search_latency_baseline",
    Path(__file__).parents[2] / "examples/search_latency_baseline.py",
)
assert _spec is not None and _spec.loader is not None
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)


class _Provider:
    def __init__(self, fine_error: Exception | None = None) -> None:
        self.fine_calls = 0
        self._fine_error = fine_error

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        del request
        response = CoarseResponse.model_validate(
            {
                "candidates": [
                    {"event_type": "SIGNAL", "span": {"start_sec": 1, "end_sec": 3},
                     "at_sec": 2, "observed": ["적색 점등"], "score": 0.8},
                    {"event_type": "SIGNAL", "span": {"start_sec": 5, "end_sec": 7},
                     "at_sec": 6, "observed": ["적색 점등"], "score": 0.4},
                ]
            }
        )
        return ProviderResult(response, ProviderUsage(100, 20, 0, 120), 1500)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        del request
        self.fine_calls += 1
        if self._fine_error is not None:
            raise self._fine_error
        response = FineResponse.model_validate(
            {
                "verification": "UNCERTAIN",
                "visual_event_type": None,
                "target": {"association_status": "AMBIGUOUS", "described_as": None,
                           "match_with_hint": None, "association_confidence": None,
                           "track_ref": None},
                "primitives": [],
                "temporal_facts": [],
                "uncertainties": [],
            }
        )
        return ProviderResult(response, ProviderUsage(50, 10, 0, 60), 700)


def _clip(tmp_path: Path) -> object:
    path = tmp_path / "clip_010s.mp4"
    _ = path.write_bytes(b"fixture")
    return baseline.Clip("clip_010s", path, 10.0, 7)


def _builder(provider: _Provider):
    ticks = count()

    def build(resolver: LocalAnalysisSourceResolver) -> SearchService:
        return SearchService(
            resolver,
            provider,
            GeminiSearchConfig(),
            FixtureMediaPreparer(10.0),
            lambda: float(next(ticks)),
        )

    return build


def _seconds():
    ticks = count(step=2)
    return lambda: float(next(ticks))


def test_measure_emits_one_coarse_row_and_top_k_fine_rows_per_repeat(tmp_path: Path) -> None:
    provider = _Provider()

    rows = list(baseline.measure(
        [_clip(tmp_path)], repeats=2, fine_top_k=1, max_latency_sec=600,
        build_service=_builder(provider), clock=_seconds(),
    ))

    assert [(r["repeat"], r["stage"]) for r in rows] == [
        (1, "coarse"), (1, "fine"), (2, "coarse"), (2, "fine"),
    ]
    coarse, fine = rows[0], rows[1]
    assert coarse["outcome"] == "SUCCEEDED"
    assert coarse["candidates"] == 2
    assert coarse["latency_ms"] == 1500
    assert coarse["wall_ms"] == 2000
    assert fine["rank"] == 1
    assert fine["verification"] == "UNCERTAIN"
    assert fine["latency_ms"] == 700
    assert fine["ledger_records"] == 1
    assert provider.fine_calls == 2


def test_measure_records_fine_error_type_without_message_and_continues(
    tmp_path: Path,
) -> None:
    provider = _Provider(fine_error=RuntimeError("secret provider body"))

    rows = list(baseline.measure(
        [_clip(tmp_path)], repeats=1, fine_top_k=2, max_latency_sec=600,
        build_service=_builder(provider), clock=_seconds(),
    ))

    fines = [r for r in rows if r["stage"] == "fine"]
    assert [r["rank"] for r in fines] == [1, 2]
    assert all(r["error_type"] for r in fines)
    assert "secret" not in repr(rows)


def test_measure_concurrent_runs_coarse_only_in_batches(tmp_path: Path) -> None:
    provider = _Provider()
    clips = [
        baseline.Clip(f"clip_{i}", _clip(tmp_path).path, 10.0, 7) for i in range(5)
    ]

    rows = list(baseline.measure_concurrent(
        clips, concurrency=2, max_latency_sec=600,
        build_service=_builder(provider), clock=_seconds(),
    ))

    assert [r["clip"] for r in rows] == [c.label for c in clips]
    assert [r["batch"] for r in rows] == [1, 1, 2, 2, 3]
    assert [r["batch_size"] for r in rows] == [2, 2, 2, 2, 1]
    assert all(r["stage"] == "coarse" and r["outcome"] == "SUCCEEDED" for r in rows)
    assert all(r["concurrency"] == 2 for r in rows)
    assert provider.fine_calls == 0
