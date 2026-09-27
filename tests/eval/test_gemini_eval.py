import json
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import override

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.schemas import CoarseCandidate, CoarseResponse, CoarseSpan, FineResponse
from daesingo.search.scope import VisualEventType
from daesingo.search.service import SearchService
from daesingo.search.sources import AnalysisSourceResolver
from daesingo.search.usage import ProviderUsage
from eval import gemini_preflight, paths, run, score
from eval.runners.impls import search_gemini
from tests.search._search_service_support import FixtureMediaPreparer


@dataclass(frozen=True, slots=True)
class _CandidateProvider:
    unknown_cost_clip_id: str | None

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        unknown_cost = request.source.source_id == self.unknown_cost_clip_id
        return ProviderResult(
            CoarseResponse(
                candidates=(
                    CoarseCandidate(
                        event_type=VisualEventType.SIGNAL,
                        span=CoarseSpan(start_sec=0.0, end_sec=1.0),
                        at_sec=0.5,
                        observed=("앞차가 정지선을 넘었다", "저해상도로 번호판 불확실"),
                        score=0.8,
                    ),
                ),
            ),
            (
                ProviderUsage(None, None, None, None)
                if unknown_cost
                else ProviderUsage(1, 0, 0, 1)
            ),
            1000 if unknown_cost else 1,
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        raise AssertionError("not called")


class _ManifestMediaPreparer(FixtureMediaPreparer):
    @override
    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]:
        duration = float(media_input.stream.read())
        return FixtureMediaPreparer(duration).prepare_coarse(media_input, deadline)


def test_preflight_reports_all_boundary_requirements_before_provider_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    clips = [
        {
            "clip_id": f"clip-{index}",
            "file_path": f"missing-{index}.mp4",
            "duration_sec": 1.0,
            "sha256": "0" * 64,
        }
        for index in range(123)
    ]
    monkeypatch.setattr(
        gemini_preflight,
        "load_env_file",
        lambda: {"DAESINGO_EVAL_DATA_ROOT": str(tmp_path)},
    )
    monkeypatch.setattr(
        gemini_preflight.manifests_io, "load_clips", lambda _: {"clips": clips}
    )

    with pytest.raises(gemini_preflight.PreflightError) as raised:
        gemini_preflight.prepare({"manifest": "b_youtube", "stage": "candidate"})

    message = str(raised.value)
    assert "before any paid API call" in message
    assert "GEMINI_API_KEY is not set" in message
    assert "media file does not exist" in message


def test_eval_cli_reports_preflight_failure_without_creating_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    built = False

    def fail_preflight(scope: dict[str, str]) -> gemini_preflight.PreparedEval:
        del scope
        raise gemini_preflight.PreflightError("missing media")

    def should_not_build(prepared: gemini_preflight.PreparedEval) -> SearchService:
        del prepared
        nonlocal built
        built = True
        raise AssertionError("provider must not be created")

    monkeypatch.setattr(search_gemini.gemini_preflight, "prepare", fail_preflight)
    monkeypatch.setattr(search_gemini, "_build_service", should_not_build)
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))

    rc = run.main(
        [
            "--impl",
            "search:gemini-coarse-p3",
            "--manifest",
            "b_youtube",
            "--stage",
            "candidate",
            "--run-id",
            "preflight-failure",
        ]
    )

    assert rc == 5
    assert built is False
    assert "missing media" in capsys.readouterr().err


@pytest.mark.parametrize("unknown_cost", [False, True], ids=["known-cost", "unknown-cost"])
def test_mock_provider_preserves_evidence_and_usage_through_prediction_and_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unknown_cost: bool
) -> None:
    clips_doc = search_gemini.gemini_preflight.manifests_io.load_clips("b_youtube")
    prepared_clips = tuple(
        gemini_preflight.PreparedClip(
            str(item["clip_id"]),
            tmp_path / str(item["clip_id"]),
            float(item["duration_sec"]),
            str(item["sha256"]),
        )
        for item in clips_doc["clips"]
    )
    prepared = gemini_preflight.PreparedEval("redacted", "2.24.0", prepared_clips)
    for clip in prepared_clips:
        clip.path.write_bytes(str(clip.duration_sec).encode("ascii"))
    services: list[SearchService] = []

    def build_service(api_key: str, resolver: AnalysisSourceResolver) -> SearchService:
        service = SearchService(
            resolver,
            _CandidateProvider(prepared_clips[0].clip_id if unknown_cost else None),
            GeminiSearchConfig(input_usd_per_million=1.0, output_usd_per_million=2.0),
            _ManifestMediaPreparer(1.0),
            RunDeadline(lambda: 0.0, budget_ms=300_000),
        )
        services.append(service)
        return service

    monkeypatch.setattr(search_gemini.gemini_preflight, "prepare", lambda _: prepared)
    monkeypatch.setattr(search_gemini, "build_gemini_search_service", build_service)
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))

    assert (
        run.main(
            [
                "--impl",
                "search:gemini-coarse-p3",
                "--manifest",
                "b_youtube",
                "--stage",
                "candidate",
                "--run-id",
                "gemini_mock_e2e",
            ]
        )
        == 0
    )
    assert score.main(["--prediction", "gemini_mock_e2e"]) == 0

    prediction = tmp_path / "predictions" / "gemini_mock_e2e.json"
    assert prediction.is_file()
    result = next((tmp_path / "results").glob("gemini_mock_e2e.g3.*.json"))
    assert result.is_file()
    assert len(services) == 1
    assert len(services[0].ledger.records()) == 123

    prediction_doc = json.loads(prediction.read_text(encoding="utf-8"))
    cost = json.loads(result.read_text(encoding="utf-8"))["cost"]
    assert len(prediction_doc["facts"]["usage_records"]) == 123
    assert cost["n_rows"] == 123
    assert cost["n_unknown_cost"] == int(unknown_cost)
    assert cost["latency_ms"]["n"] == 123
    assert cost["latency_ms"]["max"] == (1000 if unknown_cost else 1)
    if unknown_cost:
        assert prediction_doc["facts"]["usage_records"][0]["cost"] is None
        assert "UNKNOWN_COST" in cost["coverage"]
    else:
        assert cost["coverage"] is None
    for rows in (prediction_doc["raw"], prediction_doc["normalized"]):
        assert len(rows) == 123
        for row in rows:
            candidate = row["candidates"][0]
            assert candidate["summary"] == "앞차가 정지선을 넘었다; 저해상도로 번호판 불확실"
            assert candidate["uncertainties"] == ["저해상도로 번호판 불확실"]
