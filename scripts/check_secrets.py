"""Pinned, offline, counts-only pre-deploy secret scan. Never relay child output."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.request
import zipfile


VERSION = "8.30.1"
CONFIG_SHA = "e163e53b9e7e8a8511e77271e2b323ed057759542a6d988258afe3a1fa329caf"
# Official release asset digests; executable digests independently extracted
# after verifying those archives. Both are checked, including on cache reuse.
PINS = {
    "Windows": ("windows_x64.zip",
                "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
                "17157e2ee8b76fc8b1d8bee607a250e34b8a8023c8bc81822d4b5ee4d78fcb7c"),
    "Linux": ("linux_x64.tar.gz",
              "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
              "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"),
}


class ScanError(Exception):
    """Only fixed public error codes may cross the output boundary."""


PUBLIC_ERRORS = frozenset({
    "unsupported-platform", "integrity-failure", "installation-failure",
    "rules-preparation-failure", "git-query-failure", "incomplete-history",
    "partial-clone-unsupported", "grafted-history-unsupported", "unsafe-git-path",
    "unsupported-git-entry", "scanner-execution-failure", "scanner-report-failure",
    "scanner-result-mismatch", "repository-root-required", "invalid-deploy-target",
    "invalid-exceptions", "invalid-arguments", "operation-failure",
})
EXCEPTION_FILE = Path(__file__).with_name("secret_scan_exceptions.json")
EXCEPTION_REASONS = {"A01": "verified_measurement_expression", "A02": "synthetic_privacy_regression_fixture"}


@dataclass(frozen=True)
class ScanResult:
    findings: Counter
    exceptions: Counter


def validate_exceptions(entries: list[dict]) -> list[dict]:
    fields = {"id", "rule", "location_digest", "start_line", "end_line", "start_column",
              "end_column", "value_digest", "pattern_digest", "reason"}
    if not isinstance(entries, list) or len(entries) != 2:
        raise ScanError("invalid-exceptions")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ScanError("invalid-exceptions")
        identifier = entry["id"]
        if not isinstance(identifier, str) or identifier not in EXCEPTION_REASONS or identifier in seen:
            raise ScanError("invalid-exceptions")
        seen.add(identifier)
        if entry["rule"] != "generic-api-key" or entry["reason"] != EXCEPTION_REASONS[identifier]:
            raise ScanError("invalid-exceptions")
        for key in ("location_digest", "value_digest", "pattern_digest"):
            if not isinstance(entry[key], str) or re.fullmatch(r"[0-9a-f]{64}", entry[key]) is None:
                raise ScanError("invalid-exceptions")
        for key in ("start_line", "end_line", "start_column", "end_column"):
            if type(entry[key]) is not int or entry[key] < (1 if "line" in key else 0):
                raise ScanError("invalid-exceptions")
        if entry["end_line"] < entry["start_line"]:
            raise ScanError("invalid-exceptions")
        if entry["end_line"] == entry["start_line"] and entry["end_column"] < entry["start_column"]:
            raise ScanError("invalid-exceptions")
    return entries


def load_exceptions() -> list[dict]:
    try:
        data = json.loads(EXCEPTION_FILE.read_text(encoding="utf-8"))
        if set(data) != {"schema", "exceptions"} or type(data["schema"]) is not int or data["schema"] != 1:
            raise ScanError("invalid-exceptions")
        return validate_exceptions(data["exceptions"])
    except (OSError, ValueError, TypeError, KeyError):
        raise ScanError("invalid-exceptions") from None


def exception_template(entries: list[dict]) -> str:
    """Compare private fields inside Gitleaks; project only rule/anonymous IDs.

    Original values and even their hashes never cross the scanner stdout pipe.
    LF normalization only removes checkout line-ending differences. There is
    no regex/path wildcard, commit baseline or entire-rule bypass.
    """
    entries = validate_exceptions(entries)
    checks = []
    for entry in entries:
        predicates = [f'(eq .RuleID {json.dumps(entry["rule"])})']
        for field, key in (("StartLine", "start_line"), ("EndLine", "end_line"),
                           ("StartColumn", "start_column"), ("EndColumn", "end_column")):
            predicates.append(f'(eq .{field} {entry[key]})')
        expressions = {
            "location_digest": r'(.File | replace "\\" "/" | trimPrefix "./" | sha256sum)',
            "value_digest": r'(.Secret | replace "\r\n" "\n" | sha256sum)',
            "pattern_digest": r'(.Match | replace "\r\n" "\n" | sha256sum)',
        }
        predicates.extend(f'(eq {expression} {json.dumps(entry[key])})'
                          for key, expression in expressions.items())
        checks.append(("(and " + " ".join(predicates) + ")", entry["id"]))
    template = "RT15C_COUNTS_V2\n{{range .}}"
    for index, (condition, identifier) in enumerate(checks):
        template += "{{" + ("if " if index == 0 else "else if ") + condition + "}}allowed:" + identifier + "\n"
    return template + "{{else}}{{.RuleID}}\n{{end}}{{end}}"


def parse_report(code: int, stdout: bytes, stderr: bytes, rules: set[str]) -> ScanResult:
    if code not in {0, 42} or stderr:
        raise ScanError("scanner-execution-failure")
    try:
        lines = stdout.decode("ascii").splitlines()
    except UnicodeError:
        raise ScanError("scanner-report-failure") from None
    if not lines or lines[0] != "RT15C_COUNTS_V2":
        raise ScanError("scanner-report-failure")
    counts, allowed = Counter(), Counter()
    for line in lines[1:]:
        if line in rules:
            counts[line] += 1
        elif line in {"allowed:A01", "allowed:A02"}:
            allowed[line.removeprefix("allowed:")] += 1
        else:
            raise ScanError("scanner-report-failure")
    # Gitleaks still returns findings-exit42 when all findings were precisely
    # projected as exceptions. This is distinct from no scan/no report.
    if (code == 42) != bool(counts or allowed):
        raise ScanError("scanner-result-mismatch")
    return ScanResult(counts, allowed)


def pin():
    if platform.machine().lower() not in {"amd64", "x86_64"} or platform.system() not in PINS:
        raise ScanError("unsupported-platform")
    return PINS[platform.system()]


def checked(data: bytes, digest: str) -> bytes:
    if hashlib.sha256(data).hexdigest() != digest:
        raise ScanError("integrity-failure")
    return data


def binary_path(folder: Path) -> Path:
    return folder / ("gitleaks.exe" if platform.system() == "Windows" else "gitleaks")


def install(folder: Path) -> None:
    suffix, archive_sha, binary_sha = pin()
    folder.mkdir(parents=True, exist_ok=True)
    binary = binary_path(folder)
    if binary.exists() and (folder / "upstream.toml").exists():
        verify_tool(folder)
        return
    # No installer script, archive extraction paths or unpinned latest URLs.
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{suffix}"
    with urllib.request.urlopen(url, timeout=60) as response:
        archive = checked(response.read(), archive_sha)
    if suffix.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            executable = package.read("gitleaks.exe")
    else:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
            member = package.extractfile("gitleaks")
            if member is None:
                raise ScanError("installation-failure")
            executable = member.read()
    checked(executable, binary_sha)
    config_url = f"https://raw.githubusercontent.com/gitleaks/gitleaks/v{VERSION}/config/gitleaks.toml"
    with urllib.request.urlopen(config_url, timeout=60) as response:
        config = checked(response.read(), CONFIG_SHA)
    binary.write_bytes(executable)
    binary.chmod(0o700)
    (folder / "upstream.toml").write_bytes(config)
    verify_tool(folder)


def verify_tool(folder: Path) -> tuple[Path, str, set[str]]:
    _, _, digest = pin()
    binary = binary_path(folder)
    checked(binary.read_bytes(), digest)
    config = checked((folder / "upstream.toml").read_bytes(), CONFIG_SHA).decode("utf-8")
    # Keep upstream detector rules/regex allowlists but remove ALL global path
    # exemptions (including media, lock files and gitleaks.toml). Git membership,
    # not extension or broad local paths, defines our current file scope.
    config, replaced = re.subn(r"(?ms)^(paths = \[).*?^\]", "paths = []", config, count=1)
    if replaced != 1:
        raise ScanError("rules-preparation-failure")
    rules = {rule["id"] for rule in tomllib.loads(config)["rules"]}
    return binary, config, rules


def clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("GITLEAKS_", "GIT_"))}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
               GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.fsmonitor", GIT_CONFIG_VALUE_0="false",
               GIT_CONFIG_KEY_1="core.hooksPath", GIT_CONFIG_VALUE_1=os.devnull)
    return env


def captured(command: list[str], *, cwd: Path, env: dict[str, str], timeout=300):
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)


def git(repo: Path, *args: str) -> bytes:
    result = captured(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
                       "-C", str(repo), *args], cwd=repo, env=clean_env())
    if result.returncode:
        raise ScanError("git-query-failure")
    return result.stdout


def check_history(repo: Path) -> int:
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ScanError("incomplete-history")
    # Partial/promisor clones can cause implicit network I/O or absent objects.
    settings = git(repo, "config", "--local", "--name-only", "--list").lower()
    if b"partialclone" in settings or b"promisor" in settings:
        raise ScanError("partial-clone-unsupported")
    grafts = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "info/grafts").strip()))
    if (repo / grafts).exists():
        raise ScanError("grafted-history-unsupported")
    return int(git(repo, "rev-list", "--count", "HEAD").strip())


def snapshot_files(repo: Path) -> list[Path]:
    names = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    files = []
    for name in set(names) - {b""}:
        relative = Path(os.fsdecode(name))
        if relative.is_absolute() or ".." in relative.parts:
            raise ScanError("unsafe-git-path")
        source = repo / relative
        # Never follow a symlink/junction in a parent, or include submodules.
        if any(part.is_symlink() or part.is_junction() for part in (source, *source.parents) if part != repo):
            raise ScanError("unsupported-git-entry")
        if source.resolve().is_relative_to(repo) is False:
            raise ScanError("unsupported-git-entry")
        if not stat.S_ISREG(source.lstat().st_mode) or source.is_symlink():
            raise ScanError("unsupported-git-entry")
        files.append(source)
    return files


def run_scanner(binary: Path, scope: str, target: Path, work: Path, rules: set[str]) -> ScanResult:
    # Scan the view from its own cwd so File is a repository-relative identity,
    # independent of host/scratch names. Git patch paths are already relative.
    command = [str(binary), "dir" if scope == "snapshot" else "git", "." if scope == "snapshot" else str(target),
               "--config", str(work / "rules.toml"), "--gitleaks-ignore-path", str(work),
               # Values must be intact in memory to compare their fingerprints.
               # Only the fixed projection above can write the captured report.
               "--ignore-gitleaks-allow", "--redact=0", "--no-banner", "--no-color",
               "--log-level=error", "--exit-code=42", "--report-format=template",
               "--report-template", str(work / "counts.tmpl"), "--report-path=-",
               "--max-decode-depth=5", "--max-archive-depth=0", "--timeout=240"]
    if scope == "history":
        command += ["--log-opts=--full-history --root -m --no-ext-diff --no-textconv --no-show-signature --text --no-renames HEAD"]
    result = captured(command, cwd=target if scope == "snapshot" else work, env=clean_env())
    # stdout is ONLY the projection; stderr is captured even on errors and never
    # forwarded. Any diagnostic at error level means the scan was incomplete.
    return parse_report(result.returncode, result.stdout, result.stderr, rules)


def scan(repo: Path, folder: Path, scope: str, ancestor: str | None = None) -> int:
    started = time.monotonic()
    binary, config, rules = verify_tool(folder)
    if Path(os.fsdecode(git(repo, "rev-parse", "--show-toplevel").strip())).resolve() != repo:
        raise ScanError("repository-root-required")
    commits = check_history(repo) if scope != "snapshot" else 0
    if ancestor is not None:
        if scope == "snapshot" or re.fullmatch(r"[0-9a-f]{40}", ancestor) is None:
            raise ScanError("invalid-deploy-target")
        # Bind target revision to this exact scanned HEAD, not the moving remote
        # develop ref used by subsequent deployment metadata validation.
        git(repo, "merge-base", "--is-ancestor", ancestor, "HEAD")
    total = Counter()
    exceptions = Counter()
    template = exception_template(load_exceptions())
    files = snapshot_files(repo) if scope != "history" else []
    # The view contains hardlinks, not duplicated file contents. The scanner
    # only reads these links; never chmod/write any source link. Same filesystem
    # placement is deliberate. Unsupported hardlinks fail closed.
    with tempfile.TemporaryDirectory(prefix=".rt15c-", dir=repo) as temporary:
        work = Path(temporary)
        (work / "rules.toml").write_text(config, encoding="utf-8")
        (work / "counts.tmpl").write_text(template, encoding="utf-8")
        if scope != "history":
            view = work / "view"
            view.mkdir()
            for source in files:
                target = view / source.relative_to(repo)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, target)
            result = run_scanner(binary, "snapshot", view, work, rules)
            print(f"snapshot files={len(files)} findings={sum(result.findings.values())} exceptions={sum(result.exceptions.values())}")
            total.update(result.findings)
            exceptions.update(result.exceptions)
        if scope != "snapshot":
            result = run_scanner(binary, "history", repo, work, rules)
            print(f"history commits={commits} findings={sum(result.findings.values())} exceptions={sum(result.exceptions.values())}")
            total.update(result.findings)
            exceptions.update(result.exceptions)
    for rule, count in sorted(total.items()):
        print(f"rule={rule} findings={count}")
    for identifier, count in sorted(exceptions.items()):
        print(f"exception={identifier} occurrences={count}")
    print(f"secret-scan status={'findings' if total else 'clean'} elapsed_seconds={time.monotonic()-started:.2f}")
    return 1 if total else 0


def main(argv=None) -> int:
    class PrivateArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ScanError("invalid-arguments")

    parser = PrivateArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("install", "scan"))
    parser.add_argument("--tool-dir", required=True, type=Path)
    parser.add_argument("--repo", default=Path.cwd(), type=Path)
    parser.add_argument("--scope", choices=("both", "snapshot", "history"), default="both")
    parser.add_argument("--require-ancestor", default=None)
    try:
        args = parser.parse_args(argv)
        if args.operation == "install":
            install(args.tool_dir.resolve())
            print("secret-scanner installation verified")
            return 0
        return scan(args.repo.resolve(), args.tool_dir.resolve(), args.scope, args.require_ancestor)
    except ScanError as error:
        code = error.args[0] if len(error.args) == 1 else None
        code = code if isinstance(code, str) and code in PUBLIC_ERRORS else "operation-failure"
        print("secret-scan error=" + code, file=sys.stderr)
    except Exception:
        # Exception text can contain paths, URLs or source. Never expose it.
        print("secret-scan error=operation-failure", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
