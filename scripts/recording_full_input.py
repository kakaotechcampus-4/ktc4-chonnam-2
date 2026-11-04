"""원본 15개 읽기 전용 대조와 전체 logical scope 준비. encode/DB/Docker/전송 없음."""
import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

IDS = [f'input-{n:02}' for n in range(1, 16)]
PROFILE = 'full15-512m'


def finite_decimal(value):
    if isinstance(value, bool):
        raise ValueError('FINITE_DURATION_REQUIRED')
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise ValueError('FINITE_DURATION_REQUIRED')
    return result


def full_plan(manifest):
    records = manifest['files']
    if (manifest['file_count'] != 15 or len(records) != 15
            or [r['fixture_id'] for r in records] != IDS):
        raise ValueError('FULL_FIFTEEN_ORDER_REQUIRED')
    names = [r['filename'] for r in records]
    if (len(set(names)) != 15 or any(not isinstance(n, str) or Path(n).name != n
            or '/' in n or '\\' in n or ':' in n or n in ('', '.', '..') for n in names)):
        raise ValueError('EXACT_INPUT_BASENAMES_REQUIRED')
    offset, placements = Decimal(0), []
    for r in records:
        videos = [s for s in r['metadata']['streams'] if s.get('codec_type') == 'video']
        if (type(r['proposed_video_index']) is not int or r['proposed_video_index'] != 0
                or len(videos) != 1 or videos[0]['index'] != 0
                or type(r['bytes']) is not int or r['bytes'] <= 0
                or type(r['mtime_ns']) is not int or r['mtime_ns'] <= 0
                or not re.fullmatch('[0-9a-f]{64}', r['sha256'])):
            raise ValueError('INPUT_STREAM_STAT_OR_HASH_INVALID')
        duration = finite_decimal(r['metadata']['format']['duration'])
        end = offset + duration
        placements.append({'id': r['fixture_id'], 'start': float(offset), 'end': float(end), 'video_index': 0})
        offset = end
    if (manifest['total_bytes'] != sum(r['bytes'] for r in records)
            or finite_decimal(manifest['sum_metadata_duration_sec']) != offset):
        raise ValueError('MANIFEST_TOTAL_MISMATCH')
    return {'placements': placements, 'requested_sec': str(offset),
        'max_duration_ms': int((offset*1000).to_integral_value(rounding=ROUND_CEILING)),
        'total_bytes': manifest['total_bytes'], 'capture_continuity': 'UNKNOWN',
        'order_basis': 'existing_manifest_order_not_independent_capture_time_verification'}


def require_full_scope(placements, seconds):
    if [p['id'] for p in placements] != IDS:
        raise ValueError('FULL_FIFTEEN_REQUIRED')
    offset = Decimal(0)
    for p in placements:
        start, end = Decimal(str(p['start'])), finite_decimal(p['end'])
        if not start.is_finite() or start != offset or end <= start or p['video_index'] != 0:
            raise ValueError('FULL_PLACEMENT_GAP_OVERLAP_OR_STREAM')
        offset = end
    if finite_decimal(seconds) != offset:
        raise ValueError('FULL_ENDPOINT_REQUIRED_NO_PREFIX')


def stat_identity(path):
    s = path.stat()
    return s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino


def audit_sources(manifest, source_root, *, probe, timeout_sec=300):
    plan = full_plan(manifest)
    source = Path(source_root)
    if source.is_symlink() or source.resolve(strict=True) != Path(manifest['source_folder_private']).resolve(strict=True):
        raise ValueError('EXACT_SOURCE_ROOT_REQUIRED')
    source = source.resolve(strict=True)
    if {p.name for p in source.iterdir()} != {r['filename'] for r in manifest['files']}:
        raise ValueError('ORIGINAL_FILE_SET_MISMATCH')
    deadline, evidence = time.monotonic() + timeout_sec, []
    for r in manifest['files']:
        path = source/r['filename']
        if path.is_symlink() or not path.is_file():
            raise ValueError('EXACT_ORIGINAL_FILE_REQUIRED')
        before = stat_identity(path)
        if before[:2] != (r['bytes'], r['mtime_ns']):
            raise ValueError('INPUT_STAT_MISMATCH')
        h = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024*1024):
                if time.monotonic() >= deadline:
                    raise TimeoutError('INPUT_AUDIT_DEADLINE')
                h.update(block)
        if h.hexdigest() != r['sha256']:
            raise ValueError('INPUT_HASH_MISMATCH')
        observed = probe(path)
        expected = r['metadata']
        if (observed.get('streams') != expected['streams']
                or observed.get('format') != expected['format']):
            raise ValueError('INPUT_METADATA_MISMATCH')
        if time.monotonic() >= deadline:
            raise TimeoutError('INPUT_AUDIT_DEADLINE')
        if stat_identity(path) != before:
            raise ValueError('INPUT_CHANGED_DURING_READ')
        evidence.append({'id': r['fixture_id'], 'sha256': h.hexdigest(), 'bytes': before[0],
            'mtime_ns': before[1], 'hash_stat_metadata': 'PASS', 'video_index': 0})
    # 전체 대조가 끝나는 시점에도 앞서 읽은 원본의 stat을 다시 확인한다.
    for r in manifest['files']:
        if stat_identity(source/r['filename'])[:2] != (r['bytes'], r['mtime_ns']):
            raise ValueError('INPUT_CHANGED_DURING_AUDIT')
    return {'status': 'PASS_INPUT_AUDIT', 'verified_files': 15, 'files': evidence, **plan,
        'decode': 'NOT_RUN', 'recording': 'NOT_RUN', 'provider_calls': 0, 'transfer': 'NOT_RUN'}


def write_input_plan(manifest, output):
    plan = full_plan(manifest)
    output = Path(output).resolve()
    source = Path(manifest['source_folder_private']).resolve()
    if output.is_relative_to(source):
        raise ValueError('ORIGINAL_DIRECTORY_WRITE_FORBIDDEN')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    records, transfers = [], []
    for r in manifest['files']:
        safe = {k: r[k] for k in ('fixture_id', 'bytes', 'mtime_ns', 'sha256', 'proposed_video_index')}
        safe['filename'] = r['fixture_id']+'.mp4'
        records.append(safe)
        transfers.append({'source_private': str(source/r['filename']), **safe})
    smoke_duration = finite_decimal(manifest['files'][1]['metadata']['format']['duration'])
    values = {'manifest.private.json': {'files': records, 'full_scope': plan},
        'placements.private.json': {'full': plan['placements'], 'representative': plan['placements'][:2],
            'smoke': [{'id': 'input-02', 'start': 0.0, 'end': float(smoke_duration), 'video_index': 0}]},
        'transfer-plan.private.json': {'files': transfers, 'transfer': 'NOT_RUN',
            'warning': 'PRIVATE_LOCAL_PLAN_ONLY_NOT_PART_OF_FIXTURE_MOUNT'}}
    for name, value in values.items():
        with (output/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
        (output/name).chmod(0o600)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    try:
        manifest_raw = Path(args.manifest).read_bytes()
        manifest = json.loads(manifest_raw.decode('utf-8-sig'))
        source = Path(args.source_root).resolve(strict=True)
        if output.is_relative_to(source):
            raise ValueError('ORIGINAL_DIRECTORY_WRITE_FORBIDDEN')
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        from recording_cpu_quota_supervisor import bounded_capture
        binary = Path(shutil.which(args.ffprobe)).resolve(strict=True)
        version = bounded_capture([str(binary), '-version'], 10, output)
        if version.returncode:
            raise ValueError('FFPROBE_VERSION_FAILED')
        def probe(path):
            result = bounded_capture([str(binary), '-v', 'error', '-show_entries',
                'stream=index,codec_name,codec_type,width,height,avg_frame_rate,time_base,duration:format=duration',
                '-of', 'json', str(path)], 20, output)
            if result.returncode or result.stderr:
                raise ValueError('INPUT_FFPROBE_FAILED')
            return json.loads(result.stdout)
        report = audit_sources(manifest, source, probe=probe)
        report.update(manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
            ffprobe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            ffprobe_version=version.stdout.decode().splitlines()[0])
        write_input_plan(manifest, output/'input-plan')
        with (output/'audit.private.json').open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({k: report[k] for k in ('status', 'verified_files', 'requested_sec', 'total_bytes', 'capture_continuity')}))
        return 0
    except Exception as error:
        # 원본명·경로·stderr를 콘솔로 내보내지 않는다. 이전 증거를 덮어쓰지 않는다.
        print(json.dumps({'status': 'FAIL_INPUT_AUDIT', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
