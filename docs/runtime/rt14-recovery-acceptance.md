# RT-14 DB·media 백업·격리 복원 acceptance 준비

**IN_PROGRESS · Refs #450 · Related #300, #452 · 2026-10-31**

이 문서는 실제 실행을 위한 **조건부 운영 계획**이다. 이번 변경에서는 AWS 접속·SSM·workflow dispatch·배포·운영 정지·실제 backup/restore를 실행하지 않았다. 운영자가 이번 대화에서 제공한 조치 결과는 [실험 기록 후속](experiments/2026-10-31-rt14-aws-real-e2e.md#14-운영자-제공-후속-조치)에 구분해 남긴다. 기존 [Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522291826), [설계](rt14-deployment-design.md), [공개 배포 절차](rt14-public-deployment.md)는 재개방하지 않는다.

## 1. 기존 도구 평가와 실행 판정

| 구성 | 재사용 범위 | 제약·금지 조건 |
| --- | --- | --- |
| `scripts/backup_compose.py` | MySQL 8.4 `daesingo`, exclusive 0600 envelope, heads/길이/hash, writer 정지 확인, 빈 target guard, import 후 전체 re-dump bytes 동일성 | dump·포장·검증이 메모리 방식. media 파일 미포함. source routines/events 거부. 외부 writer/DDL·host 배포를 막지 않음. hash가 맞아도 신뢰하지 않는 SQL 입력 금지 |
| `scripts/smoke_backup_restore.py` | 승인된 별도 시험 자원에서 기존 합성 회귀를 실행할 때만 사용 | 무작위 **테스트 project의 DB volume을 삭제·교체**한다. 운영 project/volume 주입 및 운영 대상 helper 호출 금지. 원래 media volume 유지 검사는 media 복원 성공이 아님. build·MySQL·Paddle stack을 추가하므로 현재 4GiB 호스트에서 실행하지 않음 |
| `tests/deploy/backup_probe.py` | 작은 합성 fixture의 전체 행/identity/BLOB fingerprint 검증 의미 참고 | `.all()`·hex/JSON 직렬화가 추가 메모리를 쓴다. 운영 전체 DB에 그대로 적용하지 않음. 실제 복원 DB 동등성은 기존 도구의 migration 전 re-dump 비교를 우선 사용 |
| `deploy/ec2.py` | 실제 project/volume/config·exact image·current/previous/schema/pointer 계약과 host lock 의미 | preflight 자체도 AWS 조회/pull·Compose render·container 실행을 한다. **읽기 전용 조사 명령으로 호출하지 않음**. backup 도구는 host lock을 자동 획득하지 않음 |

**현재 판정: 운영 크기 backup/격리 복원 실행 입력 미충족.** 약 4GiB라는 사양만으로 실행 가능 판정을 하지 않는다. Gate A/B 확인 전 큰 dump, 추가 MySQL 또는 Paddle stack을 시작하지 않는다. 코드 보완 없이 기존 도구를 사용할 수 있는 범위는 **source release와 heads가 같고 승인된 자원 예산 안의 신뢰하는 artifact**다.

### Gate A — source 백업 예산

- `D`: hex BLOB을 포함한 실제 SQL byte 상한, `M`: media 전체 byte, `F`: 대상 filesystem free, `A`: 작업 시점 MemAvailable. `information_schema.tables`의 DATA_LENGTH/INDEX_LENGTH/TABLE_ROWS는 추정이며 `D` 상한으로 쓰지 않는다. `--hex-blob`은 BLOB 원문보다 SQL을 늘린다.
- `_call(capture_output=True)`는 stdout/stderr를 보관한다. `output.split(SEPARATOR, 1)`은 dump를 복사하고, `pack()`은 dump와 결합한 새 bytes를 만든다. restore의 `read_bytes()`·`unpack()` slice/split·SQL input·re-dump 비교에도 큰 데이터 여러 개가 겹친다. subprocess 통신 buffer, Python allocator, MySQL buffer/조회 working set, OS/page cache도 별도다. `--quick`은 **host Python을 streaming으로 바꾸지 않는다**.
- `D`만큼 RAM이 남으면 된다는 계산은 금지한다. 승인된 비운영 자원에서 대표 상한 데이터의 **backup / envelope 검사 / restore+re-dump 각 peak RSS와 MySQL·호스트 여유**를 관측하고 실제 상한/동시 workload에 적용 가능한 근거를 붙인다. 안전 배수·여유율을 이 문서에서 발명하지 않는다. 근거를 얻으려고 운영에서 먼저 큰 dump를 시도하지 않는다.
- disk 추가분에는 DB artifact, media archive, manifest/보호 증거, 실패 잔여와 현재/previous image·logs·DB 증가를 넣는다. 비압축 tar도 header/padding 비용이 있으므로 `M`과 동일시하지 않는다. 기존 승인 reserve를 침범하면 중단한다.

### Gate B — 격리 복원 예산

새 DB data/index·redo/temp, media **별도 사본**, API asset 응답의 detached bytes, backup 보존분, import/re-dump RAM과 로그를 합산한다. DB만 → API → offline OCR 순서로 실행하고 단계별 재측정한다. 순차 실행도 예산 근거가 없으면 금지한다. 다른 호스트를 쓰려면 운영자가 대상·자원·보호 전송을 승인/제공해야 하며 이번 작업에서 새 EC2/EBS를 만들지 않는다.

| 불충족 조건 | 필요한 최소 후속 |
| --- | --- |
| `D` 상한/peak 근거 없음 또는 4GiB 예산 부족 | 실행 보류. 승인된 별도 자원에서 근거 확보 또는 기존 envelope를 유지하는 file-backed streaming capture/pack/검증/re-dump 비교의 최소 보완을 별도 구현·실패 재현/회귀 검증. 이번에 구현한 기능은 아님 |
| client별 기존 180초/host 호출 600초 내 완료 근거 없음 | timeout/gate를 완화하지 않고 보류. 승인 자원/데이터 범위·별도 보완 검토 |
| heads 불일치 | source image에서 확인한 migrations와 검토된 도구를 함께 준비. header 변조·운영 migration·최신 checkout 강제 사용 금지 |
| media/ref/GET 표본 또는 provider 없는 검증 근거 없음 | Recording/Case 담당자가 보호된 표본·예상값 제공. 운영 media 재사용/실제 provider 호출로 대체 금지 |

## 2. 입력과 보호 경계

아래 명령은 **향후 승인된 Linux 호스트 root 세션**용이며 이번에 실행하지 않았다. Windows checkout에서 실행하지 않는다. 한 블록씩 실행하고 nonzero면 다음 블록을 진행하지 않는다. `set -x`, 전체 env/secret/SQL/inspect 출력 금지. 오류 원문·redirect도 보호 경로 안에서만 보관한다. 문서의 Python 예시는 향후 운영자가 보호 경로에 저장할 절차이며 새 배포 도구가 아니다.

| 입력 | 제공·확인 주체 | 조건 |
| --- | --- | --- |
| `SOURCE_PROJECT`, `SOURCE_COMPOSE` | 운영자 | policy·실제 container Compose label·`release-compose.json` 대조. local `compose.yaml`로 대체 금지 |
| `SOURCE_API`, `SOURCE_MEDIA_ROOT` | 운영자 | 실제 API container ID와 `/media` volume의 host Mountpoint. volume 소유 label/다른 사용자를 확인 |
| `TOOL_ROOT`, `APP_IMAGE`, `MYSQL_IMAGE`, `MYSQL_UID`, `MYSQL_GID` | Runtime + 운영자 | 검토한 script/migrations 경로, source exact app digest, MySQL 8.4 digest·실측 owner. 이미 준비된 image만 사용 |
| `RUN` | 운영자 | repo/build context·public releases·`/srv/daesingo` 밖의 **이번 실행 전용 신규 root0700 경로**. 모든 조상 경로의 접근 통제 확인. Git checkout 안이면 `git check-ignore`도 확인하지만 Git 밖 보호 보관 우선 |
| `TARGET_PROJECT`와 target host | 운영자/인프라 | source와 다른 신규 무작위 이름, 같은 이름 container/volume/network 없음, Gate B 승인 |
| `http-input.json` | Case/Recording + 운영자 | 실제 존재하는 `case_id`/`asset_ref` 키의 JSON. 식별자·원문은 `RUN` 안에만 보관. source GET 시점과 쓰기 중단 DB를 결속 |
| writer/DDL·배포 중단/복귀 담당, 점검 창 | 팀 + Runtime/Ops Owner | 외부 DB writer·예약 작업·직접 SQL·config/배포·cleanup 모두 조사, 중지/재개 책임과 종료 확인 방법 명시 |
| RPO/RTO·retention·오프호스트 보관 | Runtime/Ops Owner + 데이터/인프라 | 미승인. 단회 acceptance와 별도 결정. 값·보존 일수·목적지를 임의 확정하지 않음 |

운영자는 `RUN`을 새로 준비한 뒤 소유권/권한/용량을 확인한다. source config 복구 보존이 필요하면 immutable config를 변경하지 말고 승인된 보호 저장소를 사용한다. **config ID/hash만으로 secret 복구 가능성을 증명할 수 없다.** 운영 credential을 target으로 복사하지 않는다.

```sh
set -eu
umask 077
test "$(id -u)" = 0
: "${RUN:?신규 보호 작업 경로 필요}"
: "${TOOL_ROOT:?검토한 도구 경로 필요}"
: "${SOURCE_PROJECT:?실제 운영 project 필요}"
: "${SOURCE_COMPOSE:?실제 운영 Compose 파일 필요}"
export COMPOSE_DISABLE_ENV_FILE=1
source_compose() { docker compose --project-name "$SOURCE_PROJECT" -f "$SOURCE_COMPOSE" "$@"; }
```

## 3. 읽기 전용 사전점검

서비스 변경 전 실행한다. 결과는 `RUN`에만 저장하고 공개 요약에는 판정·비민감 수치만 사용한다. 이 단계에서 lock 생성·서비스 정지·새 container·dump를 하지 않는다.

```sh
free -b > "$RUN/memory-before.txt"
df -B1 /opt/daesingo "$RUN" > "$RUN/disk-before.txt"
docker version > "$RUN/docker-version.txt" 2>&1
docker compose version > "$RUN/compose-version.txt" 2>&1
source_compose ps --all --format json > "$RUN/source-services.json" 2>&1
command -v python3 tar sha256sum timeout cmp > "$RUN/tools.txt"
test ! -e /opt/daesingo/dirty.json
test ! -e /opt/daesingo/operation.lock
```

1. `current.json`, `previous.json`의 **부재 포함**, `schema.json`, policy, approval, release-compose, `releases/current`를 보호된 사전 snapshot에 저장한다. container image ID/OCI revision/`DAESINGO_REVISION`, Compose project/service label, config bind source/권한, DB/media mount와 volume owner/purpose를 **필요 필드만** 추출해 대조한다. 실제 source가 과거 RC와 같다고 가정하지 않는다. DB/media의 다른 project 사용자가 있으면 중단한다.
2. 다음 SELECT 블록을 `RUN/db-readonly.sh`로 저장한다. 기존 mysql container의 app password만 쓰고 DB를 변경하지 않는다. 0400 secret 형식이 기존 도구 조건과 같은지 먼저 확인한다. DB 밖 임시 client 파일은 container 내부 0700/0600이며 SQL/secret/오류를 공개하지 않는다.

```sh
set -eu
umask 077
private=$(mktemp -d /tmp/rt14-readonly.XXXXXXXX)
trap 'rm -f "$private/client.cnf"; rmdir "$private"' EXIT
trap 'exit 1' HUP INT TERM
password=$(cat /run/secrets/mysql-password)
test -n "$password"
escaped=$(printf '%s' "$password" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '[client]\nuser=daesingo\npassword="%s"\n' "$escaped" > "$private/client.cnf"
unset password escaped
timeout 180 mysql --defaults-extra-file="$private/client.cnf" --batch --skip-column-names \
  --raw --database=daesingo <<'SQL'
SELECT VERSION(), @@SESSION.max_allowed_packet;
SELECT 'case',version_num FROM case_alembic_version UNION ALL SELECT 'recording',version_num FROM recording_alembic_version UNION ALL SELECT 'runtime',version_num FROM runtime_alembic_version ORDER BY 1;
SELECT COALESCE(SUM(DATA_LENGTH),0),COALESCE(SUM(INDEX_LENGTH),0) FROM information_schema.tables WHERE table_schema='daesingo';
SELECT table_type,engine,COUNT(*) FROM information_schema.tables WHERE table_schema='daesingo' GROUP BY table_type,engine;
SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='daesingo';
SELECT COUNT(*) FROM information_schema.events WHERE event_schema='daesingo';
SELECT COALESCE(SUM(status='QUEUED'),0),COALESCE(SUM(status='RUNNING'),0),COALESCE(SUM(status IN ('SUCCEEDED','FAILED') AND case_applied_at IS NULL),0) FROM job_execution;
SQL
```

```sh
source_compose exec -T mysql sh -s < "$RUN/db-readonly.sh" \
  > "$RUN/db-preflight.tsv" 2> "$RUN/db-preflight.err"
```

지원하지 않는 engine/routines/events, 예상하지 않은 schema/trigger, SELECT 권한 부족이면 조사 후 중단한다. 기존 도구가 확인하지 않는 외부 writer/session/DDL도 DB 담당자가 별도 조회·통제한다. app 계정의 제한된 조회만으로 외부 writer 부재를 단정하지 않는다.

3. checkout·running image·실제 DB 세 registry의 heads가 같아야 한다. AST 함수는 metadata만 읽고 migration을 실행하지 않는다. source image에는 scripts가 없으므로 `/app/scripts/backup_compose.py` 호출은 하지 않는다. API의 `/app/migrations`를 읽기 복사하고 같은 검토 도구로 대조한다.

```sh
mkdir -m 700 "$RUN/source-release" "$RUN/source-release/scripts"
docker cp "$SOURCE_API:/app/migrations" "$RUN/source-release/migrations" \
  > "$RUN/migrations-copy.txt" 2>&1
cp "$TOOL_ROOT/scripts/backup_compose.py" "$RUN/source-release/scripts/backup_compose.py"
python3 - "$TOOL_ROOT" "$RUN/source-release" > "$RUN/heads.json" 2> "$RUN/heads.err" <<'PY'
import importlib.util, json, pathlib, sys
def heads(root):
    spec = importlib.util.spec_from_file_location("backup_check", pathlib.Path(root) / "scripts/backup_compose.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migration_heads()
local, running = (heads(root) for root in sys.argv[1:])
if local != running:
    raise SystemExit("migration heads가 일치하지 않습니다")
print(json.dumps(running, sort_keys=True))
PY
```

`heads.json`과 `db-preflight.tsv`의 case/runtime/recording 값을 운영자가 대조한다. source revision·tool SHA·migration tree hash를 보호 기록에 남긴다. 불일치하면 source와 호환되는 검토 tool/migrations 묶음을 새로 준비하고 `TOOL_ROOT`를 바꾼다. 운영 migration/header 수정으로 맞추지 않는다.

4. media의 `du -sb`/`du -sB1`(논리/할당), 모든 관련 filesystem의 `df -B1`, `/proc/meminfo`, `docker stats --no-stream`을 보호 저장하고 Gate A/B를 검토한다. DB 크기는 dump 상한이 아니다. 다른 filesystem이면 root free만으로 판단하지 않는다. 보호 파일 mode/owner·실행 도구·mysql 내부 timeout/mktemp·로컬 image 가용성도 확인한다.
5. Recording 담당자가 DB BLOB과 filesystem ref/locator inventory를 확인한다. media root 밖 외부 파일, symlink/특수 파일/하위 mount가 있으면 범위를 임의 확장하지 않고 중단한다. 아래 manifest는 chunk hash를 사용하며 전체 영상/dump를 메모리에 올리지 않는다. 파일 개수·디렉터리 열거 비용도 예산에 포함한다.

다음을 `RUN/media-manifest.py`로 저장한다. stdout은 보호 JSONL에만 redirect한다.

```python
import hashlib, json, os, pathlib, stat, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
device = root.stat().st_dev
for base, directories, files in os.walk(root, followlinks=False):
    directories.sort()
    for name in sorted(directories + files):
        path = pathlib.Path(base) / name
        info = path.lstat()
        if info.st_dev != device or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise SystemExit("지원하지 않는 media 항목입니다")
        row = {"path": path.relative_to(root).as_posix(), "type": "dir" if path.is_dir() else "file"}
        if row["type"] == "file":
            with path.open("rb") as stream:
                row.update(size=info.st_size, sha256=hashlib.file_digest(stream, "sha256").hexdigest())
        print(json.dumps(row, sort_keys=True, ensure_ascii=True))
```

GET 증거용 다음 코드를 `RUN/http-proof.py`로 저장한다. API container 안에서 실행하며 입력은 `http-input.json`의 JSON이다. stdout의 CaseView 원문은 보호 파일로만 저장한다.

```python
import hashlib, json, sys, urllib.parse, urllib.request
identity = json.load(sys.stdin)
case = urllib.parse.quote(identity["case_id"], safe="")
asset = urllib.parse.quote(identity["asset_ref"], safe="")
base = "http://127.0.0.1:8000/cases/" + case
with urllib.request.urlopen(base + "/view", timeout=15) as response:
    if response.status != 200:
        raise SystemExit("CaseView 조회에 실패했습니다")
    view = json.load(response)
digest, size = hashlib.sha256(), 0
with urllib.request.urlopen(base + "/assets/" + asset, timeout=15) as response:
    if response.status != 200:
        raise SystemExit("asset 조회에 실패했습니다")
    content_type = response.headers.get("Content-Type")
    while block := response.read(1024 * 1024):
        size += len(block)
        digest.update(block)
print(json.dumps({"view": view, "asset": {"size": size, "sha256": digest.hexdigest(), "content_type": content_type}}, sort_keys=True))
```

## 4. 일관된 백업과 운영 복귀

### 4.1 배포·writer·두 lock

| lock | 범위 | 통제 |
| --- | --- | --- |
| `/opt/daesingo/operation.lock` | RT-14 deploy/rollback/configure | backup 도구는 자동 획득하지 않는다. 운영자가 command/controller 종료와 dirty 부재를 확인하고 같은 atomic mkdir로 유지. 기존 lock 강탈 금지 |
| mysql container `/tmp/daesingo-rt13-logical.lock` | RT-13 backup/restore client | 도구가 획득/trap 해제. host lock 대체 아님. CLI 단절 뒤 remote client가 계속될 수 있어 process/기존 deadline 확인 전 삭제 금지 |

팀이 dispatch·수동 writer/DDL·예약/cleanup을 통제한 뒤에만:

```sh
mkdir -m 700 /opt/daesingo/operation.lock
touch "$RUN/host-lock-owned"
```

mkdir 실패 시 다음 단계 금지. 이번 run이 획득한 기록과 process 상태를 대조해 마지막에만 rmdir한다. lock 중 controller/configure를 호출하지 않는다.

### 4.2 같은 쓰기 중단 시점

1. 점검 창에 `systemctl stop caddy`로 ingress를 닫는다. 기존 설정·enabled·TLS data를 보존하며 SG/DNS를 바꾸지 않는다. loopback API·직접 DB·예약 작업 등 다른 경로도 담당자가 통제한다.
2. 외부 신규 요청이 없고 기존 API 요청이 완료된 상태에서 Worker가 기존 job/반영을 끝내는지 §3 SELECT로 확인한다. 이 **단회 backup acceptance**는 future available_at을 포함한 QUEUED/RUNNING 및 미반영 SUCCEEDED/FAILED 모두 0을 요구한다. 0이 안 되면 연기하며 job 삭제/강제 성공을 하지 않는다. 기존 deploy의 graceful-stop 정책을 full drain 필수로 변경하는 것이 아니다.
3. `source_compose stop worker migrate`. 실제 process 종료, 외부 writer/session/DDL 부재와 queue 0을 재확인한다. API가 계속 켜진 동안에는 읽기 GET만 허용하고 cleanup/진행 요청도 통제한다. 아래 baseline을 얻은 뒤 API를 정지한다.

```sh
source_compose exec -T api python -c "$(cat "$RUN/http-proof.py")" \
  < "$RUN/http-input.json" > "$RUN/source-http.json" 2> "$RUN/source-http.err"
source_compose stop api
source_compose exec -T mysql sh -s < "$RUN/db-readonly.sh" \
  > "$RUN/db-at-stop.tsv" 2> "$RUN/db-at-stop.err"
```

4. 모든 writer·media cleanup·진행 요청이 끝난 시각을 `write_stop_at`으로 기록한다. baseline GET 뒤 DB/media 변경이 있었으면 baseline과 중단점 동일성을 담당자가 확인하거나 점검을 다시 잡는다. MySQL만 가동한 채 DB dump와 media 사본/manifest를 모두 이 쓰기 중단 기간에 얻는다. 중간에 writer가 동작하면 같은 세트로 채택하지 않는다. API가 꺼져도 외부 DB writer/DDL이 있으면 tool의 quiescence 검사만으로 진행하지 않는다.

### 4.3 DB·media·hash 결속

```sh
mkdir -m 700 "$RUN/db"
python3 "$RUN/media-manifest.py" "$SOURCE_MEDIA_ROOT" \
  > "$RUN/media-before.jsonl" 2> "$RUN/media-before.err"
python3 "$TOOL_ROOT/scripts/backup_compose.py" backup \
  --project "$SOURCE_PROJECT" --compose-file "$SOURCE_COMPOSE" --directory "$RUN/db" \
  > "$RUN/backup-result.txt" 2> "$RUN/backup-error.txt"
tar --create --file "$RUN/media.tar" --directory "$SOURCE_MEDIA_ROOT" . \
  2> "$RUN/media-tar.err"
python3 "$RUN/media-manifest.py" "$SOURCE_MEDIA_ROOT" \
  > "$RUN/media-after.jsonl" 2> "$RUN/media-after.err"
cmp "$RUN/media-before.jsonl" "$RUN/media-after.jsonl"
(cd "$RUN" && sha256sum db/logical.rt13 media.tar media-before.jsonl source-http.json heads.json > artifacts.sha256)
```

`tar`의 변경 파일/error와 종료 코드를 확인한다. source 권한/owner도 archive에 보존한다. 보호된 `binding.json`에 format, write_stop_at, source exact revision/image/config ID/project, MySQL digest, DB heads, artifact/manifest hash, current/previous/schema/policy/approval/Compose/config 파일 hash, Web pointer, tool hash, 취득자·검증 상태를 기록한다. previous 부재도 명시한다. 실제 config 원문은 별도 보호 보존 정책을 따른다.

내부 manifest/CaseView/ID/ref/원문 SQL/영상/credential은 Git·Issue·로그에 넣지 않는다. DB envelope/hash는 완전성 검사이며 서명·암호화·인증이 아니다. dump/media를 평문 기밀자료로 취급하고 저장소 암호화·접근권한·보호 전송을 확인한다. 완전한 세트 검사 전 성공 마커를 붙이지 않는다.

### 4.4 운영 복귀 우선

성공/실패와 관계없이 remote client/process 종료와 불완전 artifact 격리 판단 후 **같은 source**를 먼저 복귀시킨다. DB/media/schema/secret/Compose가 변경되지 않았음을 확인한다.

```sh
source_compose start api worker
# 기존 controller health의 120초/3초 범위로 호스트 CLI까지 제한한다.
timeout --signal=KILL 120 sh -s -- "$SOURCE_PROJECT" "$SOURCE_COMPOSE" \
  > "$RUN/source-recovery-check.txt" 2>&1 <<'SH'
set -eu
until docker compose --project-name "$1" -f "$2" exec -T api python /app/docker/runtime.py ready \
  && docker compose --project-name "$1" -f "$2" exec -T worker python /app/docker/runtime.py worker-status; do
  sleep 3
done
SH
source_compose exec -T api python /app/docker/runtime.py deploy-smoke
systemctl start caddy
```

migrate 재실행 금지. container 부재·image/config 불일치면 up/recreate로 맞추지 말고 조사한다. 위 제한은 runtime.py 내부 HTTP timeout만이 아니라 전체 확인 블록과 Docker CLI에 적용된다. 시간 초과는 UNKNOWN이며 호스트 CLI 종료가 container 내부 exec의 즉시 종료를 보장하지 않는다. 다음 단계 대신 §7로 가서 실제 상태를 조사한다. 제품·workflow·기존 도구의 timeout 정책은 변경하지 않는다.

API/MySQL health·Worker status/8종, current/previous/schema/Compose/policy/approval/config hash·pointer·mount와 enabled 상태를 재대조한다. Caddy는 동일 제한으로 복귀한다. **허용 외 local HTTPS 403은 외부 Web 200/public smoke 성공이 아니다.** 허용된 외부 PC에서 기존 `deploy/public_smoke.py`를 같은 revision으로 실행한다. 미실행이면 외부 경로 UNKNOWN을 보고한다.

이번 run의 lock과 종료 상태가 확인된 뒤 `rmdir /opt/daesingo/operation.lock`하고 팀의 writer/DDL/dispatch 통제를 해제한다. lock 소유 메모는 보호 기록에 남긴다. 백업 실패 때도 운영 복귀를 생략하지 않는다.

## 5. 전용 빈 target 준비

운영 복귀 후 Gate B를 다시 통과해야 한다. 같은 호스트가 불가능하면 승인된 다른 호스트에서 보호 전송·image 가용성·권한을 재확인한다. 운영 Compose를 overlay하지 않는다. 다음 코드로 **새 target Compose와 새 credential만** 만든다. 운영 config/env/credential을 읽거나 복사하지 않는다. target에는 migrate/일반 worker, 외부 port, awslogs, 운영 network/volume, docker.sock/host gateway가 없다.

다음을 `RUN/prepare-target.py`로 저장한다. 실행 전 변수는 확인한 digest/실측 UID/GID/신규 project이며 secret 값은 아니다. root 세션에서만 실행하고 stdout/stderr도 보호한다.

```python
import json, os, pathlib, re, secrets
run = pathlib.Path(os.environ["RUN"])
project = os.environ["TARGET_PROJECT"]
if not re.fullmatch(r"rt14-restore-[0-9a-f]{12}", project) or project == os.environ["SOURCE_PROJECT"]:
    raise SystemExit("전용 target project를 확인하세요")
uid, gid = int(os.environ["MYSQL_UID"]), int(os.environ["MYSQL_GID"])
app, mysql = os.environ["APP_IMAGE"], os.environ["MYSQL_IMAGE"]
if not re.search(r"@sha256:[0-9a-f]{64}$", app) or not re.fullmatch(r"mysql@sha256:[0-9a-f]{64}", mysql):
    raise SystemExit("확인한 exact image가 필요합니다")
private = run / "target-config"
private.mkdir(mode=0o700)
password, root_password = secrets.token_hex(32), secrets.token_hex(32)
def protected(name, value, owner, group):
    path = private / name
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)
    os.chown(path, owner, group)
    path.chmod(0o400)
    return str(path)
app_secret = protected("mysql-password", password, uid, gid)
root_secret = protected("mysql-root-password", root_password, uid, gid)
# hex 생성값은 URL에서 안전하다. 운영 password는 사용하지 않는다.
runtime = protected("runtime.env", "\n".join([
    "DAESINGO_RUNTIME_DB_URL=mysql+pymysql://daesingo:" + password + "@mysql/daesingo",
    "DAESINGO_RUNTIME_MEDIA_ROOT=/media", "DAESINGO_RUNTIME_API_TEMP_ROOT=/media/api-temp",
    "DAESINGO_RUNTIME_WORKER_TEMP_ROOT=/media/worker-temp", "",
]), 10001, 10001)
def bind(source, target):
    return {"type": "bind", "source": source, "target": target, "read_only": True,
            "bind": {"create_host_path": False}}
common = {"restart": "no", "logging": {"driver": "none"}, "networks": ["recovery"]}
config = {"services": {
    "mysql": {**common, "image": mysql, "environment": {"MYSQL_DATABASE": "daesingo",
        "MYSQL_USER": "daesingo", "MYSQL_PASSWORD_FILE": "/run/secrets/mysql-password",
        "MYSQL_ROOT_PASSWORD_FILE": "/run/secrets/mysql-root-password"},
        "volumes": [{"type": "volume", "source": "mysql_data", "target": "/var/lib/mysql"},
                    bind(app_secret, "/run/secrets/mysql-password"), bind(root_secret, "/run/secrets/mysql-root-password")],
        "healthcheck": {"test": ["CMD", "mysqladmin", "ping", "--protocol=tcp", "--host=127.0.0.1", "--silent"],
                        "interval": "10s", "timeout": "5s", "retries": 10, "start_period": "30s"}},
    "api": {**common, "image": app, "user": "10001:10001",
        "environment": {"DAESINGO_ENV_FILE": "/run/secrets/runtime.env"},
        "command": ["python", "/app/docker/runtime.py", "api"],
        "volumes": [{"type": "volume", "source": "media", "target": "/media", "volume": {"nocopy": True}},
                    bind(runtime, "/run/secrets/runtime.env")]},
}, "volumes": {name: {"name": project + "_" + name} for name in ("mysql_data", "media")},
   "networks": {"recovery": {"name": project + "_recovery", "internal": True}}}
with (run / "target-compose.json").open("x", encoding="utf-8") as stream:
    json.dump(config, stream)
```

```sh
export RUN SOURCE_PROJECT APP_IMAGE MYSQL_IMAGE MYSQL_UID MYSQL_GID
TARGET_PROJECT="rt14-restore-$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
export TARGET_PROJECT
python3 "$RUN/prepare-target.py" > "$RUN/prepare-target.txt" 2> "$RUN/prepare-target.err"
TARGET_COMPOSE="$RUN/target-compose.json"
target_compose() { docker compose --project-name "$TARGET_PROJECT" -f "$TARGET_COMPOSE" "$@"; }
target_compose config --quiet
```

구체화한 Compose의 image·mount·network·credential key allowlist를 검토한다. project label뿐 아니라 exact `${TARGET_PROJECT}_mysql_data`, `_media`, `_recovery` 이름도 기존 자원과 충돌하지 않아야 한다. Docker image에 운영 secret이 없다는 기존 acceptance 근거도 확인한다. 운영자의 검토·충돌 부재 확인 후에만:

```sh
target_compose up -d --no-deps --no-build --pull never --wait mysql
target_compose create --no-build --pull never api
```

`create api`는 시작하지 않고 전용 media volume만 준비한다. `volume.nocopy`로 image의 `/media/api-temp`·`worker-temp` copy-up을 막아 archive 추출 전 빈 상태를 유지한다. 이 Compose에는 depends_on이 없으며 `create`에 지원되지 않는 `--no-deps`를 넣지 않는다. 두 volume의 Compose project/volume label·실 Mountpoint·다른 사용자 부재를 확인한다. mysql volume은 초기화되어 있으므로 target의 **DB objects=0**을 확인하고 media volume은 실제 빈 디렉터리여야 한다. target API는 아직 중지/created 상태다. target mysql에 §3 client 구성 방식으로 `SELECT COUNT(*)`를 tables/routines/events에만 실행한다. 아직 없는 version/job table은 조회하지 않는다. 기존 restore도 import 직전 clean-target guard를 수행한다.

## 6. artifact 검사·media 복원·import

1. 취득/전송 신뢰, binding/artifact hash, mode/owner, heads, tool hash와 target의 비운영성을 다시 확인한다. Gate B 확인 뒤에만 envelope 검사도 실행한다. 기존 restore는 아래 검사에 더해 import 전에 다시 검사한다.

```sh
(cd "$RUN" && sha256sum --check artifacts.sha256) > "$RUN/artifact-check.txt" 2>&1
python3 - "$TOOL_ROOT" "$RUN/db/logical.rt13" > "$RUN/envelope-check.txt" 2> "$RUN/envelope-check.err" <<'PY'
import pathlib, sys
sys.path.insert(0, sys.argv[1] + "/scripts")
from backup_compose import migration_heads, unpack
try:
    unpack(pathlib.Path(sys.argv[2]).read_bytes(), migration_heads())
except Exception:
    raise SystemExit("백업 artifact 검사가 실패했습니다") from None
print("백업 artifact 검사 PASS")
PY
```

2. `tar --list --file "$RUN/media.tar"`를 보호 파일에 저장한다. entry의 절대 path/`..`/symlink/특수 파일·하위 mount·예상 외 tree를 검토해 거부한다. source에서 직접 생성하고 hash를 결속한 **신뢰하는 자체 archive만** 입력한다. hardlink가 있으면 내부 정상 대상인지 확인하며 불명확하면 중단한다. target media Mountpoint를 `TARGET_MEDIA_ROOT`에 명시하고 신규 빈 전용 volume인지 재확인한다. 운영 media bind/reuse 금지.

```sh
tar --list --file "$RUN/media.tar" > "$RUN/media-entries.txt" 2> "$RUN/media-list.err"
# entry 검토·전용 빈 volume·실 Mountpoint 확인이 완료된 후만 다음 명령 실행.
tar --extract --file "$RUN/media.tar" --directory "$TARGET_MEDIA_ROOT" \
  --numeric-owner --same-permissions 2> "$RUN/media-extract.err"
python3 "$RUN/media-manifest.py" "$TARGET_MEDIA_ROOT" \
  > "$RUN/media-restored.jsonl" 2> "$RUN/media-restored.err"
cmp "$RUN/media-before.jsonl" "$RUN/media-restored.jsonl"
python3 "$TOOL_ROOT/scripts/backup_compose.py" restore \
  --project "$TARGET_PROJECT" --compose-file "$TARGET_COMPOSE" --directory "$RUN/db" \
  > "$RUN/restore-result.txt" 2> "$RUN/restore-error.txt"
```

3. **migration/API/Worker 시작 전** restore exit 0·3 module heads·전체 schema/data re-dump byte 동일성(`--hex-blob` BLOB 포함)을 확인한다. 이 검사는 기존 도구가 구현한다. target heads SELECT도 별도 보호 기록으로 남긴다. DDL import는 원자적 rollback이 아니므로 실패 target은 격리하고 새 빈 target만 사용한다. 운영 DB에 재시도하지 않는다.
4. 전체 media 상대 path/length/hash 일치와 DB ref/locator inventory의 target 사본/BLOB 대응을 Recording 담당자가 확인한다. 대표 asset GET만으로 전체 파일 검사를 대체하지 않는다. 빈 media나 같은 운영 volume에서 성공한 검사는 media 복원 PASS가 아니다. archive에서 복원한 owner/mode와 UID10001의 필요한 읽기/임시 경로 쓰기 권한도 확인한다.
5. 동일 heads 복원이며 이번 acceptance에서 migration을 실행할 이유가 없다. 위 비교를 먼저 확정한 뒤 API만 시작한다. egress가 없는 target network, provider/AWS/DDNS credential 부재와 port 미공개를 재확인한다.

```sh
target_compose up -d --no-deps --no-build --pull never api
timeout --signal=KILL 120 sh -s -- "$TARGET_PROJECT" "$TARGET_COMPOSE" \
  > "$RUN/target-ready-check.txt" 2>&1 <<'SH'
set -eu
until docker compose --project-name "$1" -f "$2" exec -T api python /app/docker/runtime.py ready; do
  sleep 3
done
SH
target_compose exec -T api python /app/docker/runtime.py deploy-smoke
target_compose exec -T api python -c "$(cat "$RUN/http-proof.py")" \
  < "$RUN/http-input.json" > "$RUN/target-http.json" 2> "$RUN/target-http.err"
cmp "$RUN/source-http.json" "$RUN/target-http.json"
```

API container 내부 loopback에서 실제 CaseView·asset HTTP 200·Content-Type·실수신 길이/hash를 비교한다. ID/ref는 보호 파일로 전달하고 원문은 출력하지 않는다. 기존 API `load_asset`가 detached bytes를 만들므로 큰 asset도 Gate B 대상이다. 실패한 ref를 재생성/upload/POST/provider 호출로 보완하지 않는다. 동적 필드 차이가 나오면 임의 비교 제외 없이 Case 담당자와 원인을 판정한다.

### Worker offline 경계

복원 DB에는 실제 job이 남을 수 있으므로 **일반 Worker를 시작해 claim하지 않는다**. target DB/network/media/env도 넘기지 않는 `network none` 일회 container에서 기존 media/readout offline 명령을 순차 실행한다. 실행 전 해당 메모리 예산을 재확인한다.

```sh
docker run --rm --pull never --network none --log-driver none --entrypoint python "$APP_IMAGE" \
  /app/docker/runtime.py media-preflight > "$RUN/offline-media.txt" 2>&1
docker run --rm --pull never --network none --log-driver none --entrypoint python "$APP_IMAGE" \
  /app/docker/runtime.py readout-preflight > "$RUN/offline-readout.txt" 2>&1
```

PaddleX cache root의 임시/lock과 `/tmp` 쓰기는 기존 [production OCR 실행 조건](issue468-production-readout.md)에 따라 일회 container의 writable layer에서만 허용한다. source/target의 mount나 config를 붙이지 않고 `--rm`으로 해당 layer를 제거한다. 새 `--read-only` 제약으로 기존 OCR 성공 조건을 바꾸지 않는다.

이는 Worker 의존 toolchain/OCR의 offline 검증이며 **복원 DB의 Worker job 처리 성공은 아니다**. 8종 registry/claim/반영까지 확인하려면 기존 RT-13 합성 smoke를 별도 승인 시험 자원에서 실행한다. 그 생성 test project와 운영 artifact restore를 혼동하지 않는다. 복원 DB의 synthetic Worker 검증 harness는 이번에 추가하지 않았으며 미검증으로 남긴다. credential 부재만으로 provider 차단을 주장하지 않고 network/mount/env 경계도 확인한다.

## 7. 실패·중단·종료

| 시점 | 중단·복귀·보존 |
| --- | --- |
| preflight/Gate 불충족 | 서비스에 손대지 않고 UNKNOWN/실행 불가 기록. 추가 stack/dump를 시험 삼아 실행하지 않음 |
| ingress/API/Worker 정지 중 | process/진행 요청/queue/session·정지 성공분 조사. 같은 source만 §4.4로 복귀. migrate 재실행/lock 강탈 금지 |
| dump/media/hash 실패 | remote client/lock 종료 확인, 세트 INCOMPLETE 격리, 운영 복귀 우선. tool의 정상 예외 삭제와 SIGKILL 잔여를 구분. 원본을 보전하고 이번 불완전물만 처리. prune/기존 backup 삭제로 진행 금지 |
| source 복귀 실패 | ingress 유지 차단, 운영 담당자 호출. DB/schema를 변경하지 않았으므로 restore/rollback 자동 실행 금지. 기존 public recovery runbook과 exact 상태 대조 |
| import/DDL/동등성 실패 | 부분 target 정지·격리, source는 그대로 유지. 원 artifact와 target identity/failed phase 보존. 재시도는 새 빈 target만 |
| CLI 단절/timeout/SIGKILL | UNKNOWN. 운영자가 host/client/process/SSM 상태를 확인할 때까지 재실행/lock·volume 삭제 금지 |
| API/asset/offline 실패 | 해당 단계 FAIL, 선행 DB/media 판정과 분리. 운영 전환·provider 연결·설정 완화 금지 |

종료 시 source API/MySQL health·Worker status·Caddy/mount/Docker, current/previous/schema/policy/approval/Compose/config hash·pointer와 운영 volume/network 참조 유지를 확인한다. 복귀 후 정상 write에 의한 DB/media 변화와 중단점 snapshot을 혼동하지 않는다.

target 정리 전에 이번 생성 project/container/volume/network exact name·Compose labels·실 mount·다른 사용자 부재를 기록과 재대조한다. **운영/external volume/network가 없고** 보존 판단이 끝난 target만:

```sh
target_compose down --volumes
```

같은 labels와 exact names로 잔여를 조회해 0 또는 격리 보존 대상을 기록한다. 실패했다고 `--remove-orphans`/전체 prune/이름 pattern 일괄 삭제를 추가하지 않는다. 공유 image/cache·운영 volume·기존 backup·source config·Caddy/SG/DNS는 삭제하지 않는다. offline container의 `--rm` 종료도 확인한다.

| 보존 대상 | 처리 |
| --- | --- |
| 검증된 DB artifact/media archive/manifest/binding/source release·config 복구 참조 | Owner 보관 판단까지 보호 저장. 같은 disk의 backup만으로 host/disk 손실 보호를 증명하지 않음 |
| target password/runtime.env/Compose·비교 수신 자료·빈/부분 target | 이번 소유 여부·사고 조사 보존 판단 후 명시적으로 정리. 미승인 보존 기간을 만들지 않음 |
| RAW/dump/credential/영상/내부 manifest/식별자 | Git·공개 로그·PR/Issue 제외. 보호 경로와 암호화/접근 통제 유지 |

write_stop, backup 완료, source 복귀, import 시작/완료, API 검증 완료 시각을 기록해 실측 시간을 계산한다. **관측값은 RPO/RTO 승인값이 아니다.**

## 8. 실제 실행 전 검토물과 남은 경계

| 순서 | 검토할 구체적 실행 입력 | 담당 |
| --- | --- | --- |
| 1 | source tuple/container/heads/mount·도구 hash·DB/media/RAM/disk·외부 writer/DDL/예약 목록 | 운영자 + Runtime/Recording |
| 2 | SQL 상한/단계별 peak·기존 timeout 내 완료 근거·source/격리 host 예산/reserve | Runtime/Ops Owner + 인프라 |
| 3 | 점검 창·ingress→drain→Worker→GET→API 정지·복귀 담당·두 lock·실패 연락 | 팀 + 운영자 |
| 4 | backup 경로/권한/신뢰·암호화/보관·binding 실입력·Case/asset/ref baseline | 운영자 + 데이터/Case/Recording |
| 5 | 생성할 실제 target Compose·신규 credential·network/빈 volume·정리 목록 | Runtime + 운영자 |
| 6 | DB/media/GET/offline Worker 단계별 기대값·FAIL/UNKNOWN 처리와 잔여 검증 | Runtime/Ops Owner |

입력이 갖춰지면 운영자가 **source backup → source 복귀 → 격리 restore → 비교 → 정리**를 실행하고 보호 증거에서 비민감 판정만 후속 기록에 추가한다. 이번 로컬 문서 검증으로 AWS acceptance를 체크하지 않는다.

두 번째 정상 deploy와 previous exact tuple/Web 보존·schema 호환 rollback rehearsal은 [공개 배포 §6](rt14-public-deployment.md#6-실제-acceptance-실행-순서--rehearsal)의 별도 작업이다. 이번 절차는 current/previous/schema를 승격/변경하거나 운영 복원 전환을 승인하지 않는다. 최종 Package READY는 사건 시각 overlay·이용 동의를 받은 비마스킹 입력 등 조건을 갖춘 별도 E2E에서 PLATE_IMAGE_EXPORT·drawtext·ReportPackage 생성/소비까지 확인해야 한다. 기존 7 job·영상 다운로드나 이번 기존 asset GET으로 대체하지 않는다. #452 운영 profile/capacity·장기 공개 hardening·RPO/RTO/retention/off-host 정책도 완료로 선언하지 않는다.

## 9. 이번 로컬 검증

| 직접 로컬 검사 | 결과와 한계 |
| --- | --- |
| 문서 구문 | 쉘 block 16개 `bash -n`, Python 예제/인라인 5개 AST parse PASS. 운영 명령은 실행하지 않음 |
| 링크·이력 | 추가한 로컬 링크/anchor 13개 PASS, 기존 실험 기록/Runtime Log의 본문 prefix 보존 확인. CRLF/LF 정규화는 구분 |
| target 예제 | 파일·credential 생성 없이 메모리 대역으로 Compose 생성 검증 PASS. service=mysql/api, internal network, 외부 port/build/depends_on/external volume 부재, 새 config key allowlist, media nocopy 확인. 실제 Docker render/start/import 검증 아님 |
| CLI 정합성 | 로컬 `docker compose create/up/start --help` 읽기 확인. `create`의 미지원 `--no-deps` 제거. container/daemon 작업 없음 |
| 비노출·diff | 실제 비밀값/원문 데이터 추가 없이 절차·제공 증거만 기록. `git diff --check` PASS. private 식별자/SQL/media/내부 manifest는 제출 대상 아님 |

최초 Git Bash 구문 검사는 sandbox IPC 권한 오류로 실패했고, 로컬 구문 검사 권한으로 재실행했다. 이후 Windows에 없는 `os.chown` 때문에 **검사 대역**이 실패해 메모리 mock만 수정하고 재검사를 통과했다. 제품/문서 명령의 실제 Linux 실행 실패로 세지 않는다.

구현 이력을 상속하지 않은 fresh 읽기 전용 reviewer 1명이 전체 변경과 기존 도구를 검토했다. 초기 지적은 시작 직후 단회 상태 검사, media copy-up과 빈 target의 충돌, OCR rootfs 쓰기 경계였다. 기존 120초/3초 확인 범위의 대기·media nocopy·기존 OCR writable 일회 layer로 수정했다. 같은 reviewer의 delta 지적인 Docker CLI 자체 종료 제한도 외부 timeout으로 보완했다. **같은 reviewer 최종 재확인: 기존 지적 해결, 새 actionable P1/P2 없음.** reviewer 직접 검증은 정적 검토·diff 검사이며 실제 Docker/DB/AWS acceptance가 아니다.

도구·제품·migration·Contract·workflow·timeout·strict gate 코드는 변경하지 않았다. 문서만 변경하여 focused pytest를 추가 실행하지 않았고, 전체 pytest·전체 mandatory MySQL도 실행하지 않았다. 실제 AWS/SSM/dispatch/배포/서비스 정지/backup/restore는 미실행이다. 실행 가능 판정은 Gate A/B와 실입력 review가 남아 있다.

| 전체 변경 파일 | 이유 |
| --- | --- |
| `docs/runtime/rt14-recovery-acceptance.md` | 이 조건부 실행·중단·복귀·격리 검증 절차와 로컬/reviewer 근거 |
| `docs/runtime/experiments/2026-10-31-rt14-aws-real-e2e.md` | 운영자 제공 UID/재부팅/사본 정리를 기존 이력 뒤에 추가 |
| `docs/runtime/rt14-deployment.md` | 현재 복구 준비와 후속 증거 연결 |
| `docs/runtime/rt13b-backup-restore.md` | 로컬 DB 도구/media/두 lock/운영 적용 금지 경계 연결 |
| `docs/runtime/runtime-implementation-log.md` | 이번 작업·검증·증거 구분 후속 기록 |
| `docs/superpowers/plans/2026-10-31-rt14-recovery-acceptance.md` | 사용자 제약·문서 준비 계획·검증 진행 기록 |
