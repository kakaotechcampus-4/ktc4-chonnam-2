"""Run the real CLI: missing rules/resolution must let a negative control fail."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ("jobs", "usage", "db", "config", "logging", "storage")
DOMAINS = (
    ("src/daesingo/case", "daesingo.case"),
    ("src/daesingo/recording", "daesingo.recording"),
    ("src/daesingo/search", "daesingo.search"),
    ("src/daesingo/readout", "daesingo.readout"),
    ("src/daesingo/evidence", "daesingo.evidence"),
    ("eval", "eval"),
    ("apps/web", "apps.web"),
)


@pytest.fixture
def boundary_cli(tmp_path):
    script = tmp_path / "scripts/check_boundaries.py"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/check_boundaries.py", script)

    def run(relative, source, only="boundaries"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(script), "--only=" + only], cwd=tmp_path,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    return run


def rejected(result, path, target, line=1):
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[boundary/import/" in result.stdout, result.stdout
    assert f"{path}:{line}" in result.stdout, result.stdout
    assert target in result.stdout, result.stdout
    assert not result.stderr


@pytest.mark.parametrize("common", COMMON)
@pytest.mark.parametrize("domain,target", DOMAINS)
@pytest.mark.parametrize("form", ["import", "from", "parent"])
def test_common_cannot_import_any_domain(boundary_cli, common, domain, target, form):
    path = f"src/daesingo/common/{common}/new/nested.py"
    parent, _, name = target.rpartition(".")
    source = {
        "import": f"import os, {target}.detail as harmless\n",
        "from": f"from {target}.detail import Value as harmless\n",
        "parent": f"from {parent} import {name} as harmless\n" if parent else
                  f"import {target} as harmless\n",
    }[form]
    rejected(boundary_cli(path, source), path, target)


@pytest.mark.parametrize("domain,_", DOMAINS)
@pytest.mark.parametrize("target", ["api", "worker"])
@pytest.mark.parametrize("source", [
    "import daesingo.{target}.composition as harmless\n",
    "from daesingo.{target} import composition as harmless\n",
    "from daesingo import {target} as harmless\n",
    "from daesingo.{target} import *\n",
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import daesingo.{target}\n",
    "def lazy():\n    from daesingo import {target}\n",
    "try:\n    import daesingo.{target}  # noqa: boundary\nexcept ImportError:\n    pass\n",
])
def test_domain_cannot_import_composition_roots(boundary_cli, domain, _, target, source):
    path = domain + "/new/nested.py"
    line = 3 if "TYPE_CHECKING" in source else 2 if source.startswith(("def", "try")) else 1
    rejected(boundary_cli(path, source.format(target=target)), path, "daesingo." + target, line)


@pytest.mark.parametrize("path,source,target", [
    ("src/daesingo/common/jobs/probe.py", "from ...case import Value\n", "daesingo.case"),
    ("src/daesingo/common/usage/__init__.py", "from ... import search as x\n", "daesingo.search"),
    ("src/daesingo/common/db/deep/probe.py", "from ....recording import Value\n", "daesingo.recording"),
    ("src/daesingo/common/config/deep/__init__.py", "from .... import evidence\n", "daesingo.evidence"),
    ("src/daesingo/common/logging/probe.py", "from ...readout.api import Value\n", "daesingo.readout"),
    ("src/daesingo/common/storage/probe.py", "from ...case import *\n", "daesingo.case"),
    ("src/daesingo/case/probe.py", "from .. import worker as x\n", "daesingo.worker"),
    ("src/daesingo/recording/__init__.py", "from ..api import Value\n", "daesingo.api"),
    ("src/daesingo/search/deep/probe.py", "from ... import api\n", "daesingo.api"),
    ("src/daesingo/readout/deep/__init__.py", "from ...worker import *\n", "daesingo.worker"),
    ("src/daesingo/evidence/probe.py", "from ..worker.composition import Value\n", "daesingo.worker"),
])
def test_relative_import_uses_containing_package(boundary_cli, path, source, target):
    rejected(boundary_cli(path, source), path, target)


@pytest.mark.parametrize("path,source", [
    ("src/daesingo/common/jobs/probe.py", '# import daesingo.case\ntext = "from daesingo import worker"\n'),
    ("src/daesingo/common/jobs/probe.py", "import daesingo.casebook, evaluation, apps.website\n"),
    ("src/daesingo/common/config/probe.py", "from daesingo.common import jobs, usage, db, config, logging, storage\n"),
    ("src/daesingo/common/storage/probe.py", "from ..jobs import Value\nfrom . import helper\n"),
    ("src/daesingo/common/usage/deep/__init__.py", "from ...jobs import Value\n"),
    ("src/daesingo/case/probe.py", "from daesingo.readout import api\nfrom daesingo.common.jobs import Value\n"),
    ("src/daesingo/readout/probe.py", "from . import api\nfrom .api import Value\n"),
    ("src/daesingo/readout/deep/__init__.py", "from .. import api\n"),
    ("src/daesingo/search/probe.py", "import api, worker, daesingo.api_client, daesingo.workers\n"),
    ("src/daesingo/search/probe.py", "from unrelated.daesingo.worker import Value\n"),
    ("src/daesingo/case/probe.py", "from daesingo import search as worker\nfrom daesingo.common import jobs as api\n"),
    ("eval/runners/probe.py", "from .. import paths\nfrom daesingo.search import Value\n"),
    ("apps/web/tools/probe.py", "from .. import api\n"),
    ("src/daesingo/api/probe.py", "from daesingo.case import Value\nfrom daesingo.worker import Value\n"),
    ("src/daesingo/worker/probe.py", "from daesingo.search import Value\nfrom daesingo.api import Value\n"),
])
def test_allowed_imports_and_non_import_text_pass(boundary_cli, path, source):
    result = boundary_cli(path, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr


@pytest.mark.parametrize("path,token", [
    ("src/daesingo/case/probe.py", "130MB"),
    ("src/daesingo/recording/probe.py", "신호위반"),
    ("src/daesingo/search/probe.py", "if eval_mode"),
    ("src/daesingo/readout/probe.py", "기한"),
    ("src/daesingo/evidence/probe.py", "import search"),
    ("eval/probe.py", "import case"),
    ("apps/web/probe.ts", "threshold"),
])
def test_original_string_rules_still_reject_even_comments(boundary_cli, path, token):
    result = boundary_cli(path, "# " + token + "\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "금지 문자열" in result.stdout


def test_unparseable_scoped_python_is_not_silently_skipped(boundary_cli):
    path = "src/daesingo/common/jobs/probe.py"
    result = boundary_cli(path, "from daesingo.case import (\n")
    rejected(result, path, "AST")
