"""늘린 영상(playback_speed != 1)을 보낼 때 provider가 안내를 붙이고 시각을 원본으로 되돌린다."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import BaseModel

from daesingo.search import prompts
from daesingo.search.media import PreparedMedia
from daesingo.search.prompts import COARSE_PROMPT, playback_note, sent_prompt_fingerprint
from daesingo.search.provider import CoarseRequest, FineRequest, GeminiProvider
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.scope import VisualEventType

from .test_provider_bounds import (
    _Chat,
    _Choice,
    _Completion,
    _FakeClient,
    _make_openai_module,
    _Msg,
    _source,
)


@dataclass
class _Returning:
    response: BaseModel
    calls: list[dict[str, object]] = field(default_factory=list)

    def parse(self, **kwargs: object) -> _Completion:
        self.calls.append(kwargs)
        return _Completion([_Choice(_Msg(self.response))])


def _provider(monkeypatch: pytest.MonkeyPatch, completions: _Returning) -> GeminiProvider:
    import importlib
    import sys

    from daesingo.search.config import GeminiSearchConfig

    mod = _make_openai_module(lambda **_kw: _FakeClient(_Chat(completions)))
    original = importlib.import_module
    monkeypatch.setattr(
        "daesingo.search.provider.importlib.import_module",
        lambda name: mod if name == "openai" else original(name),
    )
    monkeypatch.setitem(sys.modules, "openai", mod)
    return GeminiProvider("k", GeminiSearchConfig())


def _media(tmp_path: Path, speed: float, origin: tuple[float, float]) -> PreparedMedia:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    span = origin[1] - origin[0]
    return PreparedMedia(path, "video/mp4", 1, span / speed, origin[0], origin[1], speed)


def _prompt(completions: _Returning) -> str:
    messages = completions.calls[0]["messages"]
    return messages[0]["content"][0]["text"]  # type: ignore[index]


def test_slowed_coarse_gets_note_and_origin_times(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: 원본 12초를 0.5x로 늘린 영상에서 모델이 늘린 시각 8–12초(핵심 10초)를 답함
    reply = CoarseResponse.model_validate({"candidates": [{
        "event_type": "SIGNAL", "span": {"start_sec": 8.0, "end_sec": 12.0},
        "at_sec": 10.0, "observed": ["x"], "score": 0.5}]})
    completions = _Returning(reply)
    provider = _provider(monkeypatch, completions)

    # When
    result = provider.search_coarse(CoarseRequest(
        _source(), (VisualEventType.SIGNAL,), media=_media(tmp_path, 0.5, (0.0, 12.0))))

    # Then: 안내 단락이 붙고, 시각은 원본 4–6초(핵심 5초)로 돌아온다
    assert "2배 느리게" in _prompt(completions)
    assert _prompt(completions).endswith(playback_note(0.5))
    candidate = result.response.candidates[0]
    assert (candidate.span.start_sec, candidate.span.end_sec, candidate.at_sec) == (4.0, 6.0, 5.0)


def test_slowed_fine_offsets_return_to_clip_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reply = FineResponse.model_validate({
        "verification": "NOT_OBSERVED", "visual_event_type": None,
        "target": {"association_status": "NOT_FOUND", "described_as": None,
                   "match_with_hint": None, "association_confidence": None, "track_ref": None},
        "primitives": [], "uncertainties": [],
        "temporal_facts": [{"at_offset_ms": 8000, "fact": "f"}, {"at_offset_ms": None, "fact": "g"}],
    })
    completions = _Returning(reply)
    provider = _provider(monkeypatch, completions)

    result = provider.verify_fine(FineRequest(
        _source(), VisualEventType.SIGNAL, "", 2.0, 7.0,
        media=_media(tmp_path, 0.25, (2.0, 7.0))))

    assert "4배 느리게" in _prompt(completions)
    assert [f.at_offset_ms for f in result.response.temporal_facts] == [2000, None]


def test_unslowed_media_is_sent_as_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completions = _Returning(CoarseResponse(candidates=()))
    provider = _provider(monkeypatch, completions)

    provider.search_coarse(CoarseRequest(
        _source(), (VisualEventType.SIGNAL,), media=_media(tmp_path, 1.0, (0.0, 12.0))))

    assert "느리게" not in _prompt(completions)


def test_sent_fingerprint_matches_template_at_original_speed() -> None:
    # 원본 속도면 안내가 붙지 않으므로 v2 기록과 같은 값이다
    assert sent_prompt_fingerprint(COARSE_PROMPT, 1.0) == COARSE_PROMPT.fingerprint


def test_sent_fingerprint_follows_speed_and_note_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: 같은 템플릿을 0.5x·0.25x로 보낸다
    half = sent_prompt_fingerprint(COARSE_PROMPT, 0.5)
    quarter = sent_prompt_fingerprint(COARSE_PROMPT, 0.25)
    assert len({COARSE_PROMPT.fingerprint, half, quarter}) == 3

    # When: config.version은 그대로인 채 배속 안내 리소스 문구만 바뀐다
    edited = prompts.PromptTemplate(
        prompts.PLAYBACK_NOTE.version,
        prompts.PLAYBACK_NOTE.text + " 추가 문구.",
        "",
        prompts.PLAYBACK_NOTE.placeholders,
    )
    monkeypatch.setattr(prompts, "PLAYBACK_NOTE", edited)

    # Then: 기록되는 fingerprint가 달라져 provenance로 구분된다
    assert sent_prompt_fingerprint(COARSE_PROMPT, 0.5) != half
