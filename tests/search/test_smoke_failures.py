import json
from decimal import Decimal
from pathlib import Path

import pytest

from daesingo.search.cli import main
from daesingo.search.scope import VisualEventType
from daesingo.search.smoke import SmokeRunOptions, build_smoke_service, run_smoke
from daesingo.search.smoke_fixture import SmokeProviderFixture

FIXTURE = Path(__file__).parent / "fixtures" / "smoke_provider.json"
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


@pytest.mark.parametrize(
    ("stage_name", "failure_stage"),
    (("coarse", "coarse"), ("fine", "fine")),
)
def test_expected_fixture_timeout_becomes_one_typed_stage_failure(
    tmp_path: Path, capsys, stage_name: str, failure_stage: str
) -> None:
    # Given
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture[stage_name]["times_out"] = True
    timing_out = tmp_path / "timing-out.json"
    timing_out.write_text(json.dumps(fixture), encoding="utf-8")
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"video")

    # When
    exit_code = main(
        [
            "smoke",
            "--source",
            str(source),
            "--duration-sec",
            "12",
            "--provider-fixture",
            str(timing_out),
        ]
    )

    # Then
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert exit_code == 1
    assert report["failure_stage"] == failure_stage
    assert len([line for line in raw.splitlines() if line.startswith("{")]) == 1


def test_smoke_orchestration_does_not_swallow_programmer_assertion(
    tmp_path: Path, monkeypatch
) -> None:
    # Given
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"video")
    options = SmokeRunOptions(
        source=source,
        duration_sec=12,
        event_types=tuple(VisualEventType),
        timeout_sec=60,
        max_cost_usd=Decimal(1),
    )
    fixture = SmokeProviderFixture.from_path(FIXTURE)
    service, config = build_smoke_service(options, None, fixture)

    def broken_search(*args: JsonValue, **kwargs: JsonValue) -> JsonValue:
        del args, kwargs
        raise AssertionError("programmer defect")

    monkeypatch.setattr("daesingo.search.smoke.search_candidates", broken_search)

    # When
    with pytest.raises(AssertionError, match="programmer defect") as caught:
        run_smoke(options, service, config)

    # Then
    assert str(caught.value) == "programmer defect"


def test_smoke_cli_does_not_mislabel_unexpected_attribute_error(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    # Given
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"video")

    def broken_factory(*args: JsonValue, **kwargs: JsonValue) -> JsonValue:
        del args, kwargs
        raise AttributeError("programmer defect")

    monkeypatch.setattr("daesingo.search.cli.build_smoke_service", broken_factory)

    # When
    with pytest.raises(AttributeError, match="programmer defect") as caught:
        main(
            [
                "smoke",
                "--source",
                str(source),
                "--duration-sec",
                "12",
                "--provider-fixture",
                str(FIXTURE),
            ]
        )

    # Then
    assert str(caught.value) == "programmer defect"
    assert capsys.readouterr().out == ""
