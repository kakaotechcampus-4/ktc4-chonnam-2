# EC2 Recording 격리 측정 준비·운영 절차

**IN_PROGRESS · Refs #452 · Related #530, #553, #555 · RT-14 후속.** 정철원(Runtime 구현·Recording Owner).
이 문서는 로컬에서 준비한 실행물과 **향후 운영자가 별도 점검 승인 후 실행할 명령**이다. 이번 작성 세션에서 EC2 접속·전송·AWS/SSM·운영 중단·서버 측정은 하지 않았다.
[준비 검증 기록](2026-11-03-ec2-recording-probe-validation.md), [기존 결과 §9·§10](2026-11-03-recording-cpu-quota-probe.md), [시간 분석](2026-11-03-recording-preparation-timing.md)을 함께 읽는다. 기존 원문은 보존한다.

## 1. 범위와 선행 결정

순서는 **무미디어 acceptance → input-02 0~10초 smoke 1회 → input-01~02 명시 placement의 0~120초 대표 요청 1회**다. 각 단계는 별도 호출이고 자동 반복하지 않는다. A1/B/A2·20분·Search/provider·Case/Web/Package E2E는 실행하지 않는다. strict 검사·제품 src·Case timeout·운영 설정을 바꾸지 않는다.

| 실행 전 필요한 결정 | 확인 주체·거부 조건 |
| --- | --- |
| 기존 registry의 runner/MySQL immutable digest, amd64, EC2에 이미 있는 image | 운영자. 로컬 image ID를 registry digest로 쓰지 않음. 원격 pull/publish/ECR 조작은 이 도구에 없음. 필요한 image가 없으면 별도 준비 결정 전 중단 |
| 실제 운영 tuple·policy reserve·DockerRootDir·CPU 조건·CPU credit 관측 | Runtime/Ops. 값이 없거나 source revision과 image 의존성 호환이 불명확하면 중단 |
| 점검 창·외부 ingress 통제·직접 DB writer/예약 작업·배포/configure/backup 중지·복귀 담당 | 팀. 수단/권한/담당자가 정해지지 않으면 중단. 이 패키지는 Caddy config·SG·정책을 수정하지 않음 |
| API·Worker·MySQL 잠시 중단 후 예산 충족 여부 | 운영자. 아래 산식과 **중단 후 실제 관측** 모두 통과해야 함. 미달이면 서비스 복귀 후 연기 |
| 전송 채널·보호 경로·보존 기간 | 운영자. 기존 승인된 SSH/SFTP 등만 사용. 포트/키/권한을 새로 열어 우회하지 않음 |

RT-14 운영 규칙은 [배포 §4](../rt14-deployment.md#4-보호된-host-준비와-config), [호환·상태 복구](../rt14-public-deployment.md), [복구 acceptance §3·§4·§7](../rt14-recovery-acceptance.md), [capacity G1~G6·안전 경계](elice-runtime-capacity-smoke-plan.md#9-공통-선행조건안전중단)에서 확인한다. 이 절차는 deploy controller의 preflight를 읽기 전용 명령으로 호출하지 않는다.

## 2. 자원 예산과 중단 제안

운영자 보고는 CPU2·RAM3.7GiB·available 약1.6GiB·swap0·여유 disk 약38GiB이며, Worker647.7MiB/API106MiB/MySQL787.4MiB다. 이번 작성자의 직접 조회가 아니다. 순간 사용량이며 reclaimable memory·잔존 page cache·Caddy·호스트 사용량·CPU credit을 보증하지 않는다.

| 항목 | 실행물의 유한 한도·산식 |
| --- | --- |
| runner | 1280MiB hard, 1100MiB soft, swap 추가0, PID128, read-only root, uid10001 |
| 별도 MySQL | 512MiB hard, 440MiB soft, swap 추가0, PID128, CPU0.5core, packet64MiB·buffer pool32MiB·연결12 |
| collector/감독 예비 | 512MiB. 기존 보수 예산 유지. 실제 peak 측정값이 아님 |
| 호스트·Caddy·운영 프로세스 잔존 reserve | `R=max(실제 policy.memory_reserve_bytes, 700MiB)`; policy의 양의 정수 확인 필수 |
| 시작 MemAvailable | `1280+512+512+R = 2304MiB+R`. R=700MiB일 때만 3004MiB. 이 R을 운영값으로 확정한 것이 아님 |
| 출력·duration | 실험 전용96MiB·240000ms. 실제 요청은10초/120초만 허용 |
| temp·DBdata | temp512MiB soft. 초기 실제 DBdata +288MiB <1GiB. runner 임시/tmpfs도 hard memory scope에 포함 |
| disk | `D=max(실제 policy.disk_reserve_bytes,4GiB)`. 시작 free≥D+2GiB, 전체 증가<2GiB. source/evidence/실제 DockerRootDir의 최소 free 사용 |
| disk 후보 상세 | N=96MiB의 기존 보수 식: temp256MiB, runner624MiB, DB증가288MiB, disk증가608MiB. 원본2개242,553,742B·패키지·로그·실패 증거·기존 image/cache·운영 잔존 증가도 시작 free에서 이미 차감 |
| 시간 | DB readiness120초, 무미디어 runner180초, 실영상 runner alarm900초·host wait930초, 도구120초, cleanup 별도60초. 개별 Docker 호출도 유한 감독 |

**[추정]** 세 서비스 보고 사용량 합은1541.1MiB다. 1.6GiB를 단순히1638.4MiB로 바꿔 더하면3179.5MiB지만 RSS/usage의 반환량과 MemAvailable은 동일하지 않다. Worker만 중단(추정2286.1MiB), Worker+MySQL(추정3073.5MiB)은 실제 policy와 오차를 고려한 확정 통과 근거가 아니다. **API·Worker·MySQL 모두 중단하는 점검 창을 제안**하며 Caddy·mount·Docker는 유지한다. 그 뒤에도 `resource_gate`가 부족하면 거부한다. reserve 축소·swap·resize·cache flush·Docker/WSL 재시작·prune로 통과시키지 않는다. 운영 서비스 복귀는 실험을 중단하고 실험 runner/DB 정지를 입증한 뒤 우선한다.

CPU quota는 로컬 대조의1.5/2.0을 복제하지 않는다. 운영 Worker의 `NanoCpus/CpuQuota/CpuPeriod/CpusetCpus`, 실제 leaf·상위 `cpu.max/cpu.stat/cpuset.cpus.effective`, affinity·온라인 CPU를 읽고 비교 가능한 **단일 조건**을 Runtime이 정한다. 무제한이면2개의 온라인 CPU에 맞는 유한2core 후보를 검토할 수 있으나 상위 cgroup/cpuset가 더 작으면 거부한다. DB0.5core는 같은2core와 경합할 수 있다. leaf별 user/system/usage·periods/throttling, host load·`/proc/stat`·PSI를 함께 기록한다. CloudWatch는 해당 instance의 유형·credit mode·측정 전후 CPUUtilization/CPUCreditBalance/CPUCreditUsage와 해당하는 surplus 지표·시간 범위/해상도/누락을 운영자가 읽기 전용으로 보존한다. credit UNKNOWN이면 CPU 성능 해석은 제한하고 대표 측정 진행 여부를 먼저 결정한다.

상위 memory.max/high/swap.max·memory.current/events와 scope identity를 별도로 보존한다. **이번 adapter는 유한 상위 memory.max/high를 지원하지 않으며 여유가 커 보여도 거부**한다. 공유 상위 scope의 headroom을 추정해 통과시키지 않는다. DB 시작 전128MiB init 컨테이너에서 상위 scope를 검사하고 DB startup/실행 poll에서 다시 검사하며 runner phase 경계에서도 대조한다. leaf memory.max/swap.max의 변경도 실패다. hierarchy root에서 제공되지 않는 필드는 null로 남기며 호스트 reserve가 별도로 적용된다. EC2 Docker endpoint는 해당 호스트의 로컬 socket·daemon 이름과 일치해야 한다.

## 3. 로컬 PowerShell — identity·패키지·최소 입력 계획

각 블록을 검토 후 하나씩 실행한다. 변수는 비공개 운영 기록에서 정하며 예시값/가짜 digest로 채우지 않는다. stdout에는 secret·원본명/경로를 출력하지 않는다.

```powershell
Set-Location C:\ktc4-chonnam-2
git status --short --branch
git rev-parse HEAD
git diff --cached --stat
git merge-base --is-ancestor 23c0098499772dfa6aaa65311cf7d2da9e4dc050 HEAD
```

기대: 지정 branch·검토한 HEAD·빈 index·#555 ancestry exit0. 사용자 변경이 있으면 보존하고 차이를 검토한다. branch 이동/merge/rebase/commit/push는 하지 않는다.

`$ProbeConfig`는 보호 JSON 파일이다. 아래 key를 실제 확인값으로 작성한다. **미확정 값이 있으면 build 이후에도 EC2 실행 금지**다.

| config key | 값의 근거 |
| --- | --- |
| `runner_image`, `mysql_image` | 기존 registry의 `repository@sha256:…`. EC2 실제 image inspect RepoDigests와 대조 |
| `runtime_identity` | 선택 image에서 `recording_ec2_entry.inventory()`와 동일한 Python 버전·전체 배포판 name/version·ffmpeg/ffprobe binary hash. 격리 `--network none`·자원 제한·새 소유 컨테이너에서 수집, 원문은 보호 파일 |
| `runner_quota`, `db_quota`, `cpus` | 운영 비교 근거를 갖춘 단일 quota, DB는`.5`, 명시 CPU 목록. local A/B 값이 근거가 아님 |
| `docker_root` | EC2 `docker info --format '{{.DockerRootDir}}'`의 실제 경로 |
| `local_validation_only` | EC2용은`false`. 로컬 검증 패키지의`true`를 수정해 재사용하지 말고 새 패키지 생성 |
| `operational_identity` | `current:{revision,config_id}`, `previous:{revision,config_id}`, `schema_revision`. EC2 최신 읽기 전용 결과와 보호 대조 |
| `input_identity` | 승인한 최소 `manifest.private.json`·`placements.private.json` 각각의 SHA-256을 파일명 key로 결속. 단계별 다른 manifest로 교체할 수 없음 |

e50b2976→준비 HEAD의 `pyproject.toml/uv.lock` diff는 없고 Dockerfile 차이는 Web build 인자다. 따라서 source mount 방식은 후보로 타당하지만 **의존성 호환을 단정하지 않는다**. source archive의 Recording import, migration graph, Search 미디어 경계의 import·도구 hash와 실제 isolated DB acceptance가 먼저다. 새 image가 필요하면 작업을 멈추고 별도 image 준비/publish 결정을 받는다. 이번 도구는 image build/publish/ECR을 수행하지 않는다.

```powershell
python scripts/recording_ec2_package.py inputs --manifest $ProtectedManifest --output $InputPlanDir
# 두 최소 fixture의 SHA-256을 ProbeConfig.input_identity에 먼저 기록한다.
python scripts/recording_ec2_package.py build --repo . --config $ProbeConfig --output $PackageDir
Get-Content -LiteralPath "$PackageDir/manifest.sha256"
```

기대:`PASS_PACKAGE` 두 번. source.tar에는 명시 allowlist의 HEAD 제품 source/migrations·lock·공개 최소 파일 및 실행 하네스만 있다. `.git`, 전체 workspace, `.env`, credential, scratch, data/원본, 내부 문서는 포함하지 않는다. 모든 파일 hash와 archive hash·입력 fixture hash를 manifest에 결속한다. 제품/의존성 파일의 미커밋 차이는 거부하며 **하네스는 content SHA-256 precommit identity**다. manifest hash를 별도 승인 채널에 기록한다. checksum은 발신자 인증을 대신하지 않는다.

`inputs`는 기존 보호 manifest만 읽어 두 개의 최소 fixture와 전송 계획을 만든다. 원본 파일의 내용 읽기/복사/전송은 하지 않는다. `transfer-plan.private.json`은 원본 경로가 들어 있으므로 공개하지 않고 fixture 디렉터리에 넣지 않는다. 선택은 input-01/02, VIDEO index0, 대표 placement `[0,117.933333]`, `[117.933333,206.5]`에서 요청0~120초, smoke는 input-02의0~10초다. 이는 명시 logical placement이며 촬영 연속성을 입증하지 않는다.

최종 commit은 이번 세션에서 하지 않는다. 향후 별도 승인으로 commit한 뒤 `git status`·HEAD·ancestry를 다시 확인하고 build를 새 디렉터리에서 재수행한다. 새 HEAD와 하네스 blob/content hash·manifest/archive/image/config/tool 조합을 다시 검토하며, precommit 패키지에 commit SHA만 덮어쓰지 않는다. 변경 조합이면 무미디어 acceptance부터 새 owner로 시작한다.

## 4. EC2 — 읽기 전용 사전 확인

**아래부터 이번 세션 NOT_RUN.** 기존 접속 채널에서 root 권한이 필요한 명령만 명시적으로 사용한다. `env`, `docker inspect` 전체, `cat runtime.env`, secret/원본 경로는 공개 출력하지 않는다. 원문은 root0700 보호 기록에만 남긴다.

```sh
uname -m
uname -r
getconf _NPROCESSORS_ONLN
free -b
df -B1 /opt/daesingo
sudo docker info --format '{{.Name}} {{.DockerRootDir}}'
sudo systemctl is-active docker caddy srv-daesingo.mount
sudo test ! -e /opt/daesingo/dirty.json
sudo test ! -e /opt/daesingo/operation.lock
```

기대: amd64 호환·실제 CPU/메모리/swap/disk·서비스 active, dirty/lock 부재 exit0. 하나라도 다르거나 배포/backup/writer 작업이 있으면 다음 단계 금지. lock은 비어 있어도 다른 작업이 시작될 수 있으므로 §6에서 atomic 획득을 다시 한다.

실제 policy reserve만 비민감 출력으로 읽는 명령이다. 전체 policy나 runtime.env를 출력하지 않는다.

```sh
sudo python3 - <<'PY'
import json
from pathlib import Path
p=json.loads(Path('/opt/daesingo/policy.json').read_text())
keys=('memory_reserve_bytes','disk_reserve_bytes')
assert all(type(p[k]) is int and p[k]>0 for k in keys)
print(json.dumps({k:p[k] for k in keys}))
PY
```

기대: 양의 정수 두 값. 누락/null/권한 오류면 예시값을 채우지 말고 중단한다. 실제 식별한 Worker ID에 대한 자원 조회는 `sudo docker inspect --format '{{.HostConfig.NanoCpus}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}} {{.HostConfig.CpusetCpus}} {{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}' "$WORKER_ID"`처럼 필요한 필드만 출력한다. ID는 운영자가 실제 label과 대조해 비공개로 설정한다.

운영자가 `/opt/daesingo/policy.json`을 **읽기만** 하여 `memory_reserve_bytes/disk_reserve_bytes` 양의 정수, project·volume·MySQL digest를 보호 기록에 대조한다. 공개 요약은 reserve 숫자·identity 일치/불일치만 낸다. actual DockerRootDir와 source/evidence filesystem free도 각각 조사한다. 운영자 보고 e50b2976/current config/previous config/schema는 새 조회와 대조할 후보이며 불일치 시 수정하지 말고 중단한다. API/MySQL health, Worker 실제 status/8종·image ID/OCI revision·runtime revision, 운영 DB/media volume label·mount·network, 다른 project 사용 여부와 container 자원 한도를 확인한다.

추가로 필요한 최소 정보는 policy reserve 두 값, 현재 exact tuple·schema/pointer·dirty/lock, 운영 및 후보 image digest/플랫폼/도구·의존성, 실제 CPU/cgroup/cpuset/credit, 모든 writer/job/배포/backup의 통제 방법·복귀 담당이다. 운영 DB의 reader/schema 조회는 호환 기록용 읽기 전용이며 **운영 DB migration을 이 실험 선행조건으로 요구하지 않는다**.

## 5. 로컬 PowerShell / EC2 — 보호 전송·검증

이 단계는 사용자 검토 후 별도 수행한다. 패키지3파일(source.tar/manifest.json/manifest.sha256)과 검토한 bootstrap `recording_ec2_package.py`만 기존 승인 전송 alias와 root0700 수신함에 보낸다. `$TransferAlias`·`$RemoteInbox`는 운영자가 비공개로 정한 값이다. 승인 채널의 manifest hash와 수신 hash를 별도로 대조한다. 전송 오류 원문은 보호 파일로만 리다이렉트한다.

```powershell
scp -q -- "$PackageDir/source.tar" "$PackageDir/manifest.json" "$PackageDir/manifest.sha256" scripts/recording_ec2_package.py "${TransferAlias}:$RemoteInbox/" 2> $PrivateTransferError
if ($LASTEXITCODE -ne 0) { throw '보호 패키지 전송 실패' }
```

원본은 공개 archive/Git/Actions artifact에 넣지 않는다. 보호 전송 계획의 **두 파일만** 별도 승인 채널로 `input-01.mp4`, `input-02.mp4`라는 목적지 이름에 전송한다. `scp -q -p` 등의 읽기 전용 source 전송을 쓰며 출력·오류를 보호한다. 원본15개 폴더 전체 전송/압축은 금지한다. 전송 전후 원본 size/mtime를 기존 manifest와 확인한다. remote mtime 정밀도가 손실되면 **복사본만** 검증된 manifest의 `mtime_ns`로 `os.utime(ns=…)` 후 재검사한다. hash/size 불일치는 mtime 보정으로 통과시키지 않는다.

이후 EC2의 유지 root shell에서 새 owner와 보호 홈을 준비한다. 이미 있는 경로를 인수하지 않는다.

```sh
sudo -i
set -eu
umask 077
OWNER="rec-ec2-$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
PROBE_HOME="/var/lib/recording-probe/$OWNER"
export OWNER PROBE_HOME
test ! -e "$PROBE_HOME"
install -d -m 700 "$PROBE_HOME"
```

승인 패키지를 `$PROBE_HOME/package`에 둔다. 수신한 공개 `recording_ec2_package.py`는 새 `$PROBE_HOME/bootstrap` 디렉터리에 root0400으로 둔다. 두 디렉터리는 `install -d -m 700`으로 준비하며 수신 파일이 없으면 중단한다. 검토한 bootstrap 스크립트의 SHA-256도 발신자와 대조한 후 아래를 실행한다. bootstrap은 전달받은 하네스와 byte가 같은 공개 `recording_ec2_package.py`다. digest는 승인 채널에서 받은 값을 사용한다.

```sh
export PROBE_MANIFEST_SHA256  # 운영자가 검토한 hash를 비공개 입력으로 설정
python3 "$PROBE_HOME/bootstrap/recording_ec2_package.py" unpack \
  --package "$PROBE_HOME/package" --destination "$PROBE_HOME/source" \
  --manifest-sha256 "$PROBE_MANIFEST_SHA256"
export PYTHONPATH="$PROBE_HOME/source/scripts"
```

기대:`PASS_PACKAGE`. source root/하위 디렉터리0555·파일0444, 홈은root0700. 별도의 `fixture`에는 최소 `manifest.private.json/placements.private.json`만, `inputs`에는 위 두 파일만 둔다. 두 디렉터리는uid10001:10001·0500, 파일은0400으로 준비한다. 원본 경로가 있는 transfer plan은 넣지 않는다. 보호된 두 manifest의 hash도 발신자와 대조해 기록한다. `recording_ec2_host.input_gate()`로 두 파일 hash/size/mtime/VIDEO index를 확인하고 명시 placement를 눈으로 대조한다. alias나 순서가 다르면 다음 단계 금지. 실험 중 두 디렉터리는 readonly bind다.

## 6. EC2 — 점검 창·lock·보호 snapshot

팀의 점검 승인, ingress/writer/job/배포/backup 통제 방법·복귀 담당을 정한 뒤 진행한다. 세션이 끊겨도 lock을 지우는 자동 trap은 만들지 않는다. 기존 controller/SSM/backup client가 끝났고 dirty가 없는지 확인한다. 서비스 중단 전 atomic lock을 획득한다.

```sh
test ! -e /opt/daesingo/dirty.json
mkdir -m 700 /opt/daesingo/operation.lock
python3 - <<'PY'
import json, os
from pathlib import Path
from recording_cpu_quota_supervisor import write_new
write_new(Path('/opt/daesingo/operation.lock/recording-probe-owner.private.json'),
          {'owner':os.environ['OWNER'],'evidence':os.environ['PROBE_HOME']+'/evidence'})
print('PASS_OWNED_MAINTENANCE_LOCK')
PY
```

mkdir 실패 시 진행하지 않는다. 기존 lock 강탈·dirty 삭제·deploy/configure 호출을 하지 않는다.

```sh
python3 - <<'PY'
import os
from pathlib import Path
from recording_ec2_host import operational_snapshot
from recording_cpu_quota_supervisor import bounded_capture, write_new
home=Path(os.environ['PROBE_HOME']); run=home/'evidence'; run.mkdir(mode=0o700)
def capture(*a): return bounded_capture(['docker',*a],15,run)
policy,snapshot=operational_snapshot('/opt/daesingo',capture)
write_new(run/'operational-snapshot.private.json',snapshot)
print('PASS_PROTECTED_OPERATIONAL_SNAPSHOT')
PY
```

snapshot에는 파일 hash·pointer·원래 서비스 실행 여부·exact container/image·mount/network/자원 설정을 보존한다. config/credential 원문은 복제하지 않는다. snapshot identity와 패키지 config의 `operational_identity`가 exact 같아야 한다. current/previous/schema/approval/policy·운영 config·volume을 변경하지 않는다.

## 7. EC2 — API 차단·job drain·필요 서비스 중단·자원 gate

외부 ingress와 직접 writer/예약 작업을 통제한다. Caddy는 그대로 active이며 운영 설정은 편집하지 않는다. 먼저 snapshot의 API가 원래 실행 중이었다면 **해당 exact ID만** 유한 stop한다. 모든 stop/start 명령 전에 현재 inspect의 ID/image·project/service·mount가 snapshot과 일치하는지 확인한다. `docker compose up`, recreate, migrate, restart는 사용하지 않는다.

다음 블록의 `SERVICE`만 순서대로 `api`, drain 확인 뒤 `worker`, 마지막 `mysql`로 지정해 **각각 별도 실행**한다. API stop 실패 때 Worker/MySQL로 넘어가지 않는다.

```sh
export SERVICE=api
python3 - <<'PY'
import json,os
from pathlib import Path
from recording_cpu_quota_supervisor import bounded_capture
r=Path(os.environ['PROBE_HOME'])/'evidence'
s=json.loads((r/'operational-snapshot.private.json').read_text())['services'][os.environ['SERVICE']]
v=json.loads(bounded_capture(['docker','inspect',s['id']],15,r).stdout)[0]
assert v['Id']==s['id'] and v['Image']==s['image'] and v['Mounts']==s['mounts']
if s['running']:
    p=bounded_capture(['docker','stop','--time','30',s['id']],45,r)
    assert p.returncode==0
print('PASS_EXACT_SERVICE_STOP')
PY
```

API 중단 후 DB 담당자가 기존 보호된 MySQL client 설정으로 아래 **SELECT만** 수행한다. password argv/env export·runtime.env 복사를 하지 않는다. 실제 운영 schema명과 client defaults 경로는 담당자가 기존 값으로 지정하며 공개 출력하지 않는다.

```sql
SELECT COALESCE(SUM(status='QUEUED'),0),
       COALESCE(SUM(status='RUNNING'),0),
       COALESCE(SUM(status IN ('SUCCEEDED','FAILED') AND case_applied_at IS NULL),0)
FROM job_execution;
```

기대: 미래 `available_at`도 포함해 세 값0. 외부 session/writer·DDL·예약 event·backup·배포가 없음을 DB/팀 담당자가 확인한다. 0이 안 되면 강제 취소·재시도·timeout 변경 없이 실험을 연기하고 §10으로 복귀한다. **drain에 확정 시간 상한은 없다**. Worker는 이 확인을 통과한 뒤 stop하고 MySQL을 마지막에 stop한다.

`maintenance-approved.private.json`은 이 시점의 담당자 확인을 root0400으로 기록한다. fields는 `owner`, 보호 snapshot bytes의 `snapshot_sha256`, 실제 `recovery_owner`, 승인 종료 UTC epoch 정수`not_after_unix`, 그리고 `ingress_controlled/writers_paused/jobs_zero/deployments_paused/backups_paused` 모두`true`다. 값 미확인·만료면 감독기가 거부한다. 파일 작성이 실제 통제를 대신하지 않는다.

서비스 중단 후 `MemAvailable`, source/evidence/실제 DockerRootDir의 free를 다시 읽고 `resource_gate(policy, available, free,0,0)`를 호출한다. 예산 미달·identity 차이·새 운영 작업·CPU/credit 조건 불명은 다음 단계 금지다. 운영을 복귀하고 별도 호스트/점검 방안을 다시 정한다. 남아 있는 Caddy·host·Docker·cache 사용량은 reserve 밖으로 빼지 않는다.

## 8. EC2 — 무미디어 →10초→120초, 각 단계 별도 실행

```sh
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage acceptance
```

기대:`{"status":"PASS","stage":"acceptance","cleanup":true}`와 보호 CPU report의`PASS_LINUX_ACCEPTANCE`. 실제 uid10001·source import·의존성 inventory·도구 hash·read-only cgroup·runner/DB 서로 다른 leaf·상위 quota/cpuset·actual memory/swap·새 빈 DB의`recording_0002`·합성 청크/metadata/rollback·익명 temp sampler를 확인한다. 합성 bytes는 컨테이너 signature 검사용이며 실제 영상 decode 성공으로 표현하지 않는다.

새 stage 자원은 항상 새 DB/network/data/work volume이다. 비밀번호는 매 stage 새 난수이며 readonly 보호 파일로만 전달한다. 운영 connection/env를 사용하지 않는다. 외부 port·운영 network/volume·docker.sock·provider가 runner에 없다.

```sh
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage smoke \
  --fixture "$PROBE_HOME/fixture" --inputs "$PROBE_HOME/inputs"
```

기대:10초`PASS_RECORDING_ONLY`, cleanup true. acceptance 성공·정리·고정 identity가 없으면 거부한다. smoke 실패 시 같은 ID 재시도·대표 요청 금지. 실패 증거 보존→복귀→원인 수정/재검토 후 새 owner의 acceptance부터 시작한다.

```sh
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage representative \
  --fixture "$PROBE_HOME/fixture" --inputs "$PROBE_HOME/inputs"
```

기대:120초`PASS_RECORDING_ONLY`·cleanup true. 한 번만 호출한다. 운영 파일/hash/pointer·exact stopped service·lock/승인 만료·RAM/disk를 poll마다 대조하고 변화 시 중단한다. 승인된 fixture hash·두 입력 hash/size/mtime는 각 실영상 단계 전후 대조한다. runner/DB leaf·상위 scope가 바뀌거나 counter reset·OOM·soft limit·temp cap이면 실패다. 관측은 poll/phase 경계의 표본이며 그 사이의 짧은 변화까지 보장하지 않는다. OS/daemon 정지·kernel I/O hang에서 절대 wall 상한을 보증하지 않는다. CLI timeout만으로 서버 process가 종료됐다고 단정하지 않는다.

## 9. EC2 — 결과 판정과 보호 반출

| 확인 | 통과 조건·해석 |
| --- | --- |
| 정확성 | strict decode·frame coverage/PTS/duration·provenance·VIDEO index·명시 placements·저장 commit/rollback·새 물리 연결 detached hash/length/metadata exact PASS |
| phase | `recording_prepare`와 source/output/packet probe·encode·remux·concat·strict decode·publish·commit/fresh read 분리. parent/child phase 중복 합산 금지 |
| 자원·정리 | OOMKilled false/restart0·memory events0·actual quota/swap·RAM/disk reserve·DBdata/temp·자식0·Aborted_clients 불변·오류0 |
| 통신 | Recording-only 결과, provider0·실제 외부 socket/HTTP 시도0. negative controls의 차단 시도는 실제 송신과 구분 |
| 한계 | sampled RSS/temp는 순간 peak 보장 아님. CPU 누적/throttled를 절약 가능한 wall로 환산하지 않음. host/runner 서로 다른 monotonic clock을 빼지 않음 |

argv·manifest·원본 ref/경로·DB 로그·driver raw·credential은 보호 증거다. 공개 결과는 익명 입력 ID·상태·시간/bytes·수치와 불확실성만 수동 검토 후 추출한다. evidence 폴더 전체를 Git/Actions/외부 게시에 넣지 않는다. 로컬 기존120초 결과의 bytes/hash/3281frame과 다른 도구/플랫폼 출력은 자동 동일성 요구로 바꾸지 말고 이유를 조사한다. strict 요구를 완화하지 않는다.

## 10. EC2 — 전용 정리·기존 서비스 복귀·실패 복구

각 stage는 성공/실패 모두 정확한 owner/name과 실제 미사용을 확인한 **새 자원만**60초 정리를 시도한다. 기존 보호 volume3개·원본15개·공유 image/cache는 보존한다. credential·로그·실패 source 패키지는 보호 증거로 보존하며 보존 기간 이후 별도 소유권 확인 정리 대상으로 기록한다. prune/down -v/광역 rm/daemon 재시작은 금지한다.

| 실패 지점 | 다음 단계·복구 |
| --- | --- |
| package/hash/import/digest/운영 identity/lock | 부하 시작 금지. 설정이나 상태를 고쳐 맞추지 말고 차이를 보존. 서비스 중단 후라면 아래 exact 복귀 |
| RAM/disk/credit·job/writer gate | 새 DB/runner 시작 금지. 운영 복귀 후 연기. reserve 축소 금지 |
| DB 초기화/migration·metadata/strict 실패 | 전용 실험만 중단/정리. 운영 DB migration/rollback/restore 실행 금지 |
| Docker timeout/cleanup 실패 | 새 단계 금지. creation-intents와 owner/name·actual container 상태·mount/network 연결 조사. 부하 runner/DB가 아직 실행 중이면 운영 stack을 겹쳐 시작하지 않음 |
| 불명/세션 단절/OS 정지 | lock과 evidence 보존. 실제 daemon/process 상태·기존 명령 종료를 담당자가 확인하기 전 unlock/재시도 금지 |

수동 회수는 `creation-intents.private.jsonl`에 있는 **exact 이름만** 대상으로 한다. 예를 들어 실제 발견한 이름을`RESOURCE`로 설정하고 owner를 먼저 확인한다. 자동 wildcard/전체 목록 삭제를 하지 않는다.

```sh
docker inspect --format '{{index .Config.Labels "owner"}} {{.State.Running}}' "$RESOURCE"
timeout 20 docker stop --time 5 "$RESOURCE"
docker inspect --format '{{index .Config.Labels "owner"}} {{.State.Running}}' "$RESOURCE"
```

기대: 두 조회의 owner=`$OWNER`, 마지막 Running=false. Docker 응답이 불명확하거나 owner/name 다르면 손대지 않는다. 정지 확정 후`timeout 20 docker rm "$RESOURCE"`로 해당 container만 회수한다. volume은 owner exact·`docker ps -aq --filter volume="$RESOURCE"` 빈 결과, network는 owner exact·Containers 빈 결과를 확인한 뒤 해당 이름만`volume rm`/`network rm`한다. inspect 실패를 부재로 간주하지 않는다.

**정리 실패 시 복귀 조건:** 실험 runner/DB/init가 실제로 모두 정지했고 재시작 정책no이며, 운영 서비스가 실험 volume/network/credential을 전혀 사용하지 않고, 남은 inert 자원이 운영 시작 disk/reserve를 침범하지 않는지 확인해야 한다. 불명확하면 복귀를 강행하지 말고 팀 복귀 담당에게 넘긴다. 컨테이너 정지·미사용을 입증한 volume/network 삭제 실패만 남았다면 잔여를 보호 기록에 남기고 운영 복귀를 우선할 수 있다. 그 뒤 새 실험은 금지다.

복귀 전 `operational_snapshot()`을 다시 읽어 파일/tuple/pointer·ID/image/mount/host config/network가 원 snapshot과 exact인지 `operational_gate(...,restored=None)`로 확인한다. 이 복귀용 검사는 부분 중단 실패 때 원래 실행 중이던 서비스가 계속 실행 중인 상태도 허용하며, 원래 정지 상태였던 서비스의 예기치 않은 실행은 거부한다. original snapshot에서 **원래 running=true였고 지금 정지한 서비스만** MySQL→API→Worker 순서로 start한다. 다음 블록도 SERVICE를 하나씩 바꾸며 실행한다. MySQL healthy가 되기 전 API/Worker로 넘어가지 않는다.

```sh
export SERVICE=mysql
python3 - <<'PY'
import json,os
from pathlib import Path
from recording_cpu_quota_supervisor import bounded_capture
r=Path(os.environ['PROBE_HOME'])/'evidence'
s=json.loads((r/'operational-snapshot.private.json').read_text())['services'][os.environ['SERVICE']]
v=json.loads(bounded_capture(['docker','inspect',s['id']],15,r).stdout)[0]
assert v['Id']==s['id'] and v['Image']==s['image'] and v['Mounts']==s['mounts']
if s['running'] and not v['State']['Running']:
    p=bounded_capture(['docker','start',s['id']],30,r); assert p.returncode==0
print('PASS_EXACT_ORIGINAL_SERVICE_START')
PY
```

health는 exact ID의 `docker inspect --format '{{json .State.Health}}'`로 보호 확인한다. API는 `timeout 30 docker exec "$API_ID" python /app/docker/runtime.py ready`, Worker는 `timeout 30 docker exec "$WORKER_ID" python /app/docker/runtime.py worker-status`, API는 같은 방식으로 `deploy-smoke`를 실행한다. 각 ID는 snapshot에서 가져오며 공개하지 않는다. 무한 until loop를 쓰지 않고 기존 RT-14의120초 확인 범위에서 유한하게 확인한다. Worker status는8종 등록/실제 process 확인이며 job 건강의 대체가 아니다. job 건수·lease/heartbeat·예상 밖 신규 job 부재도 담당자가 재확인한다.

복귀는 같은 container/image/config/schema/pointer에서 start만 하며 migration·새 revision 배포·rollback을 끼워 넣지 않는다. 원래 정지 상태였던 서비스는 시작하지 않는다. current/previous/schema/approval/policy/config hash·volume/network·Caddy/mount 상태를 재대조하고 `operational_gate(...,restored=True)`로 원래 running 상태를 확인한다. 허용된 외부 단말에서 기존 public smoke를 확인할 때까지 public 경로는 UNKNOWN이다.

모두 확인한 후 lock의owner/evidence 일치·controller/실험 process 종료를 재확인한다. marker를 보호 기록에 남겨 해당 marker만 unlink하고 빈 `operation.lock`만 rmdir한다. 다른 owner의 lock이나 dirty는 삭제하지 않는다. 마지막에 팀의 ingress/writer/job/배포/backup 통제를 담당자가 해제한다. 복귀 실패 시 lock/증거와 통제를 유지하고 RT-14 복귀 담당에게 인계한다.

향후 실제 제품 배포에서는 `recording_0002`와metadata envelope decoder에 대한 구 코드 rollback 비호환을 별도로 검토한다. 이번 전용 DB는 운영 DB와 분리돼 있으므로 이 문제를 운영 migration 선행 실행이나 새 revision 전환으로 해결하지 않는다.
