# RT-13(a) — Docker / Compose local runtime

> 현재 구성 절차는 [로컬 Runtime/Ops·Recording 실행환경](./local-runtime-environment.md)을 따른다.
> 아래 초기 구현 기록의 Paddle 미설치·mutable media toolchain·Recording 미설정 설명은 당시 이력이다.
> 현재 Dockerfile은 pinned 8.1과 production Paddle/model cache를 포함한다(#465/#468).
> `--no-cache` 전용 acceptance 명령은 일반 문서/예시 수정 검증에 반복하지 않는다.

**Status: IN_PROGRESS · Refs #300 (RT-13(a))** · PR/merge SHA: pending (미생성)

근거: [Issue #300](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300), [결정 요청](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6430017764), [Runtime/Ops Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6433879506). 2026-10-27 세션에서 본문과 두 댓글을 직접 조회했다. Runtime Plan RT-13/§12, Ops §4·§4-1·§4-2·§5, Tech §4.4·§15.2, Baseline B-W1/W4/O1/H3/§2.6, Register RD-12를 적용한다.

## Implementation Notes

### 구현 결과

- Python 3.12 single application image; pinned uv 0.11.15, `uv sync --locked --no-dev --extra eval-gemini`. 기존 실제 Search client에 필요한 openai/anyio가 이 extra에 있으므로 사용한다. Paddle/OpenCV/pytest는 runtime에 설치하지 않는다.
- build/runtime stages를 나누어 uv/cache/build metadata를 runtime에 복사하지 않는다. 두 stage의 Python base 계열과 `/app/.venv` 경로를 맞춘다. 기존 migration runner의 파일 상대경로를 유지하기 위해 source editable install과 `/app/src`, `/app/migrations`를 함께 둔다.
- api/worker/migrate는 같은 image와 numeric `10001:10001`. PID 1 adapter가 api/worker를 `exec`하므로 SIGTERM을 직접 받는다. api는 기존 workers=1 entrypoint, worker는 기존 단일 claim loop다. Worker entrypoint의 기존 revision 로그 `unknown` 동작은 그대로다; image의 `DAESINGO_REVISION`과 API revision에는 build arg가 반영된다.
- migration adapter는 protected 파일에서 DB URL을 검증하고 기존 `--database-url-stdin` CLI에 stdin으로만 전달한다. one-shot exit code를 그대로 반환하며 retry/resume/downgrade/startup migration을 추가하지 않는다. 기존 forward-only/부분 DDL 실패 의미를 보존한다. 실패 시 원인 확인/repair 없이 재실행하지 않는다.
- `mysql healthy → migrate completed successfully → api/worker` dependency. API ready caller, worker stop grace, 네 service의 local log rotation. MySQL health는 credential 없는 TCP ping이며 초기화용 `--skip-networking` 임시 서버를 통과시키지 않는다. 인증/schema의 최종 확인은 migrate와 API ready다.
- MySQL data와 media는 project 범위의 별도 named volumes. image build 때 `/media`와 service별 temp 디렉터리를 10001 소유 0750으로 seed한다. 빈 named volume copy-up으로 소유권을 전달하고 runtime chown/chmod/루트 실행에 기대지 않는다. 기존 임의 소유 volume은 자동 보정하지 않는다.
- 모든 app config 값은 read-only bind env 파일에서 읽는다. Compose `environment`는 파일 경로뿐, MySQL은 공식 `_FILE` 경계를 쓴다. Dockerfile은 명시적 COPY와 allowlist build context로 실제 env·dump·로컬 media를 제외한다.
- `compose.yaml`은 YAML의 JSON subset이다. 표준 라이브러리만으로 source와 `docker compose config --format json` 결과를 같은 정책 검사기에 전달한다. 구조 PASS는 실행 PASS를 의미하지 않는다.

### Plan 대비 변경

Plan의 오래된 두 PR 예시 중 local migration 단계와 smoke를 이번 (a)에 포함했다. clean up→migration→ready가 (a)의 승인된 실행 경계이며 사용자 요청과 #300 승인에 따른다. (b)는 아래 backup/restore 및 필요시 검증 확장이다. Plan 자체는 다시 쓰지 않았다. Baseline은 이번 세션의 새 의미 선택 없이 이미 승인된 M4 값을 반영했다.

### 새로 고정된 implementation detail

| 항목 | 선택 · 이유 |
| --- | --- |
| app identity/media | UID/GID 10001:10001, `/media`, `/media/api-temp`, `/media/worker-temp`; 같은 mount 안에서 staging/final/temp를 사용 |
| spool | Python 기본 `/tmp`, tmpfs mount 없음. streaming upload staging은 `/media/staging`; temp root를 tmpfs로 옮기지 않음 |
| image/revision | local tag `daesingo-rt13:local`, build arg `REVISION`; registry/production immutable convention 아님 |
| logs | local driver의 B-O1 rotation. production transport/RD-13a를 닫지 않음 |
| MySQL | 8.4 계열 official image, db/user `daesingo`, host DB port 공개 없음 |
| local host port | API 기본 127.0.0.1:8000, 경로 외 비밀 config를 shell에서 받지 않음 |
| smoke/CI | opt-in local script, 일반 PR gate에 Compose smoke를 새로 넣지 않음. 기존 pytest에서 구조/negative-control 검사 |

base image tags와 apt ffmpeg는 digest/package snapshot pin이 아니므로 bit-for-bit image 재현을 보장하지 않는다. Python dependency resolution은 lock을 사용한다. production image digest/registry 정책은 RT-14다.

### Contract / Decision / Baseline 영향

- Contract 변경 없음. 기존 module 공개 경계, migration runner, API/Worker startup/ready/shutdown 의미를 변경하지 않았다.
- Decision: 새 정책 선택 없음. RD-12a 및 RD-12g local slice 승인 내용을 구현하고 RD-12 전체/production 항목은 OPEN 유지.
- Baseline: 승인된 값만 canonical Baseline §2.10에 근거/Evidence/지표/Trigger와 반영했다. `timeout=5s`는 B-H3=3s 조건에서 **DERIVED**; interval 10s/retries 3/start period 10s/stop grace 30s 숫자는 **CONSERVATIVE_DEFAULT**다. RT-13 smoke와 이후 Real E2E 결과로 재조정할 수 있다.
- graceful shutdown은 새 claim 중단과 30초 window 내 정상 종료 시도까지다. 모든 handler 완료 보장은 없으며 grace를 넘으면 kill, 기존 lease→STALE→retry로 복구한다.

### Owner 확인 포인트

실제 Linux engine에서 file UID 권한/copy-up, migration 실패 전파, upload 동일 path/bytes, baseline 간격을 유지한 강제 종료 recovery를 확인해야 한다. backup/restore와 production 절차는 후속 경계다. compose healthy를 Worker/provider/queue 상태로 확대하지 않는다.

## Local 실행

Linux container를 지원하는 Docker Compose가 필요하다. app이 읽을 runtime 파일은 repo 밖에서 **UID/GID 10001:10001, mode 0400**으로 준비한다. `.env.example`의 Runtime 주석에 있는 key를 파일에 쓰되 placeholder를 실제 값으로 바꾼다. 경로는 `/media`와 위 temp paths로 맞춘다. DB URL 비밀번호는 URL encoding하고, 같은 실제 password를 별도의 MySQL password 파일에 넣는다. Provider key는 기존 Worker bootstrap이 검증한다. 경로/비밀번호를 command line에 입력하지 않는다.

MySQL password 두 파일은 **사용할 mysql:8.4 image의 mysql numeric UID/GID** 소유, 0400으로 준비한다(`docker run --rm --entrypoint sh mysql:8.4 -c 'id -u mysql; id -g mysql'`로 확인). upstream entrypoint는 mysql 사용자로 재실행해 파일을 읽기 때문에 root 전용 파일로 두면 시작하지 못한다. 파일 UID를 맞추고 world/group read로 완화하지 않는다. Compose file bind는 uid/gid/mode를 대신 보장하지 않는다. Docker daemon이 source 경로를 bind할 수 있어야 한다.

shell에는 다음 **파일 경로만** 설정한다(실제 값은 파일에만 보관): `DAESINGO_RUNTIME_ENV_FILE`, `DAESINGO_MYSQL_PASSWORD_FILE`, `DAESINGO_MYSQL_ROOT_PASSWORD_FILE`. 선택적으로 비밀이 아닌 `DAESINGO_REVISION`, `DAESINGO_API_PORT`를 설정할 수 있다.

```sh
python scripts/check_compose.py
docker compose config --format json > /tmp/rt13-compose.json
python scripts/check_compose.py /tmp/rt13-compose.json
docker compose build --no-cache api
docker compose up -d api worker
docker compose ps --all
```

`docker compose down`은 named volumes를 보존한다. **기존 프로젝트의 volume을 지우는 명령은 실행하지 않는다.** app 파일 rotation은 파일 교체 후 container recreate이며 restart만으로 보장하지 않는다. migration이 실패했다면 api/worker를 `--no-deps`로 시작하지 않는다. schema를 보존한 채 기존 runner의 실패 조사/repair 경계를 따른다.

## 전용 acceptance smoke

```sh
sudo /absolute/path/to/python3 scripts/smoke_compose.py --evidence /absolute/private/path/rt13-smoke.json
```

이는 **Linux Docker host의 root 권한**이 있어야 보호된 임시 파일의 UID를 맞출 수 있다. application container는 계속 UID 10001이다. sudo에서 사용할 Docker context/engine을 먼저 확인한다. 실제 credential은 쓰지 않고 무작위 전용 password와 fake provider key를 만들며 외부 provider를 호출하지 않는다. 현재 Recording profile이 없는 기본 Worker의 기존 실패 경로로 command→T1/T2→view를 확인한다. 실제 provider/성공 영상 분석 E2E를 주장하지 않는다.

script는 무작위 `daesingo-rt13-smoke-<12hex>` project, 전용 image tag와 named volumes를 사용한다. 기존 project 자원 충돌을 거부하고 전체 prune을 사용하지 않는다. 실제 실행 순서:

1. CLI/daemon/Compose/host 권한 확인, MySQL UID 확인, 0400 임시 env/password 파일 생성.
2. source/resolved config 검사와 no-cache image build.
3. migrate exit 7 negative control: clean mysql에서 api/worker 시작이 차단되는지 확인 후 전용 volumes 삭제.
4. 다시 새 volumes에서 up → MySQL healthy → migrate exit 0 → api healthy; 별도 API/Worker IDs 확인.
5. synthetic ffmpeg AVI 생성, HTTP case 생성/upload/command/view. Worker와 API에서 업로드 bytes SHA256 및 상대 path 일치 확인; numeric UID/GID·same-device·spool 경로 확인.
6. test-only read-only probe mount로 COMPOSE_SMOKE handler barrier를 실행한다. 실제 기존 Worker composition/heartbeat로 RUNNING 확인→SIGKILL→기본 Worker 재생성→기본 lease/sweep/backoff를 기다려 attempt1 STALE/attempt2 FAILED(미등록 test kind) 확인. timeout/sleep baseline을 바꾸지 않는다.
7. 모든 service inspect, Config.Env/Cmd/Args/Image/history와 로그의 canary 비노출, 실제 health/grace/rotation/non-tmpfs/secret RW=false 및 named volumes 확인.
8. down(volume 보존)→up 뒤 같은 volume 이름·DB 행·media hash 확인. finally에서 이 project의 containers/network/volumes와 전용 image tag 정리, label 조회로 잔여 확인. upstream base image cache는 공유 자원이므로 삭제하지 않는다.

probe는 테스트 파일이며 application image에 넣지 않는다. smoke JSON은 stage 성공 증거와 실패 stage/type, 정리 상태만 보존하고 secret 원문/command output은 출력하지 않는다. 실패 시 성공 stage와 미실행 stage를 구분한다.

## Verification — 2026-10-27

이 절은 Docker 설치 전 초기 실행 결과를 보존한다. 설치 후 결과는 아래 재개 절을 따른다. 초기 HEAD/원격 develop `ef5806aec92307fa89fdc489b61f9fab9a1702bc`, branch `codex/rt13a-docker-compose`, index/worktree clean 확인 후 수정했다. 로컬 증거는 gitignored `.codex-scratch/rt13a/`에 보관한다.

| 검사 | 확인 결과 |
| --- | --- |
| bundle RED→GREEN | bundle/adapter 미존재 48 failed → 48 passed. 최초 temp sandbox 오류 2건은 workspace basetemp로 분리 재실행하여 RED 48 failed 확인 |
| smoke guard RED→GREEN | 미존재11 failed → guard 구현; override command·TCP init barrier·source snapshot 각RED1, build source/replica RED4 → deploy67 passed. Review P2 회귀 RED1 및 cleanup RED8 → 최종 deploy **79 passed**, skip/xfail0 |
| Compose 구조 | `python scripts/check_compose.py` PASS (정적 구조만) |
| 실제 Docker | Windows PATH/기본 설치 경로와 Ubuntu에서 Docker CLI를 확인하지 못함. smoke `docker_preflight` FAIL, 성공 stage 없음, 생성 Docker 자원/정리 대상 없음. config/build/up/inspect/persistence/recovery는 **미검증** |
| locked dependencies | `uv lock --check --offline` exit 0 (image build 또는 sync 실행의 증거는 아님) |
| 전체 pytest | **12,683 passed / 3 failed / 26 skipped / xfail 0**, exit 1. 실제 MySQL8.4.7 사용. 원본 `full-mysql.txt/json/xml` 보존 |
| mandatory MySQL subset | **1,044 passed / 1 failed / skip 0 / xfail 0** (collected/selected 1,045). 실패는 기존 중첩 gate의 900초 timeout |
| strict JSON/JUnit | `check_mysql_test_report.py full-mysql.json full-mysql.xml` exit 1: incomplete or invalid evidence. mandatory gate 성공으로 표현하지 않음 |
| API 실패 별도 확인 | 기존 process-safety 2건을 원래 5초 제한으로 별도 실행: **2 failed**. 전체 원본 실패를 단독 실행 결과로 덮어쓰지 않음 |
| boundary / Contract / workflow / diff | boundary 0위반; Contract semantic 104검사 0실패; workflow MySQL/strict/30분 및 nested900초 정책·운영진 소유4파일 불변; `git diff --check` exit0 |
| fresh reviewer | 이력 미상속 initial: P1없음/P2두 건 → TDD 수정 → **동일 reviewer 재리뷰: 잔여 P1/P2 source defect 없음**. reviewer 독립 deploy79 pass 및 cleanup main-path 재현 통과. 최초 default-temp63 pass/4 setup errors와 정상67 pass도 구분 보존 |

Docker 미실행으로 migration exit/ready/upload sharing/STALE attempt2/inspect secret/volume persistence의 실제 증거가 없으므로 PR acceptance 완료 또는 merge 준비 완료라고 판정하지 않는다. 코드/negative controls는 실행 smoke를 대체하지 않는다.

전체 실패 원본:

- `tests/api/test_process_safety.py::test_composition_failure_outranks_stalled_handler_write`
- `tests/api/test_process_safety.py::test_actual_server_cleanup_failure_exit_and_listener_release`
- `tests/common/db/integration/test_migration_gate.py::test_actual_report_rejects_each_missing_migration_check` (중첩 subprocess 900초 timeout)

위 기존 테스트와 application API/Worker/migration source는 이번 diff에서 수정하지 않았다. 실패의 역사적 원인이나 특정 OS 원인을 확정하지 않는다. timeout/sleep을 늘리거나 gate를 약화하지 않았다. 전체 실행 수집 당시 deploy61개 이후 추가한 negative/회귀와 review 수정은 최종 deploy79개 실행으로 검증했다. 전체 suite를 재실행해 성공했다고 주장하지 않는다.

처음 sandbox 전체 시도는 captured output/완료 JSON·JUnit 없이 중단했다(`full-pytest.txt`와 interruption note). 정확한 대기 시간과 원인은 계측하지 않았다. MySQL 미설정 최초 mandatory 시도 exit4도 별도 원본으로 남겼고, 이후 작업 전용 실제 MySQL로 위 전체 실행을 수행했다. 초기 boundary의 cp949 출력 오류와 UTF-8 재실행도 분리했다.

테스트 자원: Docker는 preflight 이전 차단으로 생성0. 실제 MySQL은 기존 binary를 읽어 전용 UUID datadir `/dev/shm/rt13a-a4919cd9505b4980b02713ccb6af49ee`, loopback port42921, schema `rt13a_test`를 생성했다. 종료 전 schema audit에서 예상 밖 schema1개가 있어 helper exit1(AssertionError)을 보존했다. finally에서 SHUTDOWN·server 종료·정확한 UUID datadir 삭제, Linux port closed는 별도 확인했다(`server-final.json`, `owned_root_absent=true`, connect errno111). 후속 `linux-final-audit.json`에서 소유 datadir 없음/mysqld0, `windows-final-audit.json`에서 listener0/소유 Python0을 직접 확인했다. 일시적인 shared WSL relay listener1 관측도 보존하며 공유 WSL/다른 MySQL service를 종료하지 않았다. 물리 자원 정리를 schema audit PASS로 소급하지 않는다.

### Fresh review 수정 기록

| 최초 판정 | TDD 수정 · 검증 |
| --- | --- |
| P2: normalized `entrypoint:null`을 override로 오인 | source와 canonical JSON의 absent/null은 허용하고 `[]`/빈 문자열/명시 command override는 거부한다. [공식 ShellCommand serialization](https://raw.githubusercontent.com/compose-spec/compose-go/main/types/command.go)·[Compose JSON path](https://raw.githubusercontent.com/docker/compose/main/cmd/compose/config.go)를 독립 확인했다. RED1→focused71 pass |
| P2: cleanup 단일 명령 실패 뒤 나머지 중단 및 잘못된 not_needed/원래 실패 덮어쓰기 | touched 이후 pending→FAIL부터 시작, down/containers/volumes/networks/image를 각각 best-effort 실행한다. per-operation failure type/exit code와 잔여 자원 종류만 기록하고 원래 failed_stage/type은 보존한다. 타 project image 거부 포함 RED8→focused79 pass |
| 비차단: recreate 뒤 volume assertion이 이전 snapshot 참조 | 새 container inspect snapshot을 읽도록 보완. 실제 Docker persistence 확인은 여전히 미검증 |

동일 reviewer는 수정 snapshot 해시·HEAD/index·diff를 확인하고 **deploy79개를 독립 실행해 통과**시켰다. canonical null entrypoint + build failure + cleanup down timeout의 main-path mock 재현에서도 원래 build failure 보존, 별도 cleanup FAIL/TimeoutExpired 기록, 3종 audit/image 제거 시도, canary 비노출을 확인했다. 실제 Docker 명령 실행이 아닌 mock transport 검증이다. reviewer는 disposable 파일을 정리했고 source/index/HEAD를 수정하지 않았다.

전체/MySQL suite 결과는 implementer의 직접 증거를 검토했으며 reviewer가 독립 실행했다고 표현하지 않는다. 최종 판정은 **미커밋 intermediate/draft PR 후보로 보존 가능, merge-ready/acceptance-complete/RT-13 DONE은 불가**다. 잔여 비차단 위험은 base/apt mutable 입력과 grace 안의 모든 handler 완료 비보장이다. provider 성공 분석/production/restore는 승인된 후속 경계이고 실제 Docker runtime 성질은 증거 없이 판정하지 않는다는 범위 판단을 유지한다. Worker의 기존 revision unknown 제한도 위 구현 결과에 기록했다.

최종 branch는 `codex/rt13a-docker-compose`, HEAD는 시작과 같은 `ef5806aec92307fa89fdc489b61f9fab9a1702bc`다. 미커밋·미스테이징이며 commit/push/PR/Issue 변경을 수행하지 않았다. README는 새 Compose 경로 및 코드로 확인한 media HTTP/기본 Worker 조립의 오래된 현황만 정정했다. 기술 스택·Node/Python 실행 명령은 대조 후 유지했으며 진행 정도 등 원천으로 확정할 수 없는 다른 현황은 재판정하지 않았다.

변경 후보 17개: `.dockerignore`, `.env.example`, `Dockerfile`, `README.md`, `compose.yaml`, `docker/runtime.py`, `scripts/check_compose.py`, `scripts/smoke_compose.py`, `tests/deploy/compose_probe.py`, `tests/deploy/test_compose.py`, `tests/deploy/test_runtime.py`, `tests/deploy/test_smoke_compose.py`, `docs/runtime/open-decision-register.md`, `docs/runtime/provisional-baseline-v0.1.md`, 이 Notes, `docs/runtime/runtime-implementation-log.md`, `docs/superpowers/plans/2026-10-27-rt13a-docker-compose.md`. 전체 diff/해시는 ignored `review.diff`/`manifest.json`으로 제공한다. 로그·임시 env·test DB·Python cache는 PR 제외다.

## Docker 설치 후 재개 — 2026-10-27

기존 17개 후보 파일의 SHA-256이 초기 세션 최종 manifest와 전부 일치함을 먼저 확인했다. branch/HEAD는 위와 같고 index는 비어 있었다. 시작 시 기존 Docker container/volume은 없고 기본 network 3개만 있었다. Windows `desktop-linux`와 Ubuntu WSL에서 같은 Docker Desktop Linux engine에 연결했다(Engine 29.9.2, Compose v5.6.1).

첫 실행은 resolved `docker compose config` PASS 뒤 build context sender가 기존 NTFS `.pytest_cache`의 xattr를 읽지 못해 실패했다. WSL에서 해당 디렉터리가 mode 0111이고 접근 거부임을 별도 확인했다. Dockerfile 실행 전의 host 파일 접근 오류이며 기존 파일/ACL은 수정하지 않았다. 최초 report의 clean_build FAIL과 image 미생성에 따른 cleanup image-remove FAIL도 보존했다. project container/network/volume 잔여는 없었다.

ignored 파일·secret을 제외한 추적 파일과 17개 후보의 현재 bytes를 전용 Linux 임시 사본으로 export했다. 2,188개 파일의 SHA-256을 원본과 대조했다. Git worktree/checkout/branch는 만들지 않았다. 이 동일 source의 깨끗한 Linux context에서 실제 smoke를 수행했다. 원래 NTFS context의 직접 build 성공으로 소급하지 않는다.

| 실제 Docker acceptance | 결과 |
| --- | --- |
| config / clean build | resolved config 검증 PASS, `build --no-cache api` exit 0 |
| migration negative control | migrate exit 7 → Compose up nonzero, API/Worker는 created 상태로 실행 차단 |
| 새 named volumes에서 시작 | MySQL healthy → migrate exit 0 → API healthy; API/Worker 별도 container, 동일 image |
| HTTP / media | case 생성·upload 201, command 202·view 200; 두 container의 상대 path와 bytes SHA-256 동일 |
| recovery | 실제 blocking Worker SIGKILL 후 기본 lease/sweep/backoff로 attempt 1 STALE → attempt 2 FAILED(의도적 미등록 test kind) |
| secret / 실제 설정 | 네 service inspect·Env/Cmd/Args·history·logs에서 생성 canary 비노출; application UID/GID 10001:10001, secret mount read-only, non-tmpfs, health 10s/5s/3/10s, worker grace 30s, local rotation 20m×5 |
| recreate persistence | volume 보존 down/up 후 새 container inspect, 동일 MySQL/media volume 이름·DB rows·media SHA-256 확인 |
| 최종 smoke cleanup | 전용 containers/network/volumes/image 제거, 세 label audit 잔여 0, PASS. 공유 upstream image cache는 보존 |

실행 project는 `daesingo-rt13-smoke-c807d9e3fb4e`다. 새 증거 `docker-snapshot.json`은 9 stages PASS/cleanup PASS이며 private transport journal에는 정리 전 State/exit/Health/logs/Mounts/dependency 관련 원본을 보존했다. 파일은 gitignored `.codex-scratch/rt13a-resume/`에만 있고 journal의 생성 test canary는 치환했다. 실제 production credential/provider 호출은 사용하지 않았다. 이 결과는 provider 성공 분석·restore·production 검증으로 확대하지 않는다.

이전 API 두 실패의 현재 Windows 재현은 1 passed/1 failed이며 develop export에서도 동일했다(원래 5초 제한). 관측용 child stack은 source import의 filesystem get_data/path_stat 구간을 포착했다. 관련 API 테스트·nested gate·애플리케이션 source 179개 파일은 develop과 바이트 단위로 동일하다. 관측은 현재 재현의 경계이며 과거 모든 실패의 정확한 원인을 확정하지 않는다. 초기 3 failed/strict FAIL과 별도 재현 기록은 덮어쓰지 않는다. Linux 대조 및 최종 단일 전체/strict 결과는 아래 후속 기록을 따른다.

### 이전 실패 조사와 최종 실행 환경

원본 full TXT/JSON/JUnit/result, API 재현, strict FAIL 총 6개 파일을 별도 SHA-256으로 봉인했고 재개 후에도 일치한다. Windows current/develop의 두 API 테스트는 각각 1 passed/1 failed, Linux current/develop은 각각 2 passed다. 원래 5초 제한을 유지했다. 관측용 stack은 현재 재현에서 import filesystem I/O를 포착했지만 과거 full의 `write_entered` 이후 지연까지 같은 원인으로 단정하지 않는다. timeout/sleep이나 API 종료 구현은 바꾸지 않았다.

같은 Docker MySQL 8.4.13 환경의 current/develop nested 재현은 모두 원래 900초에서 FAIL이다(pytest 측정 각 900.51초/900.61초; wrapper 시간은 별도 원본). 자식 stack에서 `test_timestamp_order_mysql.py`의 실제 migration `0003_usage.py` index DDL 응답을 기다리는 것을 확인했다. 서버 performance_schema 한 시점의 create table 6,969회/237.5189초, drop database 627회/110.4688초, alter table 1,149회/99.8578초, create index 2,300회/50.7674초를 보존했다. 반복 schema/migration 작업의 실제 비용을 관측한 것이며 이를 과거 전체 timeout의 단일 원인 또는 제품 deadlock으로 단정하지 않는다. 두 대조의 원본 traceback을 보존하고 RT-13의 새 코드 결함으로 처리하지 않았다.

최종 전체 실행은 Python 3.12.3/Linux와 실제 MySQL 8.4.7을 사용한다. 전용 `/dev/shm` test datadir이며 MySQL `innodb_flush_log_at_trx_commit=1`, `sync_binlog=1`과 원래 test timeout/sleep을 유지했다. 이는 **pytest 전용 서버**이며 실제 Compose의 non-tmpfs named-volume 구성은 변경하지 않았다. Linux 미디어 도구는 기존 shared dpkg의 interrupted 상태를 복구하지 않고 전용 폴더에 download/extract했다. 최종 전체 전 기존 stdin CLI migration 한 건만 별도 probe하여 PASS를 확인했으며 mandatory gate 성공으로 쓰지 않는다.

최종 전체는 `DAESINGO_REQUIRE_MYSQL=1`로 정확히 1회, 생성 JSON/JUnit의 strict CLI도 정확히 1회 실행하도록 시작 marker를 둔다. 별도 중복 MySQL 전체 suite는 만들지 않는다. develop targeted 진단은 별도 Docker DB에서 같은 host에 병행되므로 실행 시간을 통제된 성능 비교나 CI 시간 여유의 근거로 쓰지 않는다. 최종 환경에서 통과하더라도 앞선 Docker DB의 900초 실패나 초기 Windows 실패가 해결됐다고 소급하지 않는다. 이 조사에서 RT-13 실행 코드·테스트 원인으로 확인된 수정 대상이 없어 기존 RED→GREEN 구현을 보존했다.

### 최종 단일 전체 / mandatory gate 결과

| 검사 | 최종 직접 결과 |
| --- | --- |
| 전체 pytest **1회** | **12,678 passed / 3 failed / 33 skipped / xfail 0**, error 0, pytest 1,787.08초, exit 1. TXT/JSON/JUnit/시작 marker 보존 |
| mandatory 실제 MySQL | **8.4.7, 1,045 collected/selected 모두 passed, skip 0 / xfail 0**, 3,135 passed phases, collection error 0 |
| strict CLI **1회** | `check_mysql_test_report.py final-mysql.json final-full.xml` **PASS / exit 0**. 전체 non-MySQL 실패 3건을 전체 성공으로 판정하는 gate가 아님 |
| 기존 API 2건 | 이번 전체에서 둘 다 PASS(각 JUnit 1.487초/2.080초). 이전 Windows 실패 원본 유지 |
| 기존 nested gate | 이번 전체 부모 PASS(703.320초), 실제 자식 **1,027 passed / skip 0 / xfail 0**, JUnit 656.449초, 3,081 phases. 원래 900초 제한 유지. 앞선 current/develop Docker DB timeout은 여전히 FAIL 이력 |
| RT-13 deploy 회귀 | 이번 전체 안에서 **79 passed / skip 0 / xfail 0**. 별도 전체 반복 없음 |

전체의 새 실패는 `tests/search/test_diagnostic_cli.py::test_fixture_cli_writes_full_trace_only_to_local_artifacts`, `::test_output_failure_is_not_reported_as_not_executed`, `tests/search/test_runtime_deadline.py::test_timed_out_subprocess_is_terminated_and_reaped`다. 이는 저자가 Linux 검증 사본을 준비하면서 Git 문맥과 활성 venv의 `python` 검색 경로를 빠뜨린 오류였다. 원본 traceback은 앞의 두 건이 INVALID_INPUT/exit2, 마지막 건이 `FileNotFoundError: python`이다. 실제 Git ignore guard와 PATH 누락을 먼저 확인했고 소스를 수정하지 않았다.

원인 대조는 동일 3개 테스트만 수행했다. develop의 원래 사본 환경도 3 failed; current에서 PATH만 보완하면 CLI 2 failed/1 passed, 실제 Git의 읽기 전용 문맥만 보완하면 1 failed/CLI 2 passed였다. 둘을 보완하면 **current 3 passed, develop 3 passed**다. Git은 실제 원본 `.git`을 `GIT_DIR`로 읽고 임시 source를 `GIT_WORK_TREE`로 지정해 실제 HEAD/ignore guard를 확인했으며 `GIT_OPTIONAL_LOCKS=0`을 적용했다. 새 Git metadata/worktree/checkout을 만들거나 guard를 mock/우회하지 않았다. 해당 Search source/test 4개도 develop과 바이트 동일하다. timeout/sleep은 원래대로다.

이 짧은 원인 대조를 전체 성공으로 소급하지 않는다. 사용자 지시대로 **최종 전체 및 strict CLI를 재실행하지 않았으며, 전체 공식 결과는 3 failed**다. 33 skip은 선택형 의존성·실영상 opt-in·플랫폼/codec 조건을 포함하고 mandatory MySQL skip은 0이다. 원격 CI의 30분 시간 여유도 이번 다른 환경의 local 시간으로 확정하지 않는다. 새 동작/앱 수정은 없어 추가 제품 TDD 수정은 없으며 이전 RED→GREEN과 현재 79 회귀를 유지했다.

### 최종 자원 정리

전용 smoke project의 cleanup PASS와 별도로, targeted/full의 MySQL helper container 4개 및 익명 volume 4개를 정확한 container ID·mount event/journal로 추적했다. fixtures가 종료한 helper의 부재를 확인하고 남은 익명 volume만 각각 삭제했다. 별도 진단 Docker DB container/label 소유 named volume도 제거했다. 광역 prune이나 공유 자원 삭제는 하지 않았다.

진단 Docker DB의 정리 전 감사는 timeout 뒤 남은 schema 2개, transaction 1개, lock 0개로 **schema audit FAIL**이다. 그 전용 server/volume의 물리 정리와 구분해 보존했다. 최종 pytest용 실제 MySQL 8.4.7 감사는 system/전용 base 외 schema 없음, transaction/lock 0이었다. SHUTDOWN/server 종료 후 정확한 UUID datadir와 전용 Linux workspace를 삭제했다. canonical nested JSON/JUnit·mutation evidence는 삭제 전에 ignored 새 scratch에 보존했다.

독립 최종 audit: Docker containers 0 / volumes 0, 기본 networks 3개의 ID가 시작과 동일; native datadir/workspace 부재, 소유 process 0, Linux native connect errno111, Windows test ports48293/49683 listeners0이다. upstream image/build cache는 공유 cache로 남겼다. 초기 Windows 원본·최종 full3fail·strictPASS·원인 대조·cleanup/schema audit를 서로 다른 파일로 유지하며 scratch/RAW/JSON/JUnit/프로파일/임시 env/DB/cache는 PR 제외다.

### 동일 fresh reviewer의 최종 후속 판정

동일 reviewer가 최신 17개 manifest/diff·실행 원본·matrix·정리 증거를 읽기 전용으로 재검토했다. **새 P1/P2 없음, 추가 소스 수정 요청 없음**이다. reviewer는 이번 후속에서 테스트·strict CLI·Docker를 재실행하지 않았다. MySQL 1,045 nodes/3,135 phases와 JSON↔JUnit 누락·실패·skip0, 공식 전체 3fail, 기존 실패/환경 대조, 17개 해시와 code/test 불변, 정확한 helper 소유·cleanup/audit 구분을 직접 읽고 대조했다.

판정은 **미커밋 intermediate/draft PR 후보로 보존 가능**이며 전체 GREEN/무조건 merge-ready가 아니다. 단독 대조 PASS는 공식 전체 3FAIL을 대체하지 않고 원격 CI 성공·시간 여유는 미확인이다. 승인 Baseline 값과 Evidence 구분, RT-13(b) backup/restore·production/provider 성공 분석 제외 경계가 적절함을 확인했다. Mutable base/apt와 grace 내 모든 handler 완료 비보장 한계도 유지한다. 결과 기록만 추가했으며 실행 코드/테스트는 이 재개 동안 수정하지 않았다. branch/HEAD 유지, 빈 index, commit/push/PR/Issue 변경 없음, **IN_PROGRESS · Refs #300 (RT-13(a))**다.

## 후속 RT-13(b) 및 제외 범위

| 경계 | 남은 일 |
| --- | --- |
| RT-13(b) | local logical backup/restore 절차 완성과 **실제 restore smoke**; 필요시 migration/smoke 검증 후속 확장. migration 전 논리 backup 원칙은 #300 승인 그대로이며 기존 data migration의 운영 절차 완성은 여기서 주장하지 않음 |
| RT-13(a) 검증 | 초기 Docker 미검증은 위 설치 후 재개에서 동일 source Linux context의 실제 acceptance로 확인했다. 전체 pytest/mandatory strict 및 이전 실패 조사는 별도 결과로 판정 |
| RD-12f/h · RT-14 | production migration/deployment/post-deploy, EC2/ECR/SSM/registry/CloudWatch/log transport/production restart policy |

Issue #300은 닫지 않는다. RT-13 전체 DONE으로 표시하지 않는다. 새 GitHub Issue/comment/PR/commit/push를 만들지 않는다. 실제 env/DB dump/원본 media/로컬 증거는 PR 제외다.

## 2026-10-30 후속 — Issue #465

**IN_PROGRESS · Refs #465 · Related #460**

위 base tag/apt ffmpeg에 관한 문장은 당시 build의 이력이다. 현재 배포
toolchain 고정 방식, 공식 8.1 source/signature/checksum, image/package identity,
startup/preflight 및 일반 MP4 실제 변환 검증 근거는
[Issue #465 Implementation Notes](./issue465-mp4-toolchain.md)를 따른다.
지원 기준은 동일 build의 ffmpeg **8.1** / ffprobe **8.1**이며 버전 범위를
넓히지 않는다. 기존 strict tail/coverage와 #467 fixture는 바꾸지 않는다.
