"""Linux 연결·유한 감독·소유권의 합성 controls. 실제 성능 측정이 아니다."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


def module(name):
    scripts = Path(__file__).parents[2] / 'scripts'
    sys.path.insert(0, str(scripts))
    try:
        path = scripts / (name + '.py')
        assert path.exists(), '실제 연결 모듈이 필요합니다'
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path.pop(0)


def test_bridge_resolves_leaf_without_namespace_escape(tmp_path):
    bridge = module('recording_cpu_quota_linux')
    leaf = tmp_path / 'docker' / 'owned'
    leaf.mkdir(parents=True)
    assert bridge.resolve_leaf(tmp_path, '0::/docker/owned\n') == leaf
    for raw in ('0::/../escape', '0::/../../escape', '1:cpu:/docker/owned', '0::/missing'):
        with pytest.raises(ValueError):
            bridge.resolve_leaf(tmp_path, raw)


def test_real_limit_validation_checks_quota_affinity_and_parent():
    bridge = module('recording_cpu_quota_linux')
    value = {'cpu_max': '150000 100000', 'cpuset': '0-1', 'memory_max': 1280*1024**2,
             'memory_swap_max': 0}
    bridge.require_limits(value, '1.5', 1280, affinity={0, 1})
    for key, changed in [('cpu_max','200000 100000'), ('cpuset','1'), ('memory_max', 1024), ('memory_swap_max', 1)]:
        with pytest.raises(ValueError):
            bridge.require_limits({**value, key: changed}, '1.5', 1280, affinity={0, 1})
    with pytest.raises(ValueError):
        bridge.require_parent_limits([{'cpu_max':'100000 100000','cpuset':'0-1'}])
    bridge.require_parent_limits([{'cpu_max': 'max 100000', 'cpuset': '0-17'}])


def test_finite_stop_blocks_later_arm_and_cleans_even_on_timeout():
    supervisor = module('recording_cpu_quota_supervisor')
    calls = []
    class Fake:
        def stage(self, arm):
            calls.append(('stage', arm))
            if arm == 'A1':
                raise TimeoutError('CONTROL')
        def cleanup(self, arm):
            calls.append(('cleanup', arm))
    with pytest.raises(TimeoutError):
        supervisor.measure_sequence(Fake())
    assert calls == [('stage','smoke'),('cleanup','smoke'),('stage','A1'),('cleanup','A1')]


def test_ownership_and_inspect_limits_are_not_configuration_claims():
    supervisor = module('recording_cpu_quota_supervisor')
    value = {'Config':{'Labels':{'owner':'cpu-quota-test'}},'HostConfig':{
        'NanoCpus':1500000000,'CpusetCpus':'0,1','Memory':1280*1024**2,'MemorySwap':1280*1024**2},
        'State':{'OOMKilled':False},'RestartCount':0}
    supervisor.require_inspect(value, 'cpu-quota-test', '1.5', 1280, '0,1')
    value['HostConfig']['NanoCpus']=2000000000
    with pytest.raises(RuntimeError):
        supervisor.require_inspect(value, 'cpu-quota-test', '1.5', 1280, '0,1')


def test_real_tool_wrapper_restores_on_failure_and_protects_raw(tmp_path):
    bridge = module('recording_cpu_quota_linux')
    class Tool:
        def _run(self, argv):
            raise RuntimeError('CONTROL')
    from contextlib import contextmanager
    class Observer:
        @contextmanager
        def phase(self, name):
            yield {'id':0}
    original = Tool._run
    path = tmp_path/'argv.private.jsonl'
    with pytest.raises(RuntimeError):
        with bridge.capture_tools(Tool, Observer(), path):
            Tool()._run(['ffprobe','-show_frames','/inputs/private-source.mp4'])
    assert Tool._run is original
    assert 'private-source.mp4' in path.read_text()


def test_inspect_error_is_not_absence():
    supervisor=module('recording_cpu_quota_supervisor')
    fake=object.__new__(supervisor.Supervisor)
    fake.log=lambda *args:None
    fake.docker=lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'[]',stderr=b'permission denied')
    with pytest.raises(RuntimeError,match='INSPECT'):
        fake.inspect('container','owned',check=False)


def test_inspect_recognizes_actual_lowercase_not_found_only():
    supervisor=module('recording_cpu_quota_supervisor')
    fake=object.__new__(supervisor.Supervisor)
    fake.docker=lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'[]',stderr=b'error: no such object: owned\n')
    assert fake.inspect('container','owned',check=False) is None


def test_cleanup_retains_resource_on_inspect_failure(tmp_path):
    supervisor=module('recording_cpu_quota_supervisor')
    fake=object.__new__(supervisor.Supervisor)
    fake.owner='cpu-quota-test'
    fake.created=[('container','cpu-quota-test-a1-runner')]
    fake.root=tmp_path
    fake.log=lambda *a:None
    def failed(*args,**kwargs):
        raise RuntimeError('INSPECT_FAILED')
    fake.inspect=failed
    with pytest.raises(RuntimeError,match='OWNED_CLEANUP_FAILED'):
        fake.cleanup('A1')
    assert fake.created==[('container','cpu-quota-test-a1-runner')]


def test_identity_includes_manifest_and_config(tmp_path,monkeypatch):
    supervisor=module('recording_cpu_quota_supervisor')
    (tmp_path/'src').mkdir()
    (tmp_path/'scripts').mkdir()
    manifest=tmp_path/'.codex-scratch/capacity-input15-20261102/manifest.private.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text('fixed')
    root=tmp_path/'experiment'
    root.mkdir()
    (root/'config.json').write_text('fixed-config')
    for filename in ('recording_cpu_quota_supervisor.py','recording_cpu_quota_linux.py','recording_cpu_quota_probe.py',
            'recording_real_media_recheck.py','recording_probe_budget.py','recording_capacity_probe.py'):
        (tmp_path/'scripts'/filename).write_text('fixed')
    monkeypatch.setattr(supervisor,'REPO',tmp_path)
    fake=object.__new__(supervisor.Supervisor)
    fake.root=root
    a=fake.snapshot_identity()
    manifest.write_text('changed')
    b=fake.snapshot_identity()
    assert a!=b
    (root/'config.json').write_text('changed-config')
    assert b!=fake.snapshot_identity()


def test_cgroup_mount_is_readonly_and_hierarchy_change_is_rejected():
    bridge=module('recording_cpu_quota_linux')
    assert bridge.require_readonly_cgroup('1 2 0:1 / /sys/fs/cgroup ro,nosuid - cgroup2 cgroup rw\n')
    with pytest.raises(ValueError):
        bridge.require_readonly_cgroup('1 2 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n')
    with pytest.raises(ValueError):
        bridge.require_same_hierarchy({'cpu_max':'max 100000'},{'cpu_max':'100000 100000'})


def test_late_container_exit_is_still_timeout(monkeypatch):
    supervisor=module('recording_cpu_quota_supervisor')
    clock=[0]
    monkeypatch.setattr(supervisor.time,'monotonic',lambda:clock[0])
    def host():
        clock[0]=101
    fake=SimpleNamespace(host=host,owned=lambda *args:{'State':{'Running':False,'ExitCode':0,'OOMKilled':False},'RestartCount':0})
    with pytest.raises(TimeoutError):
        supervisor.Supervisor.wait(fake,'owned',100)


def test_cross_arm_signature_preserves_exact_output_and_ignores_new_ids():
    supervisor=module('recording_cpu_quota_supervisor')
    report={'final_bytes':3,'expected_sha256':'same','recording_config':{},'frames':[],
        'placements':[],'timeline_coverage':{},'parts':[3],
        'source':{'analysis_source_ref':'generated-a','duration_sec':120.0,'timeline_range':{'start_sec':0.0,'end_sec':120.0},
                  'profile_ref':'fixed','byte_size':3}}
    signature=supervisor.correctness_signature(report)
    assert signature==supervisor.correctness_signature({**report,'source':{**report['source'],'analysis_source_ref':'generated-b'}})
    assert signature!=supervisor.correctness_signature({**report,'expected_sha256':'different'})
    assert signature!=supervisor.correctness_signature({**report,'source':{**report['source'],'duration_sec':120.00000000000001}})


def test_sampler_selects_actual_leaf_in_host_and_private_namespace(tmp_path):
    runner=module('recording_real_media_recheck')
    leaf=tmp_path/'docker'/'owned'
    leaf.mkdir(parents=True)
    assert runner.current_cgroup_root(tmp_path,'0::/docker/owned')==leaf
    assert runner.current_cgroup_root(tmp_path,'0::/')==tmp_path
    with pytest.raises(ValueError):
        runner.current_cgroup_root(tmp_path,'0::/../escape')


def test_cleanup_error_keeps_original_timeout_cause():
    import subprocess
    supervisor=module('recording_cpu_quota_supervisor')
    original=subprocess.TimeoutExpired(['docker','exec','owned'],8)
    cleanup=RuntimeError('OWNED_CLEANUP_FAILED')
    cleanup.__context__=original
    result=supervisor.error_chain(cleanup)
    assert [r['type'] for r in result]==['RuntimeError','TimeoutExpired']
    assert result[1]['timeout_sec']==8 and result[1]['operation']=='exec'
    assert 'owned' not in str(result)


def test_capture_timeout_has_no_unbounded_pipe_drain(tmp_path):
    import subprocess
    import time
    supervisor=module('recording_cpu_quota_supervisor')
    started=time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        supervisor.bounded_capture([sys.executable,'-c','import time;time.sleep(10)'],.15,tmp_path)
    assert time.monotonic()-started<2
    result=supervisor.bounded_capture([sys.executable,'-c',"print('CONTROL')"],3,tmp_path)
    assert result.returncode==0 and result.stdout.strip()==b'CONTROL'
