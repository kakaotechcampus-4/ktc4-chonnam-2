"""Fixed-source publish boundaries only; no Docker/AWS/network is executed."""
import io
import hashlib
import json
from pathlib import Path
import tarfile

import pytest

from test_aws_deploy import module

CONTROL = 'a' * 40
TARGET = 'b' * 40
TREE = 'c' * 40
IMAGE = 'sha256:' + 'd' * 64


def test_fixed_revision_publish_entry_points_present():
    m = module()
    assert callable(getattr(m, 'prepare_publish', None)), 'fixed source preparation missing'
    assert callable(getattr(m, 'verify_publish_image', None)), 'pinned image identity check missing'


def archive(members=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as output:
        for name, data in (members or {'Dockerfile': b'FROM scratch\n', 'src/code.py': b'x=1\n'}).items():
            item = tarfile.TarInfo(name)
            item.size = len(data)
            output.addfile(item, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    m = module()
    assert hasattr(m, 'prepare_publish'), 'target-source preparation is missing'
    env = {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': 'refs/heads/develop',
           'GITHUB_REPOSITORY': m.REPOSITORY, 'GITHUB_REPOSITORY_ID': m.REPOSITORY_ID,
           'GITHUB_SHA': CONTROL, 'PUBLISH_REVISION': TARGET, 'RUNNER_TEMP': str(tmp_path),
           'GITHUB_OUTPUT': str(tmp_path / 'outputs'), 'RT14_EXECUTION_ENABLED': 'true',
           'AWS_REGION': m.REGION, 'AWS_ACCOUNT_ID': '1' * 12, 'ECR_REPOSITORY': 'runtime'}
    calls = []

    def command(argv, **kwargs):
        calls.append(argv)
        if argv == ['git', 'rev-parse', 'HEAD']:
            return CONTROL + '\n'
        if argv[:3] == ['git', 'cat-file', '-t']:
            return ('tree' if argv[-1].endswith('^{tree}') else 'commit') + '\n'
        if argv == ['git', 'rev-parse', TARGET + '^{tree}']:
            return TREE + '\n'
        if argv == ['git', 'merge-base', '--is-ancestor', TARGET, CONTROL]:
            return ''
        if argv == ['git', 'ls-tree', '-rz', TARGET]:
            return ''.join('100644 blob ' + hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                           + '\t' + name + '\0' for name, data in
                           {'Dockerfile': b'FROM scratch\n', 'src/code.py': b'x=1\n'}.items())
        if argv[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([{'Id': IMAGE, 'Os': 'linux', 'Architecture': 'amd64',
                'Config': {'Labels': {'org.opencontainers.image.revision': TARGET},
                           'Env': ['DAESINGO_REVISION=' + TARGET]}}])
        if argv[:2] in (['docker', 'login'], ['docker', 'tag'], ['docker', 'push'], ['docker', 'pull']):
            return ''
        pytest.fail('unexpected command boundary')

    monkeypatch.setattr(m, 'command', command)
    monkeypatch.setattr(m.tempfile, 'tempdir', str(tmp_path))
    monkeypatch.setattr(m, 'archive_revision', lambda revision: archive())
    gates = []
    monkeypatch.setattr(m, 'quality_gate', lambda env, revision=None: gates.append(revision))
    monkeypatch.setattr(m, 'aws', lambda *a, **k: pytest.fail('unexpected AWS boundary'))
    monkeypatch.setattr(m, 'oidc', lambda *a, **k: pytest.fail('unexpected OIDC boundary'))
    m.prepare_publish(env)
    return m, env, calls, gates


def test_prepare_binds_control_target_tree_and_clean_archive(prepared):
    m, env, calls, gates = prepared
    source, record = m.publish_paths(env)
    data = json.loads(record.read_text())
    assert data['control_revision'] == CONTROL and data['target_revision'] == TARGET
    assert data['target_tree'] == TREE and data['files']
    assert env['GITHUB_SHA'] == CONTROL
    assert (source / 'Dockerfile').read_bytes() == b'FROM scratch\n'
    assert gates == [None, TARGET]


@pytest.mark.parametrize('value', ['', 'develop', TARGET[:8], TARGET.upper(), TARGET + ';echo PRIVATE-CANARY'])
def test_publish_revision_has_no_fallback(prepared, value):
    m, env, _, _ = prepared
    with pytest.raises(m.DeployError):
        m.publish_revision({**env, 'PUBLISH_REVISION': value})


@pytest.mark.parametrize('failure', ['control', 'commit', 'tree', 'ancestry', 'control_ci', 'target_ci'])
def test_invalid_source_or_ci_cannot_prepare(prepared, tmp_path, monkeypatch, failure):
    m, env, calls, _ = prepared
    destination = tmp_path / failure
    destination.mkdir()
    env = {**env, 'RUNNER_TEMP': str(destination)}
    original = m.command

    def command(argv, **kwargs):
        if failure == 'control' and argv == ['git', 'rev-parse', 'HEAD']:
            return 'e' * 40
        if failure in ('commit', 'tree') and argv[:3] == ['git', 'cat-file', '-t']:
            if (failure == 'tree') == argv[-1].endswith('^{tree}'):
                return 'blob'
        if failure == 'ancestry' and argv[:3] == ['git', 'merge-base', '--is-ancestor']:
            raise m.DeployError('command_failed')
        return original(argv, **kwargs)

    def quality(env, revision=None):
        if (failure == 'control_ci' and revision is None) or (failure == 'target_ci' and revision == TARGET):
            raise m.DeployError('quality_gate_failed')

    monkeypatch.setattr(m, 'command', command)
    monkeypatch.setattr(m, 'quality_gate', quality)
    with pytest.raises(m.DeployError):
        m.prepare_publish(env)
    assert not m.publish_paths(env)[1].exists()


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'src/../../escape'])
def test_unsafe_archive_refused(prepared, tmp_path, monkeypatch, name):
    m, env, _, _ = prepared
    destination = tmp_path / 'unsafe'
    destination.mkdir()
    monkeypatch.setattr(m, 'archive_revision', lambda revision: archive({name: b'PRIVATE-CANARY'}))
    with pytest.raises(m.DeployError):
        m.prepare_publish({**env, 'RUNNER_TEMP': str(destination)})
    assert not (tmp_path / 'escape').exists()


@pytest.mark.parametrize('change', ['content', 'extra', 'target', 'control'])
def test_source_changes_cannot_reach_image_acceptance(prepared, change):
    m, env, _, _ = prepared
    source, record = m.publish_paths(env)
    if change in ('content', 'extra'):
        (source / ('Dockerfile' if change == 'content' else 'untracked.env')).write_text('PRIVATE-CANARY')
    else:
        data = json.loads(record.read_text())
        data[change + '_revision'] = 'e' * 40
        record.write_text(json.dumps(data))
    with pytest.raises(m.DeployError):
        m.verify_publish_image(env)


def test_image_identity_pins_safe_output_without_rewriting_context(prepared):
    m, env, _, _ = prepared
    m.verify_publish_image(env)
    record = json.loads(m.publish_paths(env)[1].read_text())
    assert record['image_id'] == IMAGE
    assert Path(env['GITHUB_OUTPUT']).read_text() == 'image_id=' + IMAGE + '\n'
    assert env['GITHUB_SHA'] == CONTROL


@pytest.mark.parametrize('field', ['label', 'environment', 'architecture', 'os', 'id'])
def test_wrong_image_identity_is_refused(prepared, monkeypatch, field):
    m, env, _, _ = prepared
    original = m.command

    def command(argv, **kwargs):
        result = original(argv, **kwargs)
        if argv[:3] == ['docker', 'image', 'inspect']:
            item, = json.loads(result)
            if field == 'label':
                item['Config']['Labels']['org.opencontainers.image.revision'] = CONTROL
            elif field == 'environment':
                item['Config']['Env'] = ['DAESINGO_REVISION=' + CONTROL]
            else:
                item[{'architecture': 'Architecture', 'os': 'Os', 'id': 'Id'}[field]] = 'invalid'
            result = json.dumps([item])
        return result

    monkeypatch.setattr(m, 'command', command)
    with pytest.raises(m.DeployError):
        m.verify_publish_image(env)


@pytest.mark.parametrize('existing', [False, True])
def test_publish_uses_target_tag_and_pinned_id_never_overwrites(prepared, monkeypatch, capsys, existing):
    import base64
    m, env, calls, _ = prepared
    m.verify_publish_image(env)
    registry = env['AWS_ACCOUNT_ID'] + '.dkr.ecr.' + m.REGION + '.amazonaws.com'
    requests = []

    def aws(args, **kwargs):
        requests.append(args)
        if args[:2] == ['ecr', 'describe-repositories']:
            return {'repositories': [{'imageTagMutability': 'IMMUTABLE'}]}
        if args[:2] == ['ecr', 'batch-get-image']:
            assert 'imageTag=' + TARGET in args
            return {'images': [{}], 'failures': []} if existing else {'images': [], 'failures': [{'failureCode': 'ImageNotFound'}]}
        if args[:2] == ['ecr', 'get-authorization-token']:
            return {'authorizationData': [{'proxyEndpoint': 'https://' + registry,
                'authorizationToken': base64.b64encode(b'AWS:PRIVATE-CANARY').decode()}]}
        if args[:2] == ['ecr', 'describe-images']:
            assert 'imageTag=' + TARGET in args
            return {'imageDetails': [{'imageDigest': 'sha256:' + 'e' * 64}]}
        pytest.fail('unexpected AWS operation')

    monkeypatch.setattr(m, 'aws', aws)
    if existing:
        with pytest.raises(m.DeployError):
            m.publish(env)
        assert not any(c[:2] == ['docker', 'push'] for c in calls)
        assert not any(a[:2] == ['ecr', 'get-authorization-token'] for a in requests)
    else:
        monkeypatch.setattr(m.os, 'environ', env)
        monkeypatch.setattr(m, 'oidc', lambda authenticated: authenticated)
        assert m.main(['publish']) == 0
        assert ['docker', 'tag', IMAGE, registry + '/runtime:' + TARGET] in calls
        assert any(c[:2] == ['docker', 'pull'] for c in calls)
    assert 'PRIVATE-CANARY' not in str(capsys.readouterr())


@pytest.mark.parametrize('operation', ['prepare-publish', 'publish-image'])
def test_pre_oidc_commands_finish_without_any_cloud_access(prepared, monkeypatch, tmp_path, operation):
    m, env, _, _ = prepared
    if operation == 'prepare-publish':
        destination = tmp_path / 'new-run'
        destination.mkdir()
        env = {**env, 'RUNNER_TEMP': str(destination)}
    monkeypatch.setattr(m.os, 'environ', env)
    assert m.main([operation]) == 0


@pytest.mark.parametrize('link_type', [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_archive_links_cannot_write_outside_source(prepared, tmp_path, monkeypatch, link_type):
    m, env, _, _ = prepared
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as output:
        member = tarfile.TarInfo('src/link')
        member.type, member.linkname = link_type, '../../PRIVATE-CANARY'
        output.addfile(member)
    destination = tmp_path / 'links'
    destination.mkdir()
    monkeypatch.setattr(m, 'archive_revision', lambda revision: buffer.getvalue())
    with pytest.raises(m.DeployError):
        m.prepare_publish({**env, 'RUNNER_TEMP': str(destination)})


def test_source_and_saved_manifest_cannot_be_forged_together(prepared):
    m, env, _, _ = prepared
    source, path = m.publish_paths(env)
    (source / 'Dockerfile').write_text('PRIVATE-CANARY')
    record = json.loads(path.read_text())
    record['files'] = m.source_files(source)
    path.write_text(json.dumps(record))
    with pytest.raises(m.DeployError):
        m.verify_publish_image(env)


@pytest.mark.parametrize('stage', ['control_ci', 'target_ci', 'missing_image'])
def test_publish_main_requires_both_ci_and_receipt_before_oidc(prepared, monkeypatch, stage):
    m, env, _, _ = prepared
    monkeypatch.setattr(m.os, 'environ', env)
    calls = []

    def quality(env, revision=None):
        calls.append(revision)
        if (stage == 'control_ci' and revision is None) or (stage == 'target_ci' and revision == TARGET):
            raise m.DeployError('quality_gate_failed')

    monkeypatch.setattr(m, 'quality_gate', quality)
    assert m.main(['publish']) == 1
    assert calls == ([None] if stage == 'control_ci' else [None, TARGET])


def test_digest_must_resolve_to_same_accepted_image(prepared, monkeypatch):
    import base64
    m, env, _, _ = prepared
    m.verify_publish_image(env)
    registry = env['AWS_ACCOUNT_ID'] + '.dkr.ecr.' + m.REGION + '.amazonaws.com'
    original = m.command

    def command(argv, **kwargs):
        value = original(argv, **kwargs)
        if argv[:3] == ['docker', 'image', 'inspect'] and '@sha256:' in argv[-1]:
            data = json.loads(value)
            data[0]['Id'] = 'sha256:' + 'f' * 64
            return json.dumps(data)
        return value

    def aws(args, **kwargs):
        if args[1] == 'describe-repositories':
            return {'repositories': [{'imageTagMutability': 'IMMUTABLE'}]}
        if args[1] == 'batch-get-image':
            return {'images': [], 'failures': [{'failureCode': 'ImageNotFound'}]}
        if args[1] == 'get-authorization-token':
            return {'authorizationData': [{'proxyEndpoint': 'https://' + registry,
                'authorizationToken': base64.b64encode(b'AWS:PRIVATE-CANARY').decode()}]}
        assert args[1] == 'describe-images'
        return {'imageDetails': [{'imageDigest': 'sha256:' + 'e' * 64}]}

    monkeypatch.setattr(m, 'command', command)
    monkeypatch.setattr(m, 'aws', aws)
    with pytest.raises(m.DeployError, match='published_digest_mismatch'):
        m.publish(env)
