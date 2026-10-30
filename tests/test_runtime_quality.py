"""Exercise the real quality entry point, including failures inside untyped code."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("src/daesingo/common", "src/daesingo/api", "src/daesingo/worker", "migrations/runtime")


@pytest.mark.parametrize("defect", [None, "lint", "type"])
def test_real_quality_command_accepts_clean_and_rejects_violations(tmp_path, defect):
    script = tmp_path / "scripts/check_runtime_quality.py"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/check_runtime_quality.py", script)
    shutil.copyfile(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    for index, target in enumerate(TARGETS):
        folder = tmp_path / target
        folder.mkdir(parents=True)
        (folder / f"quality_sample_{index}.py").write_text("value: int = 1\n", encoding="utf-8")
    # A new source file under migrations is checked too; it isn't in a fixed inventory.
    source = "value: int = 1\n"
    if defect == "lint":
        source = "import os\n"
    if defect == "type":
        source = "def untyped():\n    value: int = 'invalid'\n    return value\n"
    (tmp_path / TARGETS[-1] / "new_violation.py").write_text(source, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=120)
    if defect is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert ("F401" if defect == "lint" else "[assignment]") in result.stdout


@pytest.mark.parametrize("job", ["quality", "regression", "mysql"])
@pytest.mark.parametrize("result", ["success", "failure", "cancelled", "skipped", None])
def test_required_gate_includes_quality_and_fails_closed(job, result):
    from tests.ci_orchestration import required_success
    needs = {name: {"result": "success"} for name in ("quality", "regression", "mysql")}
    needs[job]["result"] = result
    assert required_success(needs) is (result == "success")


def test_workflow_quality_is_unconditional_and_uses_local_entry_point():
    workflow = (ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    quality = workflow.split("  quality:\n", 1)[1].split("  regression:\n", 1)[0]
    assert "uv sync --locked --extra quality" in quality
    assert "uv run --no-sync python scripts/check_runtime_quality.py" in quality
    assert "continue-on-error" not in quality
    assert "if:" not in quality
    assert "needs: [quality, regression, mysql]" in workflow
    assert "if: ${{ always() }}" in workflow
