import hashlib
import json
from pathlib import Path

from daesingo.search.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "smoke_provider.json"
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


def _run_smoke(
    tmp_path: Path, capsys, *extra: str
) -> tuple[int, dict[str, JsonValue], str]:
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"bounded smoke recording")

    exit_code = main(
        [
            "smoke",
            "--source",
            str(source),
            "--duration-sec",
            "12",
            "--provider-fixture",
            str(FIXTURE),
            *extra,
        ]
    )

    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out), captured.out


def test_smoke_succeeds_without_api_key_and_selects_highest_score(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    # Given
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # When
    exit_code, report, _ = _run_smoke(tmp_path, capsys)

    # Then
    assert exit_code == 0
    assert report["schema_version"] == "daesingo-search-smoke/v1"
    assert report["status"] == "succeeded"
    selected = report["selected_candidate"]
    fine = report["fine_result"]
    assert isinstance(selected, dict)
    assert isinstance(fine, dict)
    assert selected["ranking_score"] == 0.94
    assert fine["visual_evidence"]["candidate_id"] == selected["candidate_id"]
    assert fine["visual_evidence"]["target"]["evidence_refs"] == ["fr_exact_001"]


def test_smoke_reports_sha_usage_bounds_and_redacts_sensitive_data(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    # Given
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key-never-print")
    source = tmp_path / "recording.mp4"
    expected_hash = hashlib.sha256(b"bounded smoke recording").hexdigest()

    # When
    exit_code, report, raw = _run_smoke(tmp_path, capsys)

    # Then
    assert exit_code == 0
    assert report["input_sha256"] == expected_hash
    assert report["model"] == "fixture-gemini"
    assert len(report["config_fingerprint"]) == 64
    assert report["usage"] == {
        "latency_ms": 200,
        "input_tokens": 140,
        "output_tokens": 30,
        "thought_tokens": 7,
        "total_tokens": 177,
        "cost_usd": "0.00024375",
    }
    selected = report["selected_candidate"]
    assert isinstance(selected, dict)
    assert 0 <= selected["span"]["start_ms"] < selected["span"]["end_ms"] <= 12000
    assert str(source) not in raw
    assert "secret-key-never-print" not in raw
    assert "12가3456" not in raw
    assert "raw_payload" not in raw


def test_smoke_no_candidates_is_typed_failure_without_fine_fallback(
    tmp_path: Path, capsys
) -> None:
    # Given
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["coarse"]["response"]["candidates"] = []
    empty_fixture = tmp_path / "empty.json"
    empty_fixture.write_text(json.dumps(fixture), encoding="utf-8")
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
            str(empty_fixture),
        ]
    )

    # Then
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["failure_stage"] == "no_candidates"
    assert report["selected_candidate"] is None
    assert report["fine_result"] is None


def test_smoke_stops_before_fine_when_time_or_cost_budget_is_exhausted(
    tmp_path: Path, capsys
) -> None:
    # Given
    # When
    time_code, time_report, _ = _run_smoke(tmp_path, capsys, "--timeout-sec", "0.1")
    cost_code, cost_report, _ = _run_smoke(
        tmp_path, capsys, "--max-cost-usd", "0.00001"
    )

    # Then
    assert time_code == 1
    assert time_report["failure_stage"] == "time_budget"
    assert time_report["fine_result"] is None
    assert cost_code == 1
    assert cost_report["failure_stage"] == "cost_budget"
    assert cost_report["fine_result"] is None


def test_smoke_invalid_inputs_emit_one_typed_json_document(
    tmp_path: Path, capsys
) -> None:
    # Given
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"model": "missing-stages"}', encoding="utf-8")

    # When
    exit_code = main(
        [
            "smoke",
            "--source",
            str(tmp_path / "missing.mp4"),
            "--duration-sec",
            "0",
            "--provider-fixture",
            str(malformed),
        ]
    )

    # Then
    raw = capsys.readouterr().out
    assert exit_code == 2
    assert len([line for line in raw.splitlines() if line.startswith("{")]) == 1
    assert json.loads(raw)["failure_stage"] == "input"


def test_smoke_malformed_fixture_is_a_typed_input_failure(
    tmp_path: Path, capsys
) -> None:
    # Given
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"video")
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"model": "missing-stages"}', encoding="utf-8")

    # When
    exit_code = main(
        [
            "smoke",
            "--source",
            str(source),
            "--duration-sec",
            "12",
            "--provider-fixture",
            str(malformed),
        ]
    )

    # Then
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["failure_stage"] == "input"


def test_smoke_fails_closed_when_coarse_cost_is_unavailable(
    tmp_path: Path, capsys
) -> None:
    # Given
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["coarse"]["usage"]["input_tokens"] = None
    unknown_cost = tmp_path / "unknown-cost.json"
    unknown_cost.write_text(json.dumps(fixture), encoding="utf-8")
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
            str(unknown_cost),
        ]
    )

    # Then
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["failure_stage"] == "budget_unavailable"
    assert report["fine_result"] is None


def test_smoke_uses_rank_as_the_equal_score_tie_breaker(tmp_path: Path, capsys) -> None:
    # Given
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["coarse"]["response"]["candidates"][0]["score"] = 0.94
    tied = tmp_path / "tied.json"
    tied.write_text(json.dumps(fixture), encoding="utf-8")
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
            str(tied),
        ]
    )

    # Then
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["selected_candidate"]["rank"] == 1
    assert report["selected_candidate"]["event_type_hint"] == "SIGNAL"


def test_legacy_fine_command_returns_a_handled_candidate_error(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    # Given
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"video")

    # When
    exit_code = main(["fine", "--source", str(source), "--duration-sec", "12"])

    # Then
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "requires an explicit candidate" in captured.err
