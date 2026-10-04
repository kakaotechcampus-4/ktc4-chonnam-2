import json
import subprocess
import sys
from pathlib import Path

import pytest


def _video(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=2",
            "-t",
            "1",
            "-an",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_fixture_cli_writes_full_trace_only_to_local_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(Path.cwd() / "src"))
    # Given: a real input movie and a deterministic observation response.
    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "fixture",
                        "source": str(source),
                        "duration_sec": 1,
                        "event_types": ["SIGNAL"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    coarse = {
        "candidates": [],
        "window_reviews": [
            {
                "start_sec": 0,
                "end_sec": 1,
                "event_type": "SIGNAL",
                "decision": "NO_CANDIDATE",
                "observations": ["private diagnostic sentinel"],
                "reason": "No visible movement",
                "limitations": [],
            }
        ],
    }
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps({"responses": [{"content": json.dumps(coarse)}]}), encoding="utf-8"
    )
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=secret-key-sentinel\n", encoding="utf-8")
    # When: the actual local experiment entrypoint runs without network calls.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "daesingo.search.diagnostic_cli",
            "--manifest",
            str(manifest),
            "--profile",
            "diagnostic-v1",
            "--provider-fixture",
            str(fixture),
            "--env-file",
            str(env_file),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # Then: stdout is safe metadata while the full observation is available locally.
    assert proc.returncode == 0, proc.stderr + proc.stdout
    summary = json.loads(proc.stdout)
    assert summary["mode"] == "FIXTURE"
    assert "private diagnostic sentinel" not in proc.stdout + proc.stderr
    assert "secret-key-sentinel" not in proc.stdout + proc.stderr
    artifact = Path(summary["result_file"])
    assert ".superpowers" in artifact.parts
    assert "private diagnostic sentinel" in artifact.read_text(encoding="utf-8")
    assert Path(summary["report_file"]).is_file()


def test_cli_rejects_overlong_source_before_provider_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(Path.cwd() / "src"))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "long",
                        "source": "missing.mp4",
                        "duration_sec": 61,
                        "event_types": ["SIGNAL"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "daesingo.search.diagnostic_cli",
            "--manifest",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["issue_code"] == "INVALID_INPUT"
    assert "missing.mp4" not in proc.stdout + proc.stderr


def test_output_failure_is_not_reported_as_not_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from daesingo.search.diagnostic_cli import main

    source = tmp_path / "source.mp4"
    _video(source)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "fixture",
                        "source": str(source),
                        "duration_sec": 1,
                        "event_types": ["SIGNAL"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps({"responses": [{"content": '{"candidates":[]}'}]}), encoding="utf-8"
    )

    def fail_write(result, root):
        raise OSError("secret filesystem diagnostic")

    monkeypatch.setattr("daesingo.search.diagnostic_cli.store_result", fail_write)
    code = main(
        [
            "--manifest",
            str(manifest),
            "--profile",
            "p3",
            "--provider-fixture",
            str(fixture),
        ]
    )
    output = capsys.readouterr()
    assert code == 1
    assert json.loads(output.out)["issue_code"] == "OUTPUT_WRITE_FAILED"
    assert json.loads(output.out)["status"] == "FAILED"
    assert "secret filesystem" not in output.out + output.err
