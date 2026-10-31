from pathlib import Path

import pytest

from daesingo.search.prompts import FINE_GORE_NOTE
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.schemas import (
    CoarseCandidate,
    CoarseResponse,
    CoarseSpan,
    FineResponse,
    FineTarget,
)
from daesingo.search.scope import VisualEventType
from daesingo.search.usage import ProviderUsage
from eval import gemini_preflight
from eval.runners import normalize, registry
from eval.runners.impls import search_pipeline
from eval.scorers import pipeline
from tests.search._search_service_support import FixtureMediaPreparer

_GORE = FINE_GORE_NOTE.text.strip()


def _fine(verification: str) -> FineResponse:
    return FineResponse(
        verification=verification,
        visual_event_type=VisualEventType.SIGNAL if verification == "OBSERVED" else None,
        target=FineTarget(
            association_status="MATCHED",
            described_as="흰색 세단",
            match_with_hint=None,
            track_ref=None,
        ),
        primitives=(),
        temporal_facts=(),
        uncertainties=(),
    )


class _FakeProvider:
    instances: list["_FakeProvider"] = []

    def __init__(self, api_key: str, config: object) -> None:
        del api_key
        self.config = config
        self.fine_prompts: list[str] = []
        _FakeProvider.instances.append(self)

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        del request
        return ProviderResult(
            CoarseResponse(
                candidates=tuple(
                    CoarseCandidate(
                        event_type=VisualEventType.SIGNAL,
                        span=CoarseSpan(start_sec=10.0 * i, end_sec=10.0 * i + 2),
                        at_sec=10.0 * i + 1,
                        observed=("앞차가 정지선을 넘었다",),
                        score=0.9 - 0.1 * i,
                    )
                    for i in range(4)
                ),
            ),
            ProviderUsage(1, 0, 0, 1),
            1,
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        # 운영 경로(gore 포함 프롬프트). s3만 여기로 온다.
        self.fine_prompts.append("GORE")
        del request
        return ProviderResult(_fine("OBSERVED"), ProviderUsage(1, 0, 0, 1), 1)

    def invoke_structured(self, invocation) -> ProviderResult[FineResponse]:
        self.fine_prompts.append(invocation.prompt)
        return ProviderResult(_fine("NOT_OBSERVED"), ProviderUsage(1, 0, 0, 1), 1)


@pytest.fixture
def fake_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clips = tuple(
        gemini_preflight.PreparedClip(clip_id, tmp_path / clip_id, 60.0, "0" * 64)
        for clip_id in ("c1", "c2")
    )
    for clip in clips:
        clip.path.write_bytes(b"x")
    prepared = gemini_preflight.PreparedEval("redacted", "2.24.0", clips)
    _FakeProvider.instances.clear()
    monkeypatch.setattr(search_pipeline.gemini_preflight, "prepare", lambda _: prepared)
    monkeypatch.setattr(search_pipeline, "GeminiProvider", _FakeProvider)
    monkeypatch.setattr(search_pipeline, "MediaPreparer", lambda _: FixtureMediaPreparer(60.0))
    return {"manifest": "ctier3", "stage": "candidate"}


def test_points_differ_only_in_the_changed_settings():
    s1, s2, s3 = (search_pipeline.config_for(search_pipeline.POINTS[p]) for p in ("s1", "s2", "s3"))
    assert (s1.model, s1.coarse_fps, s1.fine_fps) == ("gemini-3.8-flash", 1.0, 1.0)
    assert (s2.model, s2.coarse_fps, s2.fine_fps) == ("gemini-3.8-flash", 2.0, 4.0)
    assert (s3.model, s3.coarse_fps, s3.fine_fps) == ("gemini-4-argon", 2.0, 4.0)
    assert s1.base_url == s2.base_url != s3.base_url
    assert s3.input_usd_per_million > s2.input_usd_per_million > 0


def test_registry_exposes_all_three_points():
    for name in ("search:s1-flash-1x", "search:s2-flash-slow", "search:s3-argon-gore"):
        assert registry.get(name)


def test_fine_runs_on_top_k_candidates_only(fake_run):
    raw = search_pipeline.run_s3(fake_run)

    for item in raw:
        verified = [c for c in item["candidates"] if c["verification"] is not None]
        assert len(verified) == search_pipeline.FINE_TOP_K
        top = sorted(item["candidates"], key=lambda c: -c["score"])[: search_pipeline.FINE_TOP_K]
        assert all(c["verification"] == "OBSERVED" for c in top)
    facts = search_pipeline.run_facts({})
    assert facts["point"] == "s3"
    assert facts["fine_prompt_version"] == "fine-p3+fine-gore-v1"
    # Coarse 2클립 + Fine 2×3
    assert len(facts["usage_records"]) == 2 + 2 * 3


def test_points_before_v4_send_fine_prompt_without_gore_note(fake_run):
    search_pipeline.run_s1(fake_run)

    prompts = _FakeProvider.instances[0].fine_prompts
    assert len(prompts) == 2 * search_pipeline.FINE_TOP_K
    assert all(_GORE not in p and "SIGNAL" in p for p in prompts)
    assert search_pipeline.run_facts({})["fine_prompt_version"] == "fine-p3"


def test_normalizer_keeps_verification(fake_run):
    norm = normalize.normalize_candidate(search_pipeline.run_s1(fake_run))
    assert {c["verification"] for c in norm[0]["candidates"]} == {"NOT_OBSERVED", None}


# --- pipeline scorer -------------------------------------------------------

def _cand(rank, sec, verification, event_type="SIGNAL"):
    return {"rank": rank, "representative_sec": sec, "t_start_sec": sec - 1,
            "t_end_sec": sec + 1, "event_type": event_type, "score": 1 - rank / 10,
            "verification": verification}


_GT = {"meta": {}, "items": [
    {"clip_id": "p1", "targets": [{"event_id": "e1", "violation_type": "SIGNAL",
                                   "t_onset_sec": 10, "scoring": "INCLUDED"}]},
    {"clip_id": "p2", "targets": [{"event_id": "e2", "violation_type": "SIGNAL",
                                   "t_onset_sec": 20, "scoring": "INCLUDED"}]},
    {"clip_id": "n1", "targets": []},
    {"clip_id": "n2", "targets": []},
]}


def test_pipeline_scorer_splits_verdicts_and_gates_final_results():
    norm = [
        {"clip_id": "p1", "candidates": [_cand(1, 10, "OBSERVED"), _cand(2, 40, "NOT_OBSERVED")]},
        {"clip_id": "p2", "candidates": [_cand(1, 20, "UNCERTAIN")]},
        {"clip_id": "n1", "candidates": [_cand(1, 5, "OBSERVED"), _cand(2, 9, "NOT_OBSERVED"),
                                         _cand(4, 30, "OBSERVED")]},
        {"clip_id": "n2", "candidates": []},
    ]
    r = pipeline.score(norm, _GT)

    assert r["verdicts_on_event_candidates"] == {
        "OBSERVED": 1, "UNCERTAIN": 1, "NOT_OBSERVED": 0, "None": 0}
    assert r["verdicts_on_unmatched_positive_clip_candidates"]["NOT_OBSERVED"] == 1
    # rank 4 는 k=3 밖이라 세지 않는다
    assert r["verdicts_on_negative_clip_candidates"] == {
        "OBSERVED": 1, "UNCERTAIN": 0, "NOT_OBSERVED": 1, "None": 0}
    assert r["fine_confirm_rate"] == 0.5
    assert r["fine_reject_rate"] == 0.5
    assert r["final"]["observed"]["recall"] == 0.5
    assert r["final"]["not_rejected"]["recall"] == 1.0
    assert r["final"]["observed"]["fp_per_negative_clip"] == 0.5
    assert r["final"]["observed"]["negative_clips_with_fp"] == 1


def test_pipeline_scorer_does_not_pass_unverified_candidates():
    norm = [{"clip_id": "p1", "candidates": [_cand(1, 10, None)]}]
    r = pipeline.score(norm, _GT)
    assert r["final"]["not_rejected"]["hits"] == 0
    assert not pipeline.has_verification(norm)
