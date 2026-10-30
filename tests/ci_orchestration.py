"""PR test orchestration; no product logic or alternative strict checker.

Run with the same interpreter/dependencies as pytest. All evidence stays in a
fresh directory on this runner; no downloaded or prior-run reports are inputs.
"""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
GATE = 'tests/common/db/integration/test_migration_gate.py'
SMOKE = 'tests/recording/test_ci_media_smoke.py'
PARTITIONS = ('regression', 'mysql', 'media', 'gate')
ARTIFACTS = ('mysql.json', 'mysql.xml', 'catalog.json', 'collection.json')


def pytest_arguments(partition):
    # The same definitions drive execution and the independent collection audit.
    return {
        'full': ['tests'],
        'regression': ['tests', '--ignore='+GATE, '--ignore='+SMOKE, '-m', 'not mysql'],
        'mysql': ['tests', '--ignore='+GATE, '-m', 'mysql'],
        'media': [SMOKE],
        'gate': [GATE],
    }[partition]


def pytest_command(partition, *extra):
    return [sys.executable, '-B', '-X', 'utf8', '-m', 'pytest',
            *pytest_arguments(partition), '-q', '-p', 'no:cacheprovider', *extra]


def validate_partitions(collections):
    full = Counter(collections['full'])
    if not full or any(count != 1 for count in full.values()):
        raise ValueError('Full collection is empty or duplicated')
    union = Counter()
    for name in PARTITIONS:
        if not collections[name]:
            raise ValueError('Empty execution partition: '+name)
        union.update(collections[name])
    if union != full:
        raise ValueError('Partition omission/duplication: '+json.dumps({
            'missing': list((full-union).elements()),
            'extra': list((union-full).elements())}))
    return {key: len(value) for key, value in collections.items()}


def collect_partitions(root, output, env=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    collections = {}
    for name in ('full', *PARTITIONS):
        path = output / (name+'.json')
        # A failed collection must never leave a previous successful manifest.
        path.unlink(missing_ok=True)
        with (output / (name+'.log')).open('wb') as log:
            subprocess.run(pytest_command(name, '--collect-only', '-p', 'tests.ci_collection',
                '--ci-collection='+str(path)), cwd=root, env=env,
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        collections[name] = json.loads(path.read_text(encoding='utf-8'))
    counts = validate_partitions(collections)
    (output/'summary.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')
    print('Collection partitions PASS: '+json.dumps(counts), flush=True)
    return collections


def required_success(needs):
    return (isinstance(needs, dict) and set(needs) == {'quality', 'regression', 'mysql'}
            and all(isinstance(value, dict) and value.get('result') == 'success'
                    for value in needs.values()))


def current_context():
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    workflow_sha = os.environ.get('GITHUB_SHA', revision)
    if workflow_sha != revision:
        raise ValueError('Workflow SHA does not match the checkout')
    return {'revision':revision, 'workflow_sha':workflow_sha,
            'run_id':os.environ.get('GITHUB_RUN_ID', 'local'),
            'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT', 'local')}


def _selection(directory):
    report = json.loads((directory/'mysql.json').read_text(encoding='utf-8'))
    collection = json.loads((directory/'collection.json').read_text(encoding='utf-8'))
    selected = report['selected']
    if (not collection or len(set(collection)) != len(collection)
            or Counter(selected) != Counter(collection)
            or Counter(item['nodeid'] for item in report['collected']) != Counter(collection)):
        raise ValueError('Actual MySQL collection/selection mismatch')
    return report


def seal_evidence(directory, token, started_ns):
    directory = Path(directory)
    if not token or any((directory/name).stat().st_mtime_ns < started_ns for name in ARTIFACTS):
        raise ValueError('Stale MySQL artifacts')
    _selection(directory)
    manifest = {'context':current_context(), 'token':token,
                'sha256':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
                          for name in ARTIFACTS}}
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def load_evidence(directory, token):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if not token or manifest['token'] != token or manifest['context'] != current_context():
        raise ValueError('MySQL evidence belongs to another invocation/revision')
    if set(manifest['sha256']) != set(ARTIFACTS) or any(
            hashlib.sha256((directory/name).read_bytes()).hexdigest() != manifest['sha256'][name]
            for name in ARTIFACTS):
        raise ValueError('MySQL artifact changed or is incomplete')
    return (_selection(directory), directory/'mysql.xml',
            json.loads((directory/'catalog.json').read_text(encoding='utf-8')))


def _run_stage(name, command, directory, env, timeout=None):
    start = time.monotonic()
    outcome = 'failed'
    try:
        # Inherit stdout/stderr so an active test is visible on remote runners.
        subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=timeout)
        outcome = 'success'
    finally:
        record = {'stage':name, 'outcome':outcome, 'seconds':time.monotonic()-start}
        with (directory/'timings.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record)+'\n')
        print('CI stage: '+json.dumps(record), flush=True)


def run_mysql(output):
    if os.environ.get('PYTEST_ADDOPTS', '').strip():
        raise ValueError('External pytest selection options are forbidden in CI orchestration')
    if not os.environ.get('DAESINGO_MYSQL_URL'):
        raise ValueError('A disposable MySQL URL is required')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='mysql-', dir=output))
    token = uuid4().hex
    env = dict(os.environ, DAESINGO_REQUIRE_MYSQL='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8',
               RT12_CATALOG_EVIDENCE=str(directory/'catalog.json'))
    started_ns = time.time_ns()
    _run_stage('canonical-mysql', pytest_command('mysql',
        '-vv', '-p', 'tests.observability_capture', '-p', 'tests.ci_collection',
        '--ci-collection='+str(directory/'collection.json'),
        '--basetemp='+str(directory/'actual-temp'), '--mysql-report='+str(directory/'mysql.json'),
        '--junitxml='+str(directory/'mysql.xml')), directory, env, timeout=1500)
    _run_stage('strict', [sys.executable, 'scripts/check_mysql_test_report.py',
        str(directory/'mysql.json'), str(directory/'mysql.xml')], directory, env)
    seal_evidence(directory, token, started_ns)
    env.update(DAESINGO_MYSQL_GATE_EVIDENCE=str(directory), DAESINGO_MYSQL_GATE_TOKEN=token)
    _run_stage('actual-report-mutations', pytest_command('gate',
        '--basetemp='+str(directory/'gate-temp'), '--junitxml='+str(directory/'gate.xml')),
        directory, env)
    # The verification stage must leave every original input byte intact.
    load_evidence(directory, token)
    return directory


def main():
    command, *args = sys.argv[1:]
    if command == 'required':
        try:
            accepted = required_success(json.loads(os.environ['CI_REQUIRED_RESULTS']))
        except (KeyError, ValueError, TypeError):
            accepted = False
        print('Required CI '+('PASS' if accepted else 'FAILED'))
        return 0 if accepted else 1
    if command == 'collect':
        collect_partitions(ROOT, args[0])
    elif command == 'mysql':
        print('MySQL evidence: '+str(run_mysql(args[0])))
    elif command == 'regression':
        subprocess.run(pytest_command('regression', '--junitxml='+str(Path(args[0]).resolve())),
                       cwd=ROOT, check=True)
    else:
        raise ValueError('Unknown CI command')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
