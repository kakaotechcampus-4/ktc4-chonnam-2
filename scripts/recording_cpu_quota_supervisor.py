"""Windows 호스트의 유한 Linux CPU 대조 감독기.

예: python scripts/recording_cpu_quota_supervisor.py --experiment-id <새 ID> --mode acceptance
acceptance 성공 후 동일 ID의 --mode measure만 허용한다. 이전 증거를 덮어쓰지 않으며
smoke1회와 A1/B/A2 외의 길이·반복·운영 target은 지원하지 않는다.
"""
import argparse
import ctypes
from datetime import datetime, timezone, timedelta
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from recording_probe_budget import ProbeBudget, MIB


REPO = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f'
MYSQL = 'sha256:b35575a03e5327131916eb8d39222c4c89590881fb44ed69b5814910e5fefa34'
PROTECTED = {'issue452-capacity-db','issue452-chunks-restore-db','issue452-chunks-restore2-db'}
CODE_SHA = '7b2f6b8873cc1cdfc7c333ef0f8023143382ee66'


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value,stream,indent=2)


def error_chain(error):
    result=[]
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        value={'type':type(error).__name__}
        if isinstance(error,subprocess.TimeoutExpired):
            value['timeout_sec']=error.timeout
            value['operation']=error.cmd[1] if isinstance(error.cmd,list) and len(error.cmd)>1 and error.cmd[0]=='docker' else None
        elif re.fullmatch(r'[A-Z][A-Z0-9_]+',str(error)):
            value['code']=str(error)
        result.append(value)
        error=error.__cause__ or error.__context__
    return result


def bounded_capture(argv, timeout, directory):
    """pipe의 무기한 communicate/drain 없이 실행·회수를 각각 유한하게 감독한다."""
    deadline=time.monotonic()+timeout
    limit=8*1024**2
    with tempfile.TemporaryFile(dir=directory) as stdout, tempfile.TemporaryFile(dir=directory) as stderr:
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        try:
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise subprocess.TimeoutExpired(argv,timeout)
                if max(os.fstat(stdout.fileno()).st_size,os.fstat(stderr.fileno()).st_size)>limit:
                    raise RuntimeError('DOCKER_CAPTURE_SIZE_STOP')
                try:
                    code=process.wait(timeout=min(.1,remaining))
                except subprocess.TimeoutExpired:
                    continue
                if time.monotonic()>deadline:
                    raise subprocess.TimeoutExpired(argv,timeout)
                break
            stdout.seek(0)
            stderr.seek(0)
            out,err=stdout.read(limit+1),stderr.read(limit+1)
            if max(len(out),len(err))>limit:
                raise RuntimeError('DOCKER_CAPTURE_SIZE_STOP')
            return subprocess.CompletedProcess(argv,code,out,err)
        finally:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('OWNED_DOCKER_CLIENT_REAP_FAILED') from None


def require_inspect(value, owner, quota, memory_mib, cpuset):
    cfg=value['HostConfig']
    if (value['Config'].get('Labels',{}).get('owner') != owner
            or cfg['NanoCpus'] != int(Fraction(quota)*1000000000)
            or cfg['Memory'] != memory_mib*MIB or cfg['MemorySwap'] != memory_mib*MIB
            or cfg['CpusetCpus'] != cpuset or value['State']['OOMKilled'] or value['RestartCount']):
        raise RuntimeError('OWNERSHIP_OR_ACTUAL_LIMIT_MISMATCH')


def measure_sequence(supervisor):
    for arm in ('smoke','A1','B','A2'):
        try:
            supervisor.stage(arm)
        finally:
            supervisor.cleanup(arm)


def correctness_signature(report):
    """새 DB의 생성 ref만 제외하며 bytes·hash·숫자·선택/coverage 요약은 exact 비교한다."""
    value={key:report[key] for key in ('final_bytes','expected_sha256','recording_config','frames',
        'placements','timeline_coverage','parts')}
    value['source']={key:report['source'][key] for key in ('duration_sec','timeline_range','profile_ref','byte_size')}
    return json.dumps(value,sort_keys=True,separators=(',',':'))


class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong)
        for name in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]


class Supervisor:
    def __init__(self, owner):
        if re.fullmatch(r'cpu-quota-[a-z0-9-]{1,36}',owner) is None:
            raise ValueError('EXPERIMENT_ID_INVALID')
        self.owner=owner
        self.root=REPO/'.codex-scratch'/owner
        self.root.mkdir(exist_ok=True)
        self.budget=ProbeBudget.from_profile('legacy')
        self.created=[]
        self.started=time.monotonic()
        self.stage_name=None
        self.cleanup_deadline=None

    def log(self, name, value):
        with (self.root/name).open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(value)+'\n')

    def docker(self,*args,check=True,timeout=15):
        if self.cleanup_deadline is not None:
            remaining=self.cleanup_deadline-time.monotonic()
            if remaining<=.5:
                raise TimeoutError('CLEANUP_TIMEOUT')
            timeout=min(timeout,remaining-.5)
        started=time.monotonic()
        try:
            result=bounded_capture(['docker',*args],timeout,self.root)
        except BaseException as error:
            self.log('docker-cost.private.jsonl',{'operation':args[0], 'elapsed_sec':time.monotonic()-started,
                'requested_timeout_sec':timeout,'error_type':type(error).__name__,'tag':self.stage_name})
            raise
        self.log('docker-cost.private.jsonl',{'operation':args[0], 'elapsed_sec':time.monotonic()-started,
            'returncode':result.returncode,'tag':self.stage_name})
        if check and result.returncode:
            self.log('docker-error.private.jsonl',{'operation':args[0], 'stderr':result.stderr.decode(errors='replace')})
            raise RuntimeError('DOCKER_'+args[0].upper()+'_FAILED')
        return result

    def inspect(self, kind, name, *, check=True):
        args=[kind,'inspect',name] if kind!='container' else ['inspect',name]
        result=self.docker(*args,check=check)
        if result.returncode==0:
            values=json.loads(result.stdout)
            if len(values)!=1:
                raise RuntimeError('INSPECT_AMBIGUOUS_RESULT')
            return values[0]
        text=result.stderr.decode(errors='replace').strip()
        known=(f'Error: No such object: {name}',f'Error response from daemon: No such container: {name}',
            f'Error response from daemon: get {name}: no such volume',
            f'Error response from daemon: network {name} not found')
        if not check and result.returncode==1 and text.casefold() in {item.casefold() for item in known}:
            return None
        self.log('inspect-error.private.jsonl',{'kind':kind,'name':name,'returncode':result.returncode,'stderr':text})
        raise RuntimeError('INSPECT_FAILED_NOT_CONFIRMED_ABSENT')

    def owned(self,kind,name):
        value=self.inspect(kind,name)
        labels=value['Config'].get('Labels',{}) if kind=='container' else value.get('Labels',{})
        if labels.get('owner') != self.owner:
            raise RuntimeError('EXACT_OWNER_REQUIRED')
        return value

    def create(self,kind,name,args):
        if name in PROTECTED or self.inspect(kind,name,check=False) is not None:
            raise RuntimeError('RESOURCE_NAME_EXISTS')
        # 생성 응답 timeout도 실제 생성 여부를 재확인해 이번 소유 자원만 회수한다.
        self.created.append((kind,name))
        self.log('creation-intents.private.jsonl',{'kind':kind,'name':name,'owner':self.owner})
        self.docker(*args)
        self.owned(kind,name)

    def host(self,*,start=False,db_data=0):
        m=Memory()
        m.length=ctypes.sizeof(m)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            raise RuntimeError('WINDOWS_RAM_QUERY_FAILED')
        value={'kst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
            'host_monotonic_sec':time.monotonic(),'available_ram_bytes':m.available,
            'C_free_bytes':shutil.disk_usage('C:/').free,'tag':self.stage_name}
        initial=self.root/'resource-origin.private.json'
        if not initial.exists():
            write_new(initial,value)
        origin=json.loads(initial.read_text())['C_free_bytes']
        growth=max(0,origin-value['C_free_bytes'])
        self.log('host.private.jsonl',{**value,'disk_growth_bytes':growth})
        if start:
            self.budget.preflight(available_ram=m.available,c_free=value['C_free_bytes'],disk_growth_used=growth,
                db_data=db_data,output_cap=96*MIB,search_candidate=64*MIB)
        elif (m.available < self.budget.host_reserve_mib*MIB or value['C_free_bytes'] < self.budget.disk_reserve_mib*MIB
                or growth >= self.budget.disk_growth_mib*MIB):
            raise RuntimeError('HOST_RESERVE_STOP')
        return value

    def names(self,tag):
        base=self.owner+'-'+tag.lower()
        return {kind:base+'-'+suffix for kind,suffix in [('db','db'),('runner','runner'),('init','init'),
            ('network','net'),('data','data'),('work','work')]}

    def mounts(self):
        result=[]
        for name in ('src','scripts','migrations','docker','tests','data','pyproject.toml','conftest.py'):
            result+=['--mount',f'type=bind,source={REPO/name},target=/repo/{name},readonly']
        return result

    def snapshot_identity(self):
        digest=hashlib.sha256()
        for path in sorted((REPO/'src').rglob('*.py')):
            digest.update(path.relative_to(REPO).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
        manifest=REPO/'.codex-scratch/capacity-input15-20261102/manifest.private.json'
        return {'source_sha256_v1':digest.hexdigest(),
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'config_sha256':hashlib.sha256((self.root/'config.json').read_bytes()).hexdigest(), 'scripts':{
            path:hashlib.sha256((REPO/'scripts'/path).read_bytes()).hexdigest() for path in
            ('recording_cpu_quota_supervisor.py','recording_cpu_quota_linux.py','recording_cpu_quota_probe.py',
             'recording_real_media_recheck.py','recording_probe_budget.py','recording_capacity_probe.py')}}

    def db_metrics(self,name):
        state=self.owned('container',name)
        if not state['State']['Running']:
            raise RuntimeError('DB_NOT_RUNNING')
        require_inspect(state,self.owner,'0.5',512,'')
        script=('p=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup); '
            'cat "$p/memory.current" "$p/memory.peak"; cat "$p/cpu.stat"; '
            'sed "s/^/event_/" "$p/memory.events"; '
            'du -sb /var/lib/mysql /tmp /var/tmp; '
            'sed -n "/^VmRSS:/p" /proc/1/status')
        raw=self.docker('exec',name,'sh','-c',script,timeout=8).stdout.decode().splitlines()
        value={'host_monotonic_sec':time.monotonic(),'memory_current':int(raw[0]),'memory_peak':int(raw[1])}
        for line in raw[2:]:
            parts=line.split()
            if len(parts)==2:
                if parts[0].isdecimal():
                    key={'/var/lib/mysql':'db_data_bytes','/tmp':'tmp_bytes','/var/tmp':'var_tmp_bytes'}[parts[1]]
                    value[key]=int(parts[0])
                else:
                    value[parts[0]]=int(parts[1])
            elif parts and parts[0]=='VmRSS:':
                value['rss_bytes']=int(parts[1])*1024
        self.log(self.stage_name+'-db.private.jsonl',value)
        if (value['memory_current'] >= 440*MIB or value['db_data_bytes'] >= 1024*MIB
                or value.get('event_oom',0) or value.get('event_oom_kill',0)):
            raise RuntimeError('DB_SOFT_OR_OOM_STOP')
        return value

    def wait(self,name,deadline,*,db=None):
        while True:
            if time.monotonic()>deadline:
                raise TimeoutError('FINITE_CONTAINER_TIMEOUT')
            self.host()
            if db:
                self.db_metrics(db)
            state=self.owned('container',name)
            if time.monotonic()>deadline:
                raise TimeoutError('FINITE_CONTAINER_TIMEOUT')
            if not state['State']['Running']:
                if state['State']['ExitCode'] or state['State']['OOMKilled'] or state['RestartCount']:
                    raise RuntimeError('CONTAINER_FAILED')
                return
            if time.monotonic()>deadline:
                raise TimeoutError('FINITE_CONTAINER_TIMEOUT')
            if (self.root/(self.stage_name+'.abort')).exists():
                raise RuntimeError('RUNNER_SOFT_RESOURCE_STOP')
            time.sleep(1)

    def stage(self,tag):
        if tag not in ('acceptance','smoke','A1','B','A2'):
            raise ValueError('STAGE_INVALID')
        self.stage_name=tag
        started=time.monotonic()
        if (self.root/(tag+'-stage.private.json')).exists():
            raise RuntimeError('STAGE_ALREADY_ATTEMPTED')
        write_new(self.root/(tag+'-stage.private.json'),{'status':'STARTED','tag':tag})
        config=self.root/'config.json'
        if not config.exists():
            write_new(config,{'experiment_id':self.owner,'max_output_bytes':96*MIB,'max_duration_ms':240000,
                'run_timeout_sec':900,'resource_profile':'legacy'})
        current=self.snapshot_identity()
        frozen=self.root/'identity.private.json'
        if frozen.exists():
            if json.loads(frozen.read_text())!=current:
                raise RuntimeError('SOURCE_OR_HARNESS_CHANGED')
        else:
            write_new(frozen,current)
            copies=self.root/'execution-source'
            copies.mkdir(exist_ok=False)
            for name,expected in current['scripts'].items():
                data=(REPO/'scripts'/name).read_bytes()
                if hashlib.sha256(data).hexdigest()!=expected:
                    raise RuntimeError('SOURCE_CHANGED_DURING_COPY')
                with (copies/name).open('xb') as stream:
                    stream.write(data)
            for name,path,key in [('manifest.private.json',REPO/'.codex-scratch/capacity-input15-20261102/manifest.private.json','manifest_sha256'),
                    ('config.json',config,'config_sha256')]:
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=current[key]:
                    raise RuntimeError('INPUT_CONFIG_CHANGED_DURING_COPY')
                with (copies/name).open('xb') as stream:
                    stream.write(data)
        self.host(start=True)
        names=self.names(tag)
        # 다른 컨테이너와 운영 작업이 없는 시작 조건만 허용한다.
        if self.docker('ps','-aq').stdout.strip():
            raise RuntimeError('OTHER_CONTAINER_PRESENT')
        self.create('network',names['network'],['network','create','--internal','--label','owner='+self.owner,names['network']])
        for kind in ('data','work'):
            self.create('volume',names[kind],['volume','create','--label','owner='+self.owner,names[kind]])
        self.create('container',names['init'],['create','--name',names['init'],'--label','owner='+self.owner,
            '--network','none','--cpus','.5','--memory','128m','--memory-swap','128m','--pids-limit','32',
            '--read-only','--pull=never','--user','0:0','--mount',f'type=volume,source={names["work"]},target=/work',
            '--entrypoint','python',IMAGE,'-B','-c',"import os;os.chown('/work',10001,10001);os.chmod('/work',0o700)"])
        self.docker('start',names['init'])
        self.wait(names['init'],time.monotonic()+30)
        self.docker('rm',names['init'])
        self.created.remove(('container',names['init']))
        self.create('container',names['db'],['create','--name',names['db'],'--label','owner='+self.owner,
            '--network',names['network'],'--cgroupns','host','--cpus','.5','--memory','512m','--memory-swap','512m',
            '--pids-limit','128','--pull=never','--log-driver','local','--log-opt','max-size=1m','--log-opt','max-file=2',
            '-e','MYSQL_ALLOW_EMPTY_PASSWORD=yes','-e','MYSQL_ROOT_HOST=%',
            '--mount',f'type=volume,source={names["data"]},target=/var/lib/mysql',MYSQL,
            '--max-allowed-packet=67108864','--innodb-buffer-pool-size=33554432','--innodb-redo-log-capacity=16777216',
            '--max-connections=12','--performance-schema=OFF','--skip-log-bin','--general-log=OFF','--slow-query-log=OFF'])
        self.docker('start',names['db'])
        deadline=time.monotonic()+120
        while True:
            if time.monotonic()>deadline:
                raise TimeoutError('DB_READINESS_TIMEOUT')
            self.host()
            self.db_metrics(names['db'])
            ready=self.docker('exec',names['db'],'mysql','--protocol=TCP','-h127.0.0.1','-uroot','-N','-B',
                '-e','SELECT @@session.max_allowed_packet',check=False,timeout=8)
            if time.monotonic()>deadline:
                raise TimeoutError('DB_READINESS_TIMEOUT')
            if ready.returncode==0 and ready.stdout.strip()==b'67108864':
                break
            if time.monotonic()>deadline:
                raise TimeoutError('DB_READINESS_TIMEOUT')
            time.sleep(1)
        self.docker('exec',names['db'],'mysql','--protocol=TCP','-h127.0.0.1','-uroot','-e','CREATE DATABASE probe',timeout=8)
        before=self.db_metrics(names['db'])
        self.host(start=True,db_data=before['db_data_bytes'])
        db=self.owned('container',names['db'])
        ip=db['NetworkSettings']['Networks'][names['network']]['IPAddress']
        cg=self.docker('exec',names['db'],'cat','/proc/self/cgroup',timeout=8).stdout.decode()
        quota='2.0' if tag=='B' else '1.5'
        connection={'tag':tag,'quota':quota,'mode':'acceptance' if tag=='acceptance' else 'measure',
            'db_host':ip,'db_cgroup':cg,'image_id':IMAGE,'code_sha':CODE_SHA}
        write_new(self.root/(tag+'-connection.private.json'),connection)
        manifest=REPO/'.codex-scratch/capacity-input15-20261102/manifest.private.json'
        source=json.loads(manifest.read_text(encoding='utf-8-sig'))['source_folder_private']
        self.create('container',names['runner'],['create','--name',names['runner'],'--label','owner='+self.owner,
            '--network',names['network'],'--cgroupns','host','--cpus',quota,'--cpuset-cpus','0,1',
            '--memory','1280m','--memory-swap','1280m','--pids-limit','128','--read-only','--pull=never','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--log-driver','local','--log-opt','max-size=1m','--log-opt','max-file=2',
            '--tmpfs','/tmp:rw,size=100663296,mode=1777','--workdir','/repo',
            '-e','REAL_MEDIA_RECHECK_ISOLATED=owned-internal-20261103','-e','PYTHONDONTWRITEBYTECODE=1',
            '-e','PYTHONPATH=/repo/src:/repo/scripts','-e','TMPDIR=/work',*self.mounts(),
            '--mount',f'type=bind,source={source},target=/inputs,readonly',
            '--mount',f'type=bind,source={manifest.parent},target=/fixture,readonly',
            '--mount',f'type=bind,source={self.root},target=/evidence',
            '--mount',f'type=bind,source={REPO/".venv/Lib/site-packages"},target=/host-packages,readonly',
            '--mount',f'type=volume,source={names["work"]},target=/work',
            '--entrypoint','python',IMAGE,'-B','/repo/scripts/recording_cpu_quota_linux.py',
            '--connection','/evidence/'+tag+'-connection.private.json'])
        inspect=self.owned('container',names['runner'])
        require_inspect(inspect,self.owner,quota,1280,'0,1')
        if inspect['HostConfig']['CgroupnsMode']!='host' or not inspect['HostConfig']['ReadonlyRootfs']:
            raise RuntimeError('LINUX_NAMESPACE_OR_READONLY_REQUIRED')
        if any(m['RW'] for m in inspect['Mounts'] if m['Destination'] in ('/inputs','/fixture','/repo/src','/repo/scripts')):
            raise RuntimeError('INPUT_OR_CODE_MOUNT_WRITABLE')
        write_new(self.root/(tag+'-actual-settings.private.json'),{'runner_host_config':{
            k:inspect['HostConfig'][k] for k in ('NanoCpus','CpusetCpus','Memory','MemorySwap','CgroupnsMode','ReadonlyRootfs')},
            'db_host_config':{k:db['HostConfig'][k] for k in ('NanoCpus','CpusetCpus','Memory','MemorySwap','CgroupnsMode')},
            'initial_db_metrics':before,'stage_started_host_monotonic':started})
        self.docker('start',names['runner'])
        stage_deadline=started+(300 if tag=='acceptance' else 1080)
        self.wait(names['runner'],min(stage_deadline,time.monotonic()+(120 if tag=='acceptance' else 930)),db=names['db'])
        cpu=json.loads((self.root/(tag+'-cpu.private.json')).read_text())
        if cpu['status'] not in ('PASS_LINUX_ACCEPTANCE','PASS_RECORDING_ONLY') or not cpu.get('hooks_restored'):
            raise RuntimeError('LINUX_OBSERVER_ACCEPTANCE_FAILED')
        if tag!='acceptance':
            report=json.loads((self.root/(tag+'.json')).read_text())
            if (report['status']!='PASS_RECORDING_ONLY' or report['cleanup_errors'] or report['sampler_error']
                    or report['temp_after']['including_open_unlinked_bytes'] or report['live_children_after']
                    or report['aborted_before']!=report['aborted_after'] or report['provider_calls']):
                raise RuntimeError('RECORDING_CORRECTNESS_OR_CLEANUP_FAILED')
            if tag in ('B','A2'):
                a1=json.loads((self.root/'A1.json').read_text())
                if correctness_signature(report)!=correctness_signature(a1):
                    raise RuntimeError('CROSS_ARM_OUTPUT_DIFFERENCE_STOP')
        if self.snapshot_identity()!=json.loads(frozen.read_text()):
            raise RuntimeError('SOURCE_OR_HARNESS_CHANGED_DURING_STAGE')
        self.db_metrics(names['db'])
        self.log('progress.private.jsonl',{'tag':tag,'status':'PASS','elapsed_host_sec':time.monotonic()-started})
        print(json.dumps({'tag':tag,'status':cpu['status'],'phase_count':len(cpu['events'])}),flush=True)

    def cleanup(self,tag):
        started=time.monotonic()
        self.cleanup_deadline=started+60
        errors=[]
        expected=self.names(tag)
        allowed={expected[k] for k in ('db','runner','init')}
        resources=list(self.created)
        for kind,name in reversed(resources):
            try:
                if time.monotonic()-started>60:
                    raise TimeoutError('CLEANUP_TIMEOUT')
                info=self.inspect(kind,name,check=False)
                if info is None:
                    self.created.remove((kind,name))
                    continue
                self.owned(kind,name)
                if kind=='container':
                    if name not in allowed:
                        raise RuntimeError('CLEANUP_NAME_NOT_ALLOWED')
                    if info['State']['Running']:
                        self.docker('stop','--time','5',name,timeout=12)
                    current=self.owned(kind,name)
                    if current['State']['Running']:
                        raise RuntimeError('CONTAINER_STILL_RUNNING')
                    logs=self.docker('logs',name)
                    (self.root/(tag+'-'+('db' if name==expected['db'] else 'runner')+'-logs.private.txt')).write_bytes(logs.stdout+logs.stderr)
                    self.log('final-state.private.jsonl',{'name':name,'state':{k:current['State'].get(k) for k in
                        ('Running','ExitCode','OOMKilled','StartedAt','FinishedAt')},'restart_count':current['RestartCount']})
                    self.docker('rm',name)
                elif kind=='volume':
                    if name not in {expected['data'],expected['work']} or name in PROTECTED:
                        raise RuntimeError('PROTECTED_OR_UNKNOWN_VOLUME')
                    if self.docker('ps','-aq','--filter','volume='+name).stdout.strip():
                        raise RuntimeError('VOLUME_IN_USE')
                    self.owned(kind,name)
                    self.docker('volume','rm',name)
                else:
                    if name!=expected['network'] or self.owned(kind,name).get('Containers'):
                        raise RuntimeError('NETWORK_IN_USE')
                    self.docker('network','rm',name)
                if self.inspect(kind,name,check=False) is not None:
                    raise RuntimeError('RESOURCE_STILL_EXISTS')
                self.created.remove((kind,name))
            except BaseException as error:
                errors.append({'kind':kind,'name':name,'error_type':type(error).__name__})
        self.log('cleanup.private.jsonl',{'tag':tag,'elapsed_sec':time.monotonic()-started,'errors':errors,'remaining':self.created})
        self.cleanup_deadline=None
        if errors or self.created:
            raise RuntimeError('OWNED_CLEANUP_FAILED')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id',required=True)
    parser.add_argument('--mode',choices=('acceptance','measure'),required=True)
    args=parser.parse_args()
    supervisor=Supervisor(args.experiment_id)
    marker=supervisor.root/(args.mode+'-result.private.json')
    if marker.exists():
        raise RuntimeError('ATTEMPT_CLOSED_NEW_ID_REQUIRED')
    result={'status':'FAIL','mode':args.mode}
    try:
        if args.mode=='acceptance':
            try:
                supervisor.stage('acceptance')
            finally:
                supervisor.cleanup('acceptance')
        else:
            acceptance=json.loads((supervisor.root/'acceptance-result.private.json').read_text())
            if acceptance['status']!='PASS':
                raise RuntimeError('ACCEPTANCE_REQUIRED')
            measure_sequence(supervisor)
        result['status']='PASS'
    except BaseException as error:
        result.update(error_type=type(error).__name__,error_code=str(error) if isinstance(error,(RuntimeError,ValueError,TimeoutError)) else None)
        result['error_chain']=error_chain(error)
    finally:
        write_new(marker,result)
    print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
