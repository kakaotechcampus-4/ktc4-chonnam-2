"""CI must preserve selection, fail closed, and consume only this run's evidence."""

from collections import Counter
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
GATE = "tests/common/db/integration/test_migration_gate.py"
SMOKE = "tests/recording/test_ci_media_smoke.py"


def orchestration():
    return importlib.import_module("tests.ci_orchestration")


def test_real_collection_partitions_preserve_legacy_mysql_and_smoke(tmp_path):
    # Use pytest's actual marker selection and the real legacy harness hook.
    files = {
        "tests/case/test_store_mysql.py": "def test_legacy(): pass\n",
        "tests/case/test_case_repository_contract.py": (
            "import pytest\n@pytest.mark.parametrize('repo_conn',['sqlite','mysql'])\n"
            "def test_contract(repo_conn): pass\n"),
        "tests/test_unit.py": "def test_unit(): pass\n",
        "tests/test_process.py": "import pytest\npytestmark=pytest.mark.mysql\ndef test_process(): pass\n",
        GATE: "import pytest\npytestmark=pytest.mark.mysql\ndef test_gate(): pass\n",
        SMOKE: "def test_smoke(): pass\n",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "conftest.py").write_text("pytest_plugins=['mysql_harness']\n", encoding="utf-8")
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.pytest.ini_options]\nmarkers=["mysql"]\n', encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tests'))))
    for key in ('DAESINGO_REQUIRE_MYSQL', 'DAESINGO_MYSQL_URL', 'PYTEST_ADDOPTS'):
        env.pop(key, None)
    collections = orchestration().collect_partitions(tmp_path, tmp_path / 'audit', env)
    assert {key: len(value) for key, value in collections.items()} == {
        'full': 7, 'regression': 2, 'mysql': 3, 'media': 1, 'gate': 1}
    assert collections['mysql'] == [
        'tests/case/test_case_repository_contract.py::test_contract[mysql]',
        'tests/case/test_store_mysql.py::test_legacy',
        'tests/test_process.py::test_process',
    ]
    assert collections['regression'] == [
        'tests/case/test_case_repository_contract.py::test_contract[sqlite]',
        'tests/test_unit.py::test_unit',
    ]


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'extra', 'empty', 'full_duplicate'])
def test_partition_audit_rejects_uncovered_or_repeated_execution(defect):
    values = {'full': ['unit','sql','smoke','gate'], 'regression':['unit'],
              'mysql':['sql'], 'media':['smoke'], 'gate':['gate']}
    if defect == 'missing': values['mysql'] = ['other']
    if defect == 'duplicate': values['regression'].append('sql')
    if defect == 'extra': values['regression'].append('other')
    if defect == 'empty': values['media'] = []
    if defect == 'full_duplicate': values['full'].append('sql')
    with pytest.raises(ValueError):
        orchestration().validate_partitions(values)


@pytest.mark.parametrize('job', ['regression', 'mysql'])
@pytest.mark.parametrize('result', ['failure','cancelled','skipped',None,'','success'])
def test_required_result_accepts_only_success_for_every_dependency(job, result):
    needs = {'regression':{'result':'success'}, 'mysql':{'result':'success'}}
    needs[job]['result'] = result
    assert orchestration().required_success(needs) is (result == 'success')


def test_required_result_rejects_absent_or_unexpected_dependencies():
    assert not orchestration().required_success({})
    assert not orchestration().required_success({'regression':{'result':'success'}})
    assert not orchestration().required_success({
        'regression':{'result':'success'},'mysql':{'result':'success'},'other':{'result':'failure'}})


def evidence(tmp_path, monkeypatch):
    api = orchestration()
    context = {'revision':'checkout', 'workflow_sha':'merge', 'run_id':'run', 'run_attempt':'1'}
    monkeypatch.setattr(api, 'current_context', lambda: dict(context))
    started = time.time_ns() - 1_000_000_000
    files = {
        'mysql.json': json.dumps({'collected':[{'nodeid':'sql'}], 'selected':['sql']}),
        'mysql.xml': '<testsuite><testcase name="sql"/></testsuite>',
        'catalog.json': json.dumps({'events':[], 'violations':0}),
        'collection.json': json.dumps(['sql']),
    }
    for name, value in files.items(): (tmp_path / name).write_text(value, encoding='utf-8')
    api.seal_evidence(tmp_path, 'current-token', started)
    return api, context


def test_current_evidence_is_accepted_without_modifying_source_reports(tmp_path, monkeypatch):
    api, _ = evidence(tmp_path, monkeypatch)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    report, junit, catalog = api.load_evidence(tmp_path, 'current-token')
    assert report['selected'] == ['sql']
    assert junit == tmp_path / 'mysql.xml'
    assert catalog == {'events':[], 'violations':0}
    assert before == {p.name:p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('file', ['mysql.json','mysql.xml','catalog.json','collection.json'])
@pytest.mark.parametrize('mutation', ['change','remove'])
def test_evidence_rejects_changed_or_absent_artifacts(tmp_path, monkeypatch, file, mutation):
    api, _ = evidence(tmp_path, monkeypatch)
    path = tmp_path / file
    if mutation == 'change': path.write_text('{}', encoding='utf-8')
    else: path.unlink()
    with pytest.raises((ValueError, OSError)):
        api.load_evidence(tmp_path, 'current-token')


@pytest.mark.parametrize('field', ['revision','workflow_sha','run_id','run_attempt'])
def test_evidence_rejects_another_checkout_or_workflow_attempt(tmp_path, monkeypatch, field):
    api, context = evidence(tmp_path, monkeypatch)
    context[field] = 'other'
    with pytest.raises(ValueError): api.load_evidence(tmp_path, 'current-token')


def test_evidence_rejects_previous_invocation_token(tmp_path, monkeypatch):
    api, _ = evidence(tmp_path, monkeypatch)
    with pytest.raises(ValueError): api.load_evidence(tmp_path, 'previous-token')


def test_evidence_cannot_be_sealed_over_stale_or_partial_selection(tmp_path, monkeypatch):
    api, _ = evidence(tmp_path, monkeypatch)
    with pytest.raises(ValueError): api.seal_evidence(tmp_path, 'token', time.time_ns()+1_000_000_000)
    (tmp_path/'collection.json').write_text('["sql","absent"]', encoding='utf-8')
    with pytest.raises(ValueError): api.seal_evidence(tmp_path, 'token', 0)


def test_mysql_command_runs_complete_inventory_once_with_visible_output(tmp_path, monkeypatch):
    api = orchestration()
    invocations = []
    def run(command, **kwargs):
        invocations.append((command, kwargs))
        if 'tests' in command:
            # The external pytest is the expensive boundary; stop before any
            # fabricated evidence could be accepted as real execution.
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(api.subprocess, 'run', run)
    monkeypatch.setenv('DAESINGO_MYSQL_URL','mysql+pymysql://root@localhost/test')
    monkeypatch.delenv('PYTEST_ADDOPTS', raising=False)
    with pytest.raises(subprocess.CalledProcessError): api.run_mysql(tmp_path)
    command, kwargs = invocations[-1]
    assert command.count('tests') == 1
    assert command[command.index('-m', command.index('pytest'))+1] == 'mysql'
    assert '--ignore='+GATE in command
    assert kwargs['timeout'] == 1500
    assert not any(k in kwargs for k in ('capture_output','stdout','stderr'))
    assert len([cmd for cmd, _ in invocations if 'pytest' in cmd]) == 1
    assert not list(tmp_path.rglob('manifest.json'))


def test_cli_required_uses_fail_closed_exit_status(tmp_path):
    env = dict(os.environ, CI_REQUIRED_RESULTS=json.dumps({
        'regression':{'result':'success'}, 'mysql':{'result':'skipped'}}))
    result = subprocess.run([sys.executable,'-m','tests.ci_orchestration','required'],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    env['CI_REQUIRED_RESULTS'] = json.dumps({
        'regression':{'result':'success'}, 'mysql':{'result':'success'}})
    result = subprocess.run([sys.executable,'-m','tests.ci_orchestration','required'],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
