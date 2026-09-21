from pathlib import Path

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import ContractRef
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.service import SearchService
from daesingo.search.sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver
from daesingo.search.usage import ProviderUsage
from eval import gemini_preflight, paths, run, score
from eval.runners.impls import search_gemini
from tests.search._search_service_support import FixtureMediaPreparer, OpenableResolver


class _EmptyProvider:
    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        return ProviderResult(
            CoarseResponse(candidates=()), ProviderUsage(1, 0, 0, 1), 1
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        raise AssertionError("not called")


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


def test_mock_provider_runs_prediction_then_score_for_all_official_clips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
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
    resolved = {
        clip.clip_id: ResolvedAnalysisSource(
            ContractRef(kind="analysis_source", ref=clip.clip_id),
            clip.duration_sec,
            clip.clip_id,
            1,
        )
        for clip in prepared_clips
    }
    sources = {clip_id: (src,) for clip_id, src in resolved.items()}
    sources_by_ref = {clip_id: src for clip_id, src in resolved.items()}
    service = SearchService(
        OpenableResolver(StaticAnalysisSourceResolver(sources, sources_by_ref)),
        _EmptyProvider(),
        GeminiSearchConfig(),
        FixtureMediaPreparer(1.0),
        RunDeadline(lambda: 0.0, budget_ms=300_000),
    )
    monkeypatch.setattr(search_gemini.gemini_preflight, "prepare", lambda _: prepared)
    monkeypatch.setattr(search_gemini, "_build_service", lambda _: service)
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
    result = next(
        (tmp_path / "results").glob("gemini_mock_e2e.g3*.json"), None
    )
    assert result is not None, sorted(
        p.name for p in (tmp_path / "results").iterdir()
    )
    assert prediction.is_file()
    assert result.is_file()
    assert len(service.ledger.records()) == 123
