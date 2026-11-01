"""Offline wrapper failure policy; real scanner controls live outside regression."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import check_secrets as scan


def test_checksum_failure_does_not_accept_changed_download():
    with pytest.raises(scan.ScanError, match="integrity-failure"):
        scan.checked(b"changed archive", hashlib.sha256(b"approved archive").hexdigest())


@pytest.mark.parametrize("returncode,stdout,stderr", [
    (1, b"RT15C_COUNTS_V1\n", b"private diagnostic"),
    (0, b"", b""),
    (0, b"RT15C_COUNTS_V1\nunknown-rule\n", b""),
    (42, b"RT15C_COUNTS_V1\n", b""),
    (0, b"RT15C_COUNTS_V1\ngithub-pat\n", b""),
    (42, b"RT15C_COUNTS_V1\ngithub-pat\n", b"private diagnostic"),
])
def test_invalid_or_incomplete_scanner_execution_cannot_pass(monkeypatch, returncode, stdout, stderr):
    monkeypatch.setattr(scan, "captured", lambda *a, **k: subprocess.CompletedProcess([], returncode, stdout, stderr))
    with pytest.raises(scan.ScanError):
        scan.run_scanner(Path("unused"), "snapshot", Path("."), Path("."), {"github-pat"})


@pytest.mark.parametrize("returncode,lines,expected", [
    (0, b"RT15C_COUNTS_V2\n", {}),
    (42, b"RT15C_COUNTS_V2\ngithub-pat\ngithub-pat\n", {"github-pat": 2}),
])
def test_counts_projection_preserves_detection_status(monkeypatch, returncode, lines, expected):
    monkeypatch.setattr(scan, "captured", lambda *a, **k: subprocess.CompletedProcess([], returncode, lines, b""))
    result = scan.run_scanner(Path("unused"), "snapshot", Path("."), Path("."), {"github-pat"})
    assert result.findings == expected
    assert result.exceptions == {}


def test_exception_message_and_child_output_never_escape_main(monkeypatch, capsys):
    sentinel = "SYNTHETIC_PRIVATE_DIAGNOSTIC"

    def failure(*args):
        raise OSError(sentinel)

    monkeypatch.setattr(scan, "scan", failure)
    assert scan.main(["scan", "--tool-dir", "."]) == 2
    output = capsys.readouterr()
    if sentinel in output.out + output.err:
        pytest.fail("diagnostic escaped capture boundary")
    assert "operation-failure" in output.err


def test_failed_download_cannot_become_successful_install(monkeypatch, tmp_path, capsys):
    class Download:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b"tampered download"

    monkeypatch.setattr(scan.urllib.request, "urlopen", lambda *a, **k: Download())
    assert scan.main(["install", "--tool-dir", str(tmp_path)]) == 2
    assert "integrity-failure" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_inherited_config_cannot_disable_rules_or_trigger_lazy_fetch(monkeypatch):
    monkeypatch.setenv("GITLEAKS_CONFIG_TOML", "[allowlist]\nregexes=['.*']")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "untrusted command")
    env = scan.clean_env()
    assert "GITLEAKS_CONFIG_TOML" not in env
    assert "untrusted command" not in env.values()
    assert env["GIT_NO_LAZY_FETCH"] == "1"


def test_untrusted_scanerror_message_is_not_a_public_error_code(monkeypatch, capsys):
    sentinel = "PRIVATE_ERROR_SENTINEL"

    def failure(*args):
        raise scan.ScanError(sentinel)

    monkeypatch.setattr(scan, "scan", failure)
    assert scan.main(["scan", "--tool-dir", "."]) == 2
    output = capsys.readouterr()
    if sentinel in output.out + output.err:
        pytest.fail("untrusted exception escaped public error boundary")


def test_invalid_cli_arguments_do_not_echo_values_paths_or_urls(capsys):
    sentinel = "PRIVATE_ARGUMENT_SENTINEL"
    try:
        result = scan.main(["scan", "--tool-dir", ".", "--unknown=https://synthetic.invalid/" + sentinel])
    except SystemExit as error:
        result = error.code
    assert result == 2
    output = capsys.readouterr()
    if sentinel in output.out + output.err:
        pytest.fail("invalid argument escaped public error boundary")


def test_malformed_report_and_error_streams_do_not_escape(monkeypatch, capsys):
    sentinel = "PRIVATE_REPORT_SENTINEL"

    def fail_scan(*args):
        monkeypatch.setattr(scan, "captured", lambda *a, **k: subprocess.CompletedProcess(
            [], 42, ('{"source":"' + sentinel + '"}').encode(),
            ("https://synthetic.invalid/" + sentinel).encode()))
        return scan.run_scanner(Path("unused"), "snapshot", Path("."), Path("."), {"github-pat"})

    monkeypatch.setattr(scan, "scan", fail_scan)
    assert scan.main(["scan", "--tool-dir", "."]) == 2
    output = capsys.readouterr()
    if sentinel in output.out + output.err:
        pytest.fail("untrusted child streams escaped capture")


def test_only_named_exceptions_may_convert_findings_to_success():
    assert hasattr(scan, "parse_report"), "missing strict exception report parser"
    result = scan.parse_report(42, b"RT15C_COUNTS_V2\nallowed:A01\nallowed:A02\n", b"", {"generic-api-key"})
    assert result.findings == {}
    assert result.exceptions == {"A01": 1, "A02": 1}
    result = scan.parse_report(42, b"RT15C_COUNTS_V2\nallowed:A01\ngeneric-api-key\n", b"", {"generic-api-key"})
    assert result.findings == {"generic-api-key": 1}


@pytest.mark.parametrize("code,report", [
    (0, b"RT15C_COUNTS_V2\nallowed:A01\n"),
    (42, b"RT15C_COUNTS_V2\n"),
    (42, b"RT15C_COUNTS_V2\nallowed:unknown\n"),
])
def test_incomplete_or_unknown_exception_reports_fail_closed(code, report):
    assert hasattr(scan, "parse_report"), "missing strict exception report parser"
    with pytest.raises(scan.ScanError):
        scan.parse_report(code, report, b"", {"generic-api-key"})


def test_control_runner_suppresses_failure_context_and_test_streams():
    import io
    import unittest
    from contextlib import redirect_stdout, redirect_stderr
    from scripts import secret_scan_controls as controls

    assert hasattr(controls, "SafeControlResult"), "missing control error output boundary"
    sentinel = "PRIVATE_CONTROL_SENTINEL"

    class BrokenSyntheticControl(unittest.TestCase):
        def runTest(self):
            print(sentinel)
            print(sentinel, file=sys.stderr)
            raise OSError("https://synthetic.invalid/" + sentinel)

    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        result = unittest.TextTestRunner(stream=output, buffer=True,
                                        resultclass=controls.SafeControlResult).run(BrokenSyntheticControl())
    assert not result.wasSuccessful()
    if sentinel in output.getvalue():
        pytest.fail("synthetic control error escaped runner")


def test_control_cli_argument_errors_are_also_private():
    script = Path(__file__).resolve().parents[1] / "scripts/secret_scan_controls.py"
    sentinel = "PRIVATE_CONTROL_ARGUMENT_SENTINEL"
    result = subprocess.run([sys.executable, str(script), "--tool-dir", "unused", "--unknown=" + sentinel],
                            capture_output=True, timeout=30)
    assert result.returncode == 2
    if sentinel.encode() in result.stdout + result.stderr:
        pytest.fail("control CLI argument escaped error boundary")


def test_optimized_python_cannot_turn_mandatory_assertions_into_a_pass():
    script = Path(__file__).resolve().parents[1] / "scripts/secret_scan_controls.py"
    result = subprocess.run([sys.executable, "-O", str(script), "--help"], capture_output=True, timeout=30)
    assert result.returncode == 2


@pytest.mark.parametrize("boundary", ["resolve", "runner"])
def test_control_setup_failures_and_printed_streams_are_captured(monkeypatch, capsys, boundary):
    from scripts import secret_scan_controls as controls
    import io
    import unittest
    from contextlib import redirect_stdout, redirect_stderr
    sentinel = "PRIVATE_CONTROL_SETUP_SENTINEL"

    def failure(*args, **kwargs):
        print(sentinel)
        print(sentinel, file=sys.stderr)
        raise OSError("https://synthetic.invalid/" + sentinel)

    if boundary == "resolve":
        class BrokenPath:
            def __init__(self, *args):
                pass

            def resolve(self):
                return failure()

        monkeypatch.setattr(controls, "Path", BrokenPath)
    else:
        monkeypatch.setattr(unittest, "main", failure)
    captured = io.StringIO()
    escaped = False
    with redirect_stdout(captured), redirect_stderr(captured):
        try:
            code = controls.main(["--tool-dir", "unused"])
        except Exception:
            escaped = True
    if escaped:
        pytest.fail("control setup escaped output boundary", pytrace=False)
    assert code == 2
    output = capsys.readouterr()
    if sentinel in captured.getvalue() + output.out + output.err:
        pytest.fail("control setup stream escaped capture")


def test_control_success_payload_cannot_smuggle_a_non_numeric_report(monkeypatch, capsys):
    from scripts import secret_scan_controls as controls
    sentinel = "PRIVATE_SUCCESS_PAYLOAD_SENTINEL"

    class BadResult:
        testsRun = sentinel
        failures = []
        errors = []
        skipped = []
        expectedFailures = []

        def wasSuccessful(self):
            return True

    monkeypatch.setattr(controls, "_run_controls", lambda argv: BadResult())
    result = controls.main(["--tool-dir", "unused"])
    output = capsys.readouterr()
    if sentinel in output.out + output.err:
        pytest.fail("framework success payload escaped fixed summary boundary")
    assert result == 2


@pytest.mark.parametrize("missing", ["empty", "skipped", "expected_failure"])
def test_mandatory_controls_cannot_pass_without_execution(monkeypatch, missing):
    import unittest
    from scripts import secret_scan_controls as controls
    result = unittest.TestResult()
    result.testsRun = 0 if missing == "empty" else 1
    if missing == "skipped":
        result.skipped.append((None, "synthetic skipped control"))
    if missing == "expected_failure":
        result.expectedFailures.append((None, "synthetic expected failure"))
    monkeypatch.setattr(controls, "_run_controls", lambda argv: result)
    assert controls.main(["--tool-dir", "unused"]) == 2


def test_current_exceptions_cannot_hide_a_subsequent_history_failure(monkeypatch, tmp_path, capsys):
    from collections import Counter
    monkeypatch.setattr(scan, "verify_tool", lambda folder: (tmp_path / "unused", "fixed rules", {"generic-api-key"}))
    monkeypatch.setattr(scan, "git", lambda repo, *args: str(repo).encode())
    monkeypatch.setattr(scan, "check_history", lambda repo: 1)
    monkeypatch.setattr(scan, "snapshot_files", lambda repo: [])
    monkeypatch.setattr(scan, "load_exceptions", lambda: [])
    monkeypatch.setattr(scan, "exception_template", lambda entries: "fixed projection")
    scopes = []

    def scanner(binary, scope, target, work, rules):
        scopes.append(scope)
        if scope == "snapshot":
            return scan.ScanResult(Counter(), Counter({"A01": 1}))
        raise scan.ScanError("scanner-execution-failure")

    monkeypatch.setattr(scan, "run_scanner", scanner)
    assert scan.main(["scan", "--repo", str(tmp_path), "--tool-dir", str(tmp_path)]) == 2
    assert scopes == ["snapshot", "history"]
    output = capsys.readouterr()
    assert "status=clean" not in output.out
