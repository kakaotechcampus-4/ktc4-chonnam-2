"""Real offline scanner controls; all credential-like data is generated synthetic data."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

import unittest
import tempfile
import shlex
import hashlib


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_secrets.py"


def scanner_module():
    if __package__:
        from . import check_secrets
    else:
        import check_secrets
    return check_secrets


class SafeControlResult(unittest.TextTestResult):
    """Control failures must not echo source, paths, exception text or buffers."""

    def _exc_info_to_string(self, err, test):
        return "Synthetic control failed; details suppressed."

    def _restoreStdout(self):
        self._mirrorOutput = False
        super()._restoreStdout()


def git(repo, *args, data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, timeout=30)
    if result.returncode:
        raise AssertionError("synthetic Git setup failed (output suppressed)")
    return result.stdout


def create_repo(tmp_path):
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "config", "user.name", "Synthetic control")
    git(tmp_path, "config", "user.email", "synthetic@example.invalid")
    (tmp_path / "sample.txt").write_text("safe example\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "synthetic root")
    return tmp_path


def tool_dir():
    value = os.environ.get("RT15C_TEST_TOOL_DIR")
    if value:
        return Path(value).resolve()
    # The explicit control command always requires a pinned installation.
    raise AssertionError("set RT15C_TEST_TOOL_DIR after pinned scanner installation")


def scan(repo, *, scope="both", tool=None, env=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "scan", "--repo", str(repo),
         "--tool-dir", str(tool or tool_dir()), "--scope", scope],
        capture_output=True, timeout=120, env=env,
    )
    return result


def synthetic():
    # Never an issued credential. Construct to avoid storing a contiguous token.
    return "ghp_" + "A9b8C7d6E5f4G3h2I1j0K9l8M7n6O5p4Q3r2"


def safe_output(result, sentinel):
    if sentinel.encode() in result.stdout + result.stderr:
        raise AssertionError("synthetic sentinel escaped capture boundary")
    if b"ADJACENT_SENTINEL" in result.stdout + result.stderr:
        raise AssertionError("synthetic adjacent code escaped capture boundary")


def reviewed_sources():
    """Resolve only two hashed locations privately; never log their paths/code."""
    scanner = scanner_module()
    entries = scanner.load_exceptions()
    names = scanner.git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    paths = {hashlib.sha256(name.replace(b"\\", b"/")).hexdigest(): Path(os.fsdecode(name))
             for name in names if name}
    result = []
    for entry in entries:
        relative = paths[entry["location_digest"]]
        source = ROOT / relative
        if source.stat().st_size > 64_000:
            raise AssertionError("reviewed control source unexpectedly large")
        result.append((entry, relative, source.read_text(encoding="utf-8")))
    return result


def replace_reviewed_value(text, entry):
    """Change only the reviewed value, preserving path/line/width/coordinates."""
    lines = text.splitlines(keepends=True)
    if entry["start_line"] != entry["end_line"]:
        raise AssertionError("control requires a single-line reviewed match")
    line = lines[entry["start_line"] - 1]
    candidates = [line[i:j] for i in range(len(line)) for j in range(i + 1, len(line) + 1)
                  if hashlib.sha256(line[i:j].encode()).hexdigest() == entry["value_digest"]]
    if len(candidates) != 1:
        raise AssertionError("reviewed value fingerprint mismatch")
    value = candidates[0]
    # Generic-only synthetic credential: no provider-specific prefix. Construct
    # it so this test's source is not itself a new contiguous credential.
    replacement = ("N7q1B8v2C9w3" + "D0x4E1y5F2z6G3h7J4k8L5m9")[:len(value)]
    if len(replacement) != len(value):
        raise AssertionError("synthetic replacement width mismatch")
    lines[entry["start_line"] - 1] = line.replace(value, replacement, 1)
    return "".join(lines), replacement


class SecretScanControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rt15c-control-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name).resolve()
        self.repo = create_repo(self.work)

    def test_reviewed_exceptions_only_and_same_position_new_values_fail(self):
        sources = reviewed_sources()
        for changed, _, _ in sources:
            with self.subTest(anonymous=changed["id"]):
                repo = self.work / ("reviewed-" + changed["id"])
                repo.mkdir()
                create_repo(repo)
                for entry, relative, text in sources:
                    destination = repo / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(text, encoding="utf-8")
                git(repo, "add", ".")
                git(repo, "commit", "-qm", "reviewed false positives only")
                clean = scan(repo)
                assert clean.returncode == 0
                assert b"exception=A01" in clean.stdout and b"exception=A02" in clean.stdout
                for entry, relative, text in sources:
                    if entry["id"] == changed["id"]:
                        replacement, token = replace_reviewed_value(text, entry)
                        (repo / relative).write_text(replacement, encoding="utf-8")
                red = scan(repo, scope="snapshot")
                safe_output(red, token)
                assert red.returncode == 1 and b"rule=generic-api-key" in red.stdout
                git(repo, "add", ".")
                git(repo, "commit", "-qm", "new synthetic value at same reviewed position")
                historical_red = scan(repo, scope="history")
                safe_output(historical_red, token)
                assert historical_red.returncode == 1 and b"rule=generic-api-key" in historical_red.stdout

    def test_safe_official_example_and_text_media_path(self):
        # Upstream aws-access-token permits this public EXAMPLE suffix only.
        example = "AKIA" + "IOSFODNN7EXAMPLE"
        (self.repo / ".env.example").write_text("AWS_ACCESS_KEY_ID=" + example, encoding="utf-8")
        assert scan(self.repo).returncode == 0
        # A file extension, including media, must not exempt textual secrets.
        (self.repo / "sample.png").write_text(synthetic(), encoding="utf-8")
        assert scan(self.repo).returncode == 1

    def test_real_child_streams_and_report_projection_hide_sentinels(self):
        scanner = scanner_module()
        token = synthetic()
        (self.repo / ("ADJACENT_SENTINEL-" + token)).write_text(
            "ADJACENT_SENTINEL token=" + token, encoding="utf-8")
        original = scanner.captured
        streams = []

        def observe(command, **kwargs):
            result = original(command, **kwargs)
            if Path(command[0]).name.startswith("gitleaks"):
                streams.append(result)
            return result

        with patch.object(scanner, "captured", side_effect=observe):
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                result = scanner.scan(self.repo, tool_dir(), "snapshot")
        assert result == 1 and streams
        for stream in streams:
            safe_output(stream, token)
            assert stream.stdout.splitlines()[0] == b"RT15C_COUNTS_V2"
        if token in output.getvalue() + error.getvalue():
            raise AssertionError("wrapper sentinel disclosure")

    def test_real_scanner_error_diagnostics_are_captured(self):
        scanner = scanner_module()
        original = scanner.captured

        def break_scanner(command, **kwargs):
            if Path(command[0]).name.startswith("gitleaks"):
                command = [*command, "--SYNTHETIC_PRIVATE_DIAGNOSTIC"]
            return original(command, **kwargs)

        with patch.object(scanner, "captured", side_effect=break_scanner):
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                result = scanner.main(["scan", "--repo", str(self.repo), "--tool-dir", str(tool_dir())])
        assert result == 2
        if "SYNTHETIC_PRIVATE_DIAGNOSTIC" in output.getvalue() + error.getvalue():
            raise AssertionError("scanner diagnostic disclosure")

    def test_real_cli_red_green_and_no_report(self):
        repo = self.repo
        assert scan(repo).returncode == 0
        token = synthetic()
        source = repo / "sample.txt"
        source.write_text(f"ADJACENT_SENTINEL token={token}\n", encoding="utf-8")
        result = scan(repo)
        safe_output(result, token)
        assert result.returncode == 1
        assert b"github-pat" in result.stdout
        source.write_text("safe example\n", encoding="utf-8")
        assert scan(repo).returncode == 0
        assert not list(repo.rglob("*.json"))


    def test_new_files_and_ignored_paths_do_not_hide_tracked_secrets(self):
        repo = self.repo
        token = synthetic()
        (repo / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        scratch = repo / "scratch"
        scratch.mkdir()
        (scratch / "ignored.txt").write_text(token, encoding="utf-8")
        assert scan(repo, scope="snapshot").returncode == 0
        git(repo, "add", "-f", "scratch/ignored.txt")
        result = scan(repo, scope="snapshot")
        safe_output(result, token)
        assert result.returncode == 1
        git(repo, "reset", "-q", "HEAD", "scratch/ignored.txt")
        (repo / "new.txt").write_text(token, encoding="utf-8")
        assert scan(repo, scope="snapshot").returncode == 1


    def test_deleted_secret_in_root_history_is_detected(self):
        repo = self.repo
        token = synthetic()
        (repo / "sample.txt").write_text(token, encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "--amend", "--no-edit", "-q")
        (repo / "sample.txt").write_text("clean now\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "remove synthetic data")
        assert scan(repo, scope="snapshot").returncode == 0
        result = scan(repo, scope="history")
        safe_output(result, token)
        assert result.returncode == 1


    def test_deleted_side_history_is_detected(self):
        repo = self.repo
        git(repo, "checkout", "-qb", "side")
        (repo / "side.txt").write_text(synthetic(), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "synthetic side secret")
        (repo / "side.txt").unlink()
        git(repo, "add", "-u")
        git(repo, "commit", "-qm", "remove side secret")
        git(repo, "checkout", "-q", "main")
        git(repo, "merge", "--no-ff", "--no-commit", "side")
        (repo / "resolution.txt").write_text("clean resolution", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "synthetic merge resolution")
        assert scan(repo, scope="history").returncode == 1

    def test_only_merge_resolution_secret_is_detected(self):
        repo = self.repo
        git(repo, "checkout", "-qb", "side")
        (repo / "side.txt").write_text("clean side", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "clean side")
        git(repo, "checkout", "-q", "main")
        git(repo, "merge", "--no-ff", "--no-commit", "side")
        (repo / "resolution.txt").write_text(synthetic(), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "synthetic merge resolution")
        (repo / "resolution.txt").unlink()
        git(repo, "add", "-u")
        git(repo, "commit", "-qm", "clean after merge")
        assert scan(repo, scope="snapshot").returncode == 0
        assert scan(repo, scope="history").returncode == 1

    def test_partial_clone_is_rejected_without_fetch(self):
        git(self.repo, "config", "extensions.partialclone", "origin")
        assert scan(self.repo, scope="history").returncode == 2

    def test_git_binary_attribute_cannot_hide_text_secret_history(self):
        repo = self.repo
        (repo / ".gitattributes").write_text("sample.txt -diff\n", encoding="utf-8")
        (repo / "sample.txt").write_text(synthetic(), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "synthetic attributed data")
        (repo / "sample.txt").write_text("clean now", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "remove synthetic data")
        assert scan(repo, scope="history").returncode == 1

    def test_required_deploy_target_must_belong_to_scanned_head(self):
        repo = self.repo
        head = git(repo, "rev-parse", "HEAD").strip().decode("ascii")
        base = [sys.executable, str(SCRIPT), "scan", "--repo", str(repo),
                "--tool-dir", str(tool_dir()), "--require-ancestor"]
        for target, expected in [(head, 0), ("f" * 40, 2), ("", 2), ("invalid", 2)]:
            result = subprocess.run([*base, target], capture_output=True, timeout=120)
            assert result.returncode == expected

    def test_history_does_not_execute_signature_verifier(self):
        repo = self.repo
        headers, body = git(repo, "cat-file", "-p", "HEAD").split(b"\n\n", 1)
        signed = headers + b"\ngpgsig -----BEGIN PGP SIGNATURE-----\n synthetic\n -----END PGP SIGNATURE-----\n\n" + body
        sha = git(repo, "hash-object", "-t", "commit", "-w", "--stdin", data=signed).strip().decode("ascii")
        git(repo, "update-ref", "HEAD", sha)
        marker = self.work / "verifier-executed"
        probe = self.work / ("probe.cmd" if os.name == "nt" else "probe.sh")
        if os.name == "nt":
            probe.write_text('@echo off\r\necho synthetic > "' + str(marker) + '"\r\nexit /b 1\r\n', encoding="utf-8")
        else:
            probe.write_text("#!/bin/sh\nprintf synthetic > " + shlex.quote(str(marker)) + "\nexit 1\n", encoding="utf-8")
            probe.chmod(0o700)
        git(repo, "config", "log.showSignature", "true")
        git(repo, "config", "gpg.program", str(probe))
        assert scan(repo, scope="history").returncode == 0
        assert not marker.exists()


    def test_shallow_history_fails_instead_of_passing(self):
        repo = self.repo
        tmp_path = self.work
        clone = tmp_path / "shallow"
        git(repo, "clone", "--depth=1", "file:///" + repo.as_posix().lstrip("/"), str(clone))
        assert scan(clone, scope="history").returncode == 2


    def test_missing_or_corrupt_tool_fails_without_echo(self):
        repo = self.repo
        tmp_path = self.work
        missing = tmp_path / "missing"
        assert scan(repo, tool=missing).returncode == 2
        copy = tmp_path / "corrupt"
        shutil.copytree(tool_dir(), copy)
        binary = copy / ("gitleaks.exe" if os.name == "nt" else "gitleaks")
        binary.write_bytes(b"not executable")
        assert scan(repo, tool=copy).returncode == 2


    def test_repository_config_and_inline_suppression_cannot_disable_detection(self):
        repo = self.repo
        (repo / ".gitleaks.toml").write_text("[allowlist]\nregexes=['.*']\n", encoding="utf-8")
        (repo / ".gitleaksignore").write_text("*\n", encoding="utf-8")
        (repo / "sample.txt").write_text(synthetic() + " # gitleaks:allow\n", encoding="utf-8")
        env = dict(os.environ, GITLEAKS_CONFIG_TOML="[allowlist]\nregexes=['.*']")
        assert scan(repo, env=env).returncode == 1


    def test_sensitive_filename_never_appears_in_output(self):
        repo = self.repo
        token = synthetic()
        (repo / f"ADJACENT_SENTINEL-{token}.txt").write_text(token, encoding="utf-8")
        result = scan(repo)
        safe_output(result, token)
        assert result.returncode == 1

class ControlError(Exception):
    pass


def _run_controls(argv):
    import argparse
    if not __debug__:
        raise ControlError("optimized-assertions")

    class PrivateParser(argparse.ArgumentParser):
        def error(self, message):
            raise ControlError("invalid-arguments")

    parser = PrivateParser()
    parser.add_argument("--tool-dir", required=True)
    args = parser.parse_args(argv)
    os.environ["RT15C_TEST_TOOL_DIR"] = str(Path(args.tool_dir).resolve())
    program = unittest.main(module=__name__, argv=[sys.argv[0]], exit=False, testRunner=unittest.TextTestRunner(
        verbosity=2, buffer=True, resultclass=SafeControlResult))
    return program.result


def main(argv=None):
    # This also covers framework/setup failures outside a test method. Never
    # forward buffered output, even if a dependency prints before raising.
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = _run_controls(argv)
            passed = result.wasSuccessful()
            total, failures, errors = result.testsRun, len(result.failures), len(result.errors)
            if type(passed) is not bool or any(type(value) is not int or value < 0 for value in (total, failures, errors)):
                raise ControlError("operation-failure")
            if total == 0 or result.skipped or result.expectedFailures:
                raise ControlError("incomplete-controls")
    except ControlError as error:
        code = error.args[0] if len(error.args) == 1 else None
        code = code if isinstance(code, str) and code in {
            "invalid-arguments", "optimized-assertions", "incomplete-controls"
        } else "operation-failure"
        print("secret-controls error=" + code, file=sys.stderr)
        return 2
    except SystemExit as error:
        if error.code == 0:
            print("usage: secret_scan_controls.py --tool-dir PATH")
            return 0
        print("secret-controls error=invalid-arguments", file=sys.stderr)
        return 2
    except Exception:
        print("secret-controls error=operation-failure", file=sys.stderr)
        return 2
    print(f"synthetic-controls tests={total} failures={failures} errors={errors}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
