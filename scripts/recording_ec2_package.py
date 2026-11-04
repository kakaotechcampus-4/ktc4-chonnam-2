"""HEAD 제품과 미커밋 하네스를 명시 allowlist로 묶는다. 원본/secret 전송은 하지 않는다."""
import argparse
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

SCRIPTS = {
    'recording_cpu_quota_supervisor.py', 'recording_cpu_quota_linux.py',
    'recording_cpu_quota_probe.py', 'recording_real_media_recheck.py',
    'recording_probe_budget.py', 'recording_capacity_probe.py',
    'recording_ec2_package.py', 'recording_ec2_host.py', 'recording_ec2_entry.py',
    'recording_full_input.py',
}
ROOT_FILES = {'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE', 'docker/runtime.py'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def allowed(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        return False
    if any(part.startswith('.') or part == '__pycache__' for part in p.parts):
        return False
    return (name in ROOT_FILES or (p.parent == PurePosixPath('scripts') and p.name in SCRIPTS)
            or (name.startswith('src/daesingo/') and p.suffix in ('.py', '.json', '.txt')
                and (p.suffix == '.py' or p.parent.name in ('prompt_resources', 'evidence')))
            or (name.startswith('migrations/') and p.suffix in ('.py', '.ini', '.mako')))


def verify_files(root, manifest):
    root = Path(root)
    expected = manifest['files']
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('PACKAGE_SYMLINK_FORBIDDEN')
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name == 'manifest.json':
            continue
        actual.add(name)
        if not allowed(name) or name not in expected or sha(path.read_bytes()) != expected[name]:
            raise ValueError('PACKAGE_CONTENT_MISMATCH')
    if actual != set(expected):
        raise ValueError('PACKAGE_FILE_SET_MISMATCH')


def build(repo, output, config):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])
    revision = git('rev-parse', 'HEAD').decode().strip()
    # 제품과 migration/lock은 commit 내용과 byte까지 같아야 한다.
    files = {}
    selected = [name for name in git('ls-tree', '-r', '--name-only', revision).decode().splitlines()
                if allowed(name) and not name.startswith('scripts/')]
    with tarfile.open(fileobj=io.BytesIO(git('archive', revision, '--', *selected))) as committed:
        for member in committed.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or member.name not in selected:
                raise ValueError('COMMITTED_SYMLINK_OR_UNKNOWN_FILE')
            name = member.name
            data = committed.extractfile(member).read()
            if (repo/name).read_bytes() != data:
                raise ValueError('UNCOMMITTED_PRODUCT_OR_DEPENDENCY_SOURCE')
            files[name] = data
    for name in SCRIPTS:
        files['scripts/'+name] = (repo/'scripts'/name).read_bytes()
    manifest = {'format': 'recording-ec2-package/v1', 'product_revision': revision,
                'harness_identity': 'content-sha256-precommit', 'config': config,
                'files': {name: sha(data) for name, data in sorted(files.items())}}
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tarfile.open(output/'source.tar', 'w', format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(files.items()):
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.mtime = len(data), 0o444, 0
            tar.addfile(item, io.BytesIO(data))
    manifest['archive_sha256'] = sha((output/'source.tar').read_bytes())
    (output/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    (output/'manifest.sha256').write_text(sha((output/'manifest.json').read_bytes())+'\n', encoding='ascii')
    return manifest


def prepare_inputs(manifest_path, output):
    """보호 전송 계획/최소 manifest만 작성한다. 원본은 읽거나 복사하지 않는다."""
    original = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    selected = original['files'][:2]
    if [r['fixture_id'] for r in selected] != ['input-01', 'input-02']:
        raise ValueError('EXPECTED_PROTECTED_INPUTS_REQUIRED')
    records, transfer, placements = [], [], []
    offset = Decimal(0)
    for record in selected:
        if record['proposed_video_index'] != 0:
            raise ValueError('EXPECTED_VIDEO_INDEX_REQUIRED')
        safe = {key: record[key] for key in ('fixture_id', 'bytes', 'mtime_ns', 'sha256', 'proposed_video_index')}
        safe['filename'] = record['fixture_id']+'.mp4'
        records.append(safe)
        transfer.append({'source_private': str(Path(original['source_folder_private'])/record['filename']), **safe})
        end = offset+Decimal(record['metadata']['format']['duration'])
        placements.append({'id': record['fixture_id'], 'start': float(offset), 'end': float(end), 'video_index': 0})
        offset = end
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = {'manifest.private.json': {'files': records},
              'placements.private.json': {'representative': placements,
                 'smoke': [{'id': 'input-02', 'start': 0.0,
                            'end': float(Decimal(selected[1]['metadata']['format']['duration'])), 'video_index': 0}]},
              'transfer-plan.private.json': {'files': transfer, 'source_read': 'NOT_RUN', 'transfer': 'NOT_RUN'}}
    for name, value in values.items():
        with (output/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
        (output/name).chmod(0o600)


def unpack(package, destination, expected):
    package, destination = Path(package), Path(destination)
    raw = (package/'manifest.json').read_bytes()
    if sha(raw) != expected:
        raise ValueError('MANIFEST_IDENTITY_MISMATCH')
    manifest = json.loads(raw)
    archive = package/'source.tar'
    if sha(archive.read_bytes()) != manifest['archive_sha256']:
        raise ValueError('ARCHIVE_IDENTITY_MISMATCH')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or set(names) != set(manifest['files']):
            raise ValueError('ARCHIVE_MEMBER_SET_MISMATCH')
        for member in members:
            if not member.isfile() or not allowed(member.name) or member.size > 16*1024**2:
                raise ValueError('ARCHIVE_MEMBER_FORBIDDEN')
            data = tar.extractfile(member).read()
            if sha(data) != manifest['files'][member.name]:
                raise ValueError('ARCHIVE_MEMBER_HASH_MISMATCH')
            target = destination/member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            target.chmod(0o444)
    (destination/'manifest.json').write_bytes(raw)
    verify_files(destination, manifest)
    (destination/'manifest.json').chmod(0o444)
    for directory in sorted((p for p in destination.rglob('*') if p.is_dir()), reverse=True):
        directory.chmod(0o555)
    destination.chmod(0o555)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    b.add_argument('--repo', default='.')
    b.add_argument('--output', required=True)
    b.add_argument('--config', required=True)
    u = sub.add_parser('unpack')
    u.add_argument('--package', required=True)
    u.add_argument('--destination', required=True)
    u.add_argument('--manifest-sha256', required=True)
    i = sub.add_parser('inputs')
    i.add_argument('--manifest', required=True)
    i.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        if args.action == 'build':
            build(args.repo, args.output, json.loads(Path(args.config).read_text(encoding='utf-8-sig')))
        elif args.action == 'unpack':
            unpack(args.package, args.destination, args.manifest_sha256)
        else:
            prepare_inputs(args.manifest, args.output)
        print('PASS_PACKAGE')
    except Exception as error:
        print(json.dumps({'status': 'FAIL_PACKAGE', 'error_type': type(error).__name__}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
