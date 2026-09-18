from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from daesingo.common import load_env_file
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.fine import normalize_event_type
from daesingo.search.privacy import mask_license_plates
from daesingo.search.prompts import COARSE_PROMPT, FINE_PROMPT, fine_prompt_for
from daesingo.search.retry import RetryPolicy, call_with_retry
from daesingo.search.schemas import CoarseResponse
from daesingo.search.scope import VisualEventType
from daesingo.search.usage import ProviderUsage


def test_prompt_versions_placeholders_and_fingerprints_are_stable_metadata():
    assert COARSE_PROMPT.version == "coarse-p3"
    assert COARSE_PROMPT.placeholders == frozenset({"event_types", "duration_sec"})
    assert FINE_PROMPT.version == "fine-p2"
    assert {
        "event_type",
        "target_hint",
        "start_sec",
        "end_sec",
    } == FINE_PROMPT.placeholders
    assert len(COARSE_PROMPT.fingerprint) == 64
    rendered = COARSE_PROMPT.render(event_types="SIGNAL", duration_sec=10.0)
    assert "{event_types}" not in rendered
    assert "점선처럼 보이거나" in rendered
    assert "법적 위반 여부를 확정하지 마세요" in rendered
    lane = fine_prompt_for(VisualEventType.SOLID_LINE_LANE_CHANGE)
    signal = fine_prompt_for(VisualEventType.SIGNAL)
    assert lane.fingerprint != signal.fingerprint
    assert "점선처럼 보인다는 이유만으로" in lane.text


def test_coarse_schema_accepts_only_contract_event_names_and_relative_coordinates():
    parsed = CoarseResponse.model_validate(
        {
            "candidates": [
                {
                    "event_type": "SIGNAL",
                    "span": {"start_sec": 1.0, "end_sec": 3.0},
                    "at_sec": 2.0,
                    "observed": ["적색 점등"],
                    "score": 0.8,
                }
            ]
        }
    )
    assert parsed.candidates[0].event_type is VisualEventType.SIGNAL
    with pytest.raises(ValidationError):
        CoarseResponse.model_validate(
            {
                "candidates": [
                    {
                        "event_type": "NONE",
                        "span": {"start_sec": 1, "end_sec": 2},
                        "at_sec": 1.5,
                        "observed": [],
                        "score": 0.1,
                    }
                ]
            }
        )


@dataclass
class _Usage:
    total_input_tokens: int | None
    total_output_tokens: int | None
    total_thought_tokens: int | None
    total_tokens: int | None


def test_usage_preserves_none_and_zero_and_includes_thought_cost():
    missing = ProviderUsage.from_sdk(_Usage(None, 0, None, None))
    assert missing.input_tokens is None
    assert missing.output_tokens == 0
    assert missing.cost_usd is None
    measured = ProviderUsage.from_sdk(_Usage(1_000_000, 0, 1_000_000, 2_000_000))
    assert measured.cost_usd is not None
    assert str(measured.cost_usd) == "4.50"


def test_retry_only_retries_rate_limits():
    calls = 0
    sleeps: list[float] = []

    def rate_limited_then_ok() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "ok"

    assert (
        call_with_retry(rate_limited_then_ok, RetryPolicy(2, 0.5), sleeps.append)
        == "ok"
    )
    assert sleeps == [0.5]
    with pytest.raises(RuntimeError, match="bad request"):
        call_with_retry(
            lambda: (_ for _ in ()).throw(RuntimeError("bad request")),
            RetryPolicy(3, 1),
        )


def test_privacy_and_fine_legacy_event_mapping():
    assert (
        mask_license_plates("차량 12가3456, 123 나 9876") == "차량 12가****, 123나****"
    )
    assert normalize_event_type("LANE_CHANGE") is VisualEventType.SOLID_LINE_LANE_CHANGE


def test_config_defaults_are_values_not_slot_descriptors():
    config = GeminiSearchConfig.from_dotenv(env={})
    assert config.model == "gemini-3.8-flash"
    assert config.base_url.endswith("/v1")


def test_config_reads_values_from_env_mapping_only():
    config = GeminiSearchConfig.from_dotenv(
        env={
            "DAESINGO_GEMINI_MODEL": "gemini-x",
            "DAESINGO_GEMINI_BASE_URL": "https://proxy.local/v1",
        }
    )
    assert config.model == "gemini-x"
    assert config.base_url == "https://proxy.local/v1"
    # 미지정 키는 코드 기본값을 쓴다.
    assert config.media_resolution == "low"


def test_load_env_file_parses_keys_and_ignores_env_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\nGEMINI_API_KEY="secret"\nDAESINGO_GEMINI_MODEL=gemini-x\n\nBAD LINE\n',
        encoding="utf-8",
    )
    # shell 환경변수는 무시된다 — 값은 .env 에서만 온다.
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    values = load_env_file(str(env_file))
    assert values == {"GEMINI_API_KEY": "secret", "DAESINGO_GEMINI_MODEL": "gemini-x"}


def test_load_env_file_missing_returns_empty(tmp_path):
    assert load_env_file(str(tmp_path / "nope.env")) == {}
