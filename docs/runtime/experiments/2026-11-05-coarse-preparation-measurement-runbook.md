# 기존 EC2 전체15개 Coarse 준비 완료 시간 측정 — 실행 준비

**현재: Linux 신호4개·실제 systemd 임시unit7시나리오 PASS(§8). 운영Docker/snapshot/health adapter는 대역이며 실제 EC2 복구·측정·provider·제품E2E는 NOT_RUN.** 실행 허가 문서가 아니다. 원본/기존 실패 증거/보호 volume을 보존한다.

## 1. 요청·revision과 이전 결과

2026-11-05 읽기 조회한 [#452 Search 요청6634374912](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6634374912), [Recording 준비 답변6634842630](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6634842630), [PM 답변6634926335](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6634926335)를 따른다. 같은 EC2·15개 전체·Coarse270p/CRF28을 유지하고 provider0으로 준비 완료 시간을 먼저 잰다. 이 예외로 일반 운영 Search150초·Case 정책·품질 옵션을 바꾸지 않는다. 디코더 최적화는 하지 않는다.

로컬 시작점은 깨끗한 develop `d3301e912de8ff781f907dc30a7456e5c6135e7a`였고 `codex/issue452-coarse-preparation-deadline`으로 분리했다. 이전11개는 #567로 병합되어 현재 HEAD에 보존되어 있다. [#568](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/568)의 연결 duration 정밀도 수정도 포함된다. [#564](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/564)는 원격 merged지만 현재 checkout에는 없다. [#572](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/572)는 조회 시 open이었다. 이번 직접 하네스는 Case를 호출하지 않고 기존 명시적270p hook을 사용한다. 향후 두 PR을 포함한 제품 revision과 혼동하지 않는다.

이전 EC2 수치는 운영자 제공 진단 JSON과 사용자 확인 근거다(이번 서버 재조회 없음): Recording1584.173332초·425679447B·provenance/commit/새 연결 detached hash-length/strict decode PASS, runner peak1831919616B/OOM false. Coarse는 source copy1.61668768초 뒤 encode148.38342971초에서150초 deadline 실패했다. **29622320B는 중단된 출력이며 최종 media/request cap 통과·완료 크기 증거가 아니다.** provider0. 자동복구 outcome은 없었고 별도 수동복구로 운영 복귀/잠금 해제가 완료됐다. 실제 자동복구 실패 원인은 여전히 UNKNOWN이다.

### 425MB 재사용 판정

| 확인 범위 | 결과 |
| --- | --- |
| 로컬 retry568/transfer 보존물 | 파일시스템 항목327/350개 inventory에서400MB 이상 파일0개. 425679447B 재사용 파일을 찾지 못함. report 숫자는 media 파일이 아님 |
| 구현의 수명 | `recording_real_media_recheck.py`의 detached는 익명 TemporaryFile이며 finally close한다. Search 임시 디렉터리도 finally 삭제한다. `Supervisor.cleanup`은 이번 격리DB data/work volume을 제거한다. commit은 운영DB가 아닌 격리DB에 대한 검증이다 |
| 서버 수동 복사본/별도 backup | **확인 필요**. AWS/SSM·전송 금지 범위여서 조회하지 않았다. cleanup true만으로 서버 모든 위치의 부재를 주장하지 않는다 |
| 준비한 경로 | 보존된425MB를 가정한 재사용 기능은 넣지 않았다. 새 owner의 원본15개 등록→전체 resolve/materialization/연결/provenance→격리DB commit→새 연결 detached 조회/hash/strict를 한 번 재생성한 뒤 Coarse를 측정한다. 원본 재전송 필요 여부는 서버에 남은 검증된15개 복사본을 읽기 확인해 결정 |

운영자의 사전 읽기 확인에서 완성된 별도425MB 파일/DB가 발견돼도 크기만으로 채택하지 않는다. 원래 hash·duration·stream·logical scope/provenance·reader와 immutable 보존 여부를 확인한다. 현재 실행물의 재생성 경로를 임의로 우회하지 않는다. 기존 owner/volume의 재가동은 하지 않는다.

## 2. 최소 변경과 예산

실제 운영값으로 작성하는 새 package config에 아래 **세 필드**를 함께 둔다. 다른 image/inventory/운영 identity/input identity/CPU·reserve 필드는 기존 full15 runbook에 따라 실측값으로 채운다. 과거 config를 현재 승인값으로 복사하지 않는다.

```json
{
  "probe_profile": "full15-512m",
  "full_probe_mode": "coarse_270p_stop_before_send",
  "full_search_prepare_budget_ms": 900000
}
```

| 경계 | 제안/구현·근거 |
| --- | --- |
| Search 준비 | 명시적 full+270p 실험만900초. source copy/hash/probe·encode·media guard·duration probe를 포함. 150초에서 미완료였으므로 완료시간은 UNKNOWN이며900초는 단회 측정 중단선이지 예측/보장값이 아님 |
| request guard | 준비 뒤 별도 기존150초. 원래 source512MiB/media40MiB/request56MiB 유지. SDK sentinel까지 도달해도 실제 SDK body/HTTP/provider는 실행하지 않음 |
| legacy/default | 명시 필드 없으면 기존150초와 공유 deadline 유지. acceptance/10초/120초는 기존 예산. profile·mode·정수·유한 상한 불일치 거부 |
| full 자원 | 기존 runner hard3072MiB/soft2560MiB·swap0·DB512MiB/soft440·temp1280MiB·output512MiB·disk증가4GiB·host reserve≥700MiB/디스크reserve≥4GiB 유지. 기존 host 시작≥4796MiB·디스크free≥8GiB gate 유지. 425MB 실측/1.83GB peak를 전체 peak 보장으로 쓰지 않음 |
| 단계 시간 | full runner3600초 유지, 기존 host의 runner wait3630초 유지. 세션 전체 host subprocess4200초 ceiling은 DB readiness/생성/정리까지 포함한 외부 중단선. 3600초 안에 Recording+준비가 못 끝나면 실패로 중단 |
| 복구/점검창 | 정상 경로는 host4200+자식 회수20+복구900+복구 회수20=5140초다. 기존90분은 systemd 실패 경로까지 포함하지 못했다. 이제 full 시작 gate는 **10200초(170분)**: unit runtime5200+중단 상태5개×940+예비300. 실제systemd 버전/effective unit 검증 전 보수적 제안이며 성공/커널 장애 복구 보장값은 아니다. 팀 점검 합의가 이 창을 수용하지 못하면 시작하지 않는다. acceptance/10/120 사전 검증 시간은 별도이며 중단한 채 다음 창을 기다리지 않는다 |

일반 제품 E2E의 Search 실행 상한은 이번에 정하지 않았다. #564 공식은 `max(실행상한+30, min(실행상한+30+범위길이×2,3600))`이며1584.173332초·기존150초를 대입하면3348.346664초다(계산값). 현재 checkout의 Case는 그 변경 전이다. 이 직접 측정은 Case를 호출하지 않으므로 실험900초가 Case에 전파되지 않는다. 이후 실제 E2E 상한은 실측 Recording/준비/전송/provider 시간을 분리해 PM·Search·Case가 결정하고,60분 및 Runtime 경계와 다시 대조한다.

## 3. 측정값·송신 차단

`full/recording.private.json`에 `search_prepare_completed`, `search_prepare_wall_sec`, `search_media_bytes`, `search_media_duration_sec`, `coarse_output`을 남긴다. 완료시간은 MediaPreparer가 encode 종료+기존 media guard+duration probe를 마치고 yield한 순간이다. 실패하면 완료값 대신 `search_prepare_failed_elapsed_sec`가 남는다. 상세 frame 검사·request guard 시간은 events의 별도 단계를 함께 본다.

`coarse_output`의 stream/format duration/frame PTS·origin 시작/끝·playback_speed를 확인한다. Coarse는 기존 fps/setpts로 느리게 재생하므로 출력 duration을 원본1584.173332초와 무조건 같다고 검사하지 않는다. `search_prepare_peak_sampled_cgroup_bytes`는0.2초 샘플 최대이며 실제 peak 보장은 아니다. 기존 cgroup peak/CPU observer·OOM events·runner/DB/current/상위cgroup·디스크/temp를 함께 보존한다.

기존 internal network·DB 외 socket/HTTP 차단·credential 미주입·SDK sentinel을 그대로 사용한다. `request_guard=PASS_STOP_BEFORE_SEND`, `sdk_entry_count=1`, provider0·HTTP/SDK body NOT_RUN을 모두 확인한다. sentinel1은 실제 SDK 호출1이 아니다. media/request guard 실패나900초 소진이면 PASS로 바꾸지 않는다. 완성 media가 guard에서 거부된 경우도 최종 E2E 성공이 아니다.

## 4. 터미널과 분리한 복구

scratch 후보의 AST 대역 검사를 새 evidence로 반복했다. 독립 recovery stdio까지 요구하는 checker에서 원래 wrapper0/24, 후보24/24였다. 이 결과는 실제 host body/복구 명령을 대역으로 바꾼 검사다. 닫힌 owner에 결속된 후보를 서버에서 그대로 쓰지 않는다.

새 `recording_probe_session.py`는 현재 package hash·새 owner·operation lock·snapshot·유효 승인·직전 단계 PASS를 검사한다. 자식은 stdin null·역할별 exclusive 파일 stdout/stderr·유한 wait를 사용한다. 로그 open 실패 시 devnull로라도 복구를 시도하고 outcome 기록은 복구 뒤 수행한다. 로그 파일명은 재사용하지 않는다. 출력 write/flush/closed 오류는 progress 경계를 벗어나지 않고 broken stdout의 종료시 재flush도 피한다.

TERM/INT 때 host process group을 종료·회수한 뒤 finally 복구한다. POSIX 자식 회수 중 두 신호를 block해 반복 신호가 wait/reap를 끊지 않게 한다. 실제 child PID/start ticks가 살아 있으면 restore는 운영 복귀를 거부한다. systemd unit은 파일 stdio·Restart=no·RuntimeMaxSec5200·TimeoutStopSec940·KillMode=control-group과 **별도 ExecStopPost restore**를 포함한다. ExecStopPost는 시작/실행 실패도 다루는 별도 경로다([공식 문서](https://www.freedesktop.org/software/systemd/man/256/systemd.service.html)). 실제 설치 버전/구문/동작은 운영 전 검증해야 한다.

inline과 ExecStopPost는 같은 immutable `recovery-window.private.json`의 **누적900초**를 공유하며 자동 연장하지 않는다. 복구는 정확한 full 소유 자원만 정리하고 기존mysql→api→worker ID를 복귀한다. worker-status·API ready200·docker/caddy/mount active·release/config/schema/보호 파일/서비스 identity를 확인한 뒤 receipt를 쓰고 exact owned lock만 해제한다. receipt 후 crash도 재진입하여 readiness를 재검사하고 잠금 해제를 마친다. snapshot 불일치/추가 lock 파일/미확인 자원/복구 실패 시 잠금을 유지한다. 복구 cleanup 로그는 새 디렉터리에 남겨 기존 실패 로그를 덮어쓰지 않는다.

SIGKILL/OS·systemd 장애/디스크 쓰기 실패를 finally만으로 보장하지 않는다. ExecStopPost도 실행 못 한 호스트 장애는 독립 운영자 복구가 필요하다. 새 경로가 이전 EC2 자동복구의 실제 원인을 해결했다고 주장하지 않는다.

## 5. 로컬 재현·검증

위치는 `C:\ktc4-chonnam-2`. 매번 새 scratch 경로를 사용한다.

```powershell
.venv\Scripts\python.exe -B -X utf8 -m pytest tests/runtime/test_recording_coarse_measurement.py `
  tests/runtime/test_recording_full_input.py tests/runtime/test_real_media_recheck.py `
  tests/runtime/test_recording_ec2_probe.py tests/runtime/test_recording_probe_budget.py `
  tests/runtime/test_recording_cpu_quota_supervisor.py tests/runtime/test_recording_cpu_quota_probe.py `
  tests/runtime/test_capacity_probe.py -q -p no:cacheprovider --basetemp $NewTemp --junitxml $NewReport
.venv\Scripts\python.exe -B -X utf8 -m ruff check scripts/recording_probe_session.py scripts/recording_real_media_recheck.py scripts/recording_ec2_host.py scripts/recording_ec2_entry.py scripts/recording_ec2_package.py tests/runtime/test_recording_coarse_measurement.py
.venv\Scripts\python.exe -B -X utf8 scripts/check_boundaries.py
.venv\Scripts\python.exe -B -X utf8 scripts/check_contract_fixtures.py
git diff --check
```

기대 출력: focused 실패0, Windows에서는 새 Linux 전용4개만 skip, ruff/경계/계약/diff exit0. 실패시 새 log를 보존하고 해당 control만 진단한다. 전체 비-MySQL 회귀를 반복하지 않는다.

### 이번 검증 상태

| 검사 | 판정 |
| --- | --- |
| Windows focused | **186 PASS / 새 Linux 전용4 SKIP,18.77초**. 새파일23PASS/4SKIP+기존관련163PASS. 전체 회귀가 아니며 기존 전체14431PASS/22FAIL/26SKIP를 PASS로 바꾸지 않음 |
| 같은151초 준비 대조 | 기본150초 DeadlineExceeded,900초 완료/request150초 분리·hook 복원 PASS. 실제151초 영상 처리가 아닌 clock/MediaPreparer 대역 검증 |
| 자식/복구 controls | Windows 실제 자식의 정상/실패/timeout·로그open 실패,출력 오류,서비스 대역의 exact 복귀/identity 거부/readiness 실패/extra lock/재진입,공유 복구창·unit 인자 PASS. 실제 운영서비스 복구가 아님 |
| 실제 Linux pipe/SIGHUP/TERM/반복TERM | **NOT_RUN_RESOURCE_GATE**. 기존 시작RAM3149922304B/free6442450944B에 대해 관측RAM3146416128B/free4502020096B. 기준 변경·보존물 삭제·다른 예산 우회 없음. 새4개 control은 Windows에서 플랫폼 조건으로 skip |
| 실제 systemd ExecStopPost/실제 Docker 복구 | **NOT_RUN**. Linux controls 통과 후에도 승인된 같은 구성의 격리환경에서 unit 중단/강제종료/복구 검증 필요 |
| 원본15개 | **PASS_INPUT_AUDIT**. hash/size/mtime/VIDEO/metadata,1584.173332초·1771439266B. 촬영 연속성UNKNOWN |
| package | 직전270파일 build/unpack/verify PASS(당시 source).170분 gate 교정 후 재build는 NOT_RUN. 운영identity/image 없는 실행 불가 구조검증물과 이전 실패log 모두 보존 |
| EC2 준비시간/최종크기/실제메모리·provider/E2E/READY/download | **NOT_RUN** |

Ruff·경계/계약104개·diff 검사 PASS. 직전5400초 admission 버전 package270파일의 manifest hash는 `a59821750c9c3b6cdbd9bfb98e683eaacf1d64d2a23330936a093316c2d67751`이며 실행 불가 구조검증물이다. 이번10200초 admission 수정 후 현재 source와 이 package는 다르며, 디스크 여유가 부족해 재build하지 않았다. 다음 실제 사용 전 새 package/hash/검토/검증이 필요하다. 원본 audit·package·JUnit·준비 gate·이전wrapper 대역 대조·RED/GREEN 로그·GitHub 읽기 snapshot은 `.codex-scratch/coarse-deadline-local-20261105/`에 보존했다.

독립 fresh review의 운영root 전달 누락과 반복TERM 자식 회수 지적을 각각 RED→GREEN으로 처리했다. 문서의 사전검증/중단 순서 지적도 수정하고 같은owner의 다른stage가 실행 중이면 운영복귀를 거부하는 control을 RED→GREEN으로 보완했다. 같은 reviewer가 수정과 추가 확정결함 없음을 확인했다. POSIX 신호 control은 미실행이므로 대역 PASS로 실제 Linux/EC2 복구를 입증하지 않는다. index는 비어 있고 commit/push/게시는 하지 않았다.

## 6. 운영자 실행 순서 — 이번에는 실행 금지

1. 먼저 기존 Linux 자원 gate를 충족하는 승인된 환경에서 새 controls29개(그중 실제 신호4개)와 필요한 관련 controls를 검증한다. native subprocess 검사에서도 운영서비스는 대역이며, 실제 systemd/owned Docker 복구는 별도 격리 검증이 필요하다. 이전425MB 보존 여부는 읽기 조사로 먼저 확정하고 존재를 가정하지 않는다.
2. 팀 점검 창·복구 담당자·새 미사용owner·실제 revision/image/inventory/reader·schema/rollback·원래 서비스snapshot을 확인한다. 검증된15개 복사본이 남았다면 hash/stat/manifest 재대조 후 재전송을 생략할 수 있다. 없으면 입력 staging을 별도 승인받는다. 보호volume3개·공유image/cache를 변경하지 않는다.
3. 실제값으로 config를 작성하고 `python scripts/recording_ec2_package.py build --repo . --config "$PROBE_CONFIG" --output "$NEW_PACKAGE"`. manifest hash를 별도 검토한다. 전송/전개는 별도 승인 대상이다. 이 단계에서 부하/사전검증을 시작하지 않는다. 기존120초/전회 Recording425MB PASS를 새 실행물의 PASS로 쓰지 않는다.
4. Linux root에서 기존 full15 runbook의 `OWNER`·`PROBE_HOME`·`PROBE_MANIFEST_SHA256`·`OPS_ROOT`를 실제 확인값으로 설정한다. 닫힌owner/state/복구후보를 재사용하지 않는다. 새 unit을 **서비스 중단 전** 생성·구문 확인한다.

```sh
NEW_UNIT=/run/systemd/system/${OWNER}-coarse-prepare.service
test ! -e "$NEW_UNIT" || exit 1
python3 -B "$PROBE_HOME/source/scripts/recording_probe_session.py" unit \
  --home "$PROBE_HOME" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --operation-root "$OPS_ROOT" > "$NEW_UNIT"
chmod 600 "$NEW_UNIT"
systemd-analyze verify "$NEW_UNIT"
systemctl daemon-reload
```

5. 기존 exact snapshot/lock/ingress·writer·job0·deployment/backup 통제·원래 서비스 중단·자원 gate를 먼저 지킨다. 그 후 승인된 기존 단계별 감독/독립 복구 절차로 새 package의 acceptance→10초→120초를 새owner에서 각1회 검증한다(각 창에 해당 단계와 복구 여유를 별도 확보). 실패하면 full 금지이며 해당 host 종료·정확한 stage 소유 자원 정리 후 즉시 독립 복구한다. 아직 다른 qualification 자원이 실행 중이면 새 restore도 운영 시작을 거부하므로 기존 stage 정리 절차를 먼저 수행한다. 선행검증을 끝냈어도 full 시작시 최소10200초와 독립 복구 담당/접근 수단이 **다시** 남아 있어야 한다. 부족하면 부하를 시작하지 않고 원래 서비스로 복귀하고 새 점검창을 잡는다.

```sh
systemctl start --no-block "${OWNER}-coarse-prepare.service"
systemctl show "${OWNER}-coarse-prepare.service" -p ActiveState -p SubState -p Result -p ExecMainStatus
```

SSH/terminal과 stdin/stdout을 공유하지 않는다. 관측 연결이 끊기면 unit에 재접속해 상태와 보호 로그를 읽는다. `--pipe`나 이전 wrapper 직접실행으로 대체하지 않는다.

6. 기대값은 full-result PASS/cleanup true, `search_prepare_completed=true`,최종media/duration·caps/guard PASS_STOP_BEFORE_SEND,provider0,session outcome의 host_passed/original_recovered true,services-restored receipt의 manifest/owner 일치,원래 서비스ready/identity 일치,operation.lock 해제다. unit start 성공만으로 측정/복구 PASS라 하지 않는다. main 실패 후 ExecStopPost가 복구했다면 main 실패와 복구 성공을 별도로 기록한다.
7. 시간/자원/identity/approval/cap/egress 이상이면 이번 unit만 `systemctl stop "${OWNER}-coarse-prepare.service"`. 독립 복구 뒤에도 불명확하면 잠금을 수동 삭제하지 않고 담당자에게 인계한다. 전체/다른owner/보호volume에 대한 stop/prune/rm은 금지한다.
8. 자동 복구창이 남아 있을 때 독립 복구는 다음과 같다. **같은 unit의 ExecStopPost와 기존 restore가 모두 종료됐고, unit/cgroup에 host가 남지 않았는지 먼저 확인한다.** 동시 복구를 시작하지 않는다.

```sh
timeout 910 python3 -B "$PROBE_HOME/source/scripts/recording_probe_session.py" restore \
  --home "$PROBE_HOME" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --operation-root "$OPS_ROOT"
```

900초 창 소진시 자동 재시도하지 않는다. 담당자가 상태·종료된host·원래identity를 확인하고 **새 최대900초 수동 복구창1회**를 명시 승인한 후에만 위 restore에 `--manual-recovery-id "$MANUAL_RECOVERY_ID"`를 붙인다(새16자리hex 실제값). 기존window/실패receipt를 삭제해 연장하지 않는다. 실패하면 잠금 유지·인계한다.

9. 이전425MB Recording 성공/새 Coarse 측정/실제provider/E2E를 구분해 보고한다. Coarse 완료시간만으로 PM의 최종Search 상한이나 일반 장시간 지원을 확정하지 않는다. 실제26분 E2E·Package READY·다운로드는 측정 이후에도 별도다.


## 7. 실제 Linux 복구 검증 후속 — 자원 gate 미달

이번 후속에서도 실제 Linux 부하/프로세스·unit 종료 검증은 시작하지 않았다. 시작 기준 RAM3149922304B·디스크6442450944B에 대해 기록한 마지막 관측은 RAM2583277568B·디스크4343001088B다. 부족분은 각각566644736B·2099449856B이며 값은 관측 순간의 수치다. 작업 소유 실행 중 Python/ffmpeg/ffprobe 프로세스0·container0·임시volume0, 보호volume3개만 존재했다. 종료/삭제/압축/전송/공유cache 정리 없이 조사만 했다.

현재 작업 scratch 하위 디렉터리의 합계 논리크기는11966486B다. pytest 합성 임시파일은 목록만 남겼으며 RED/GREEN 재현 자료도 보존한다. package·input audit는 보호 증거다. 파일 논리크기는 NTFS 실제 회수량이 아니며, 삭제 없는 회수 가능량으로 확인된 값은0B다. 공유Docker/WSL·다른 작업을 멈춰 RAM을 만들지 않았다.

| 요청 경로 | 이번 판정 |
| --- | --- |
| Linux 정상 종료/실행 실패/출력 연결 종료/감독 종료 | **NOT_RUN_RESOURCE_GATE** |
| 실제 자식 부하 회수·finally·ExecStopPost | **NOT_RUN_RESOURCE_GATE** |
| 실제 복구 중복 실행·복구 실패 잠금 보존 | **NOT_RUN_RESOURCE_GATE**. 이전 Windows 서비스 대역 검증과 구분 |
| 점검창 교정 control | **PASS 5개**.6000초/8000초 창 거부,11000초 허용,unit 생성/공유900초 복구창. 새 RED2→GREEN과 Ruff PASS. 이 검사만 실행하고 이전 전체 focused/비MySQL 회귀는 반복하지 않음 |

### 점검창 산술 재확인

- runner3600초 안에 Recording 재생성·DB commit/새 연결 조회/strict·Coarse 준비900초·request guard150초·나머지 runner 작업이 들어간다. 따라서 준비와 guard를 모두 소진하면 Recording/DB/기타에 남는 것은2550초이며, 이것은 완료 보장/별도 배정값이 아니다. 초과하면 실패 중단한다.
- host4200초는 runner wait3630·DB readiness120·정리60 뒤390초를 초기화/검사 등 나머지 작업에 남긴다. 이것도 모두 완료한다는 보장 대신 외부 중단선이다.
- 정상 host+inline 복구는 최대4200+20+900+20=5140초로 unit runtime5200초 안에 든다. 다만 이 합만으로 전체 실패 경로의 점검창을 정하면 안 된다.
- 보수적 systemd v256 기본 terminate 상태 경로는 stop TERM→stop KILL→stop-post→final TERM→final KILL이다. 각940초 timer를 포함하면5200+5×940=9900초,예비300초까지10200초(170분)다. ExecStopPost900초 복구는 stop-post940초 안에 포함되어 추가 이중 합산하지 않는다. inline/ExecStopPost의 shared900초 창도 자동 연장하지 않는다. [공식 timeout 설명](https://www.freedesktop.org/software/systemd/man/256/systemd.service.html)과 [v256 상태 전이 구현](https://github.com/systemd/systemd/blob/v256/src/core/service.c)을 확인했다.

이는 점검창의 보수적 회계이며 현재 EC2 설치 버전/override 확인이나 OS 장애 복구 보장이 아니다. 부하 시작 전 실제버전·effective unit의 failure mode/추가명령/타이머를 대조하고 달라지면 재계산한다.170분을 확보할 수 없다면 시작하지 않는다. 줄이기 위해 운영설정·Case·Search 예산을 바꾸거나 자원 gate를 완화하지 않는다. 사전 acceptance/10/120 창과 수동 복구 새 승인창은 별도다.

### 최신 develop 읽기 비교

조회한 develop을 `a6c975f5d2f5418aabbe4a66b14a742a5424ddbe`로 고정해 현재 HEAD `d3301e912de8ff781f907dc30a7456e5c6135e7a`와 비교했다:20커밋 ahead/0behind·25파일 변경. fetch/pull/merge/reset은 하지 않았다.

| 변경 | 실행물 영향 |
| --- | --- |
| Case domain 대기 | #564의 범위×2 준비 여유와3600초 상한이 최신develop에 존재. 현재HEAD는 이전 공식이다. 실제E2E의 대기/late 반영 조건에 영향. 직접 격리 하네스는Case 미호출 |
| Case view/계약 | case-view/v1.11·Package plate_image_ref 추가. 이후Package/UI E2E와 제품 package의 source identity에 영향 |
| Web 지도/화면·관련tests | 직접 Recording→Coarse 측정 경로는 미사용. 제품 브라우저 E2E는 별도 검토 |
| MLAPI 공식입력 문서 | 선택 모델/근거·미확정 외부 정책 정리. 문서 완료를provider 상한/E2E 보장으로 해석하지 않음 |
| Recording/Search/하네스/lock·dependency/배포·migration | 이번 pinned25파일 비교에는 변경 없음. 자동 병합 없이 현재 실행물의제품revision을 유지 |

최신develop을 나중에 반영하면 src Case 파일도 package allowlist에 포함되므로 새revision/hash·필요한회귀 검증이 필요하다. 비교 JSON·관련파일diff·자원/소유 임시물목록·RED/GREEN·JUnit은 `.codex-scratch/linux-recovery-followup-20261105/`에 보존한다. 이전 실패/원본/보호volume을 건드리지 않았으며 이번에도 AWS·서버조회·전송·서비스중단·실제영상/provider·배포·commit/push/게시 없음.


## 8. 자원 확보 뒤 실제 Linux 무미디어 복구 검증

이 절은 §7의 gate 미달 이후 실행한 별도 검증이다. 로컬시작전 RAM6534922240B·C:free10387951616B로 기존3149922304B/6442450944B 시작 기준을 충족했다. Linux는 기존 Ubuntu WSL2의 systemd255.4-1ubuntu8.18·Python3.12이며 추가설치·이미지build/pull은 없다. 원본/DB/보호volume/실제provider는 연결하지 않았다.

### 170분 산식 선행 확인

unit의 유효값은 Type=exec,RuntimeMax5200초,TimeoutStop940초,StopFailureMode=terminate,SendSIGKILL=yes,KillSignal=TERM,FinalKillSignal=KILL,Restart=no,RuntimeRandomizedExtra0이었다. drop-in은 없고 생성 unit에 ExecStartPre/ExecStartPost/ExecStop 추가 명령은 없다. watchdog은 systemd255에서 infinity로 표시되는 비활성 상태다. `service_start_watchdog`의 timestamp_is_set 판정은0/infinity를 비활성으로 처리한다([v255 코드](https://github.com/systemd/systemd/blob/v255/src/core/service.c), [시간 판정](https://github.com/systemd/systemd/blob/v255/src/basic/time-util.h)). 텍스트 출력에서 빈 Exec 배열이 생략되는 부가진단은 성공 근거를 확보하지 못했으며, 명령 부재는 생성 unit과 drop-in 부재로 대조했다. 이 출력 진단의 예상값 오류는 하네스 결함/timeout 변경으로 정산하지 않았다.

- 다섯940초는 **stop TERM→stop KILL→stop-post→final TERM→final KILL** 순서의 서로 다른 상태 timer다. 프로세스가 사라지지 않고 각 timer가 소진될 때 순차 진입할 수 있다. 정상 종료/복구에서는 대부분 생략된다. 실제로940초를5번 기다린 실측이 아니며, 제거 불가능한 커널 프로세스는 주입하지 않았다.
- unit runtime5200초 안에 host4200초·자식회수20초·inline 복구900초·회수20초가 들어가므로 이를5200에 다시 더하지 않는다. ExecStopPost의900초 복구도 stop-post940초 안에 포함되므로 추가로 더하지 않는다. inline/post의 공유900초 창은 그대로다.
- 기본 startup90초는 Type=exec의 시작/실행 전 단계다. 실제 부하 admission은 Python 진입과 bindings 검증 후 **남은 승인시각을 다시 검사**하므로 이미 지난 startup을 그 시점의 잔여10200초에 다시 더하지 않는다. 시작 실패 경로의90+5×940=4790초도 running 경로9900초보다 짧다.
- 따라서 admission 시점의 보수적 합계5200+5×940+300=10200초(170분)를 유지한다. 타이머/안전 기준/실험900초/운영 Search150초/Case 정책은 변경하지 않았다. 실제 EC2의 버전/override는 이번 확인 범위가 아니다.

### 실제 검증 범위와 결과

기존 native 신호 테스트4개만 실행했다: closed pipe/SIGHUP/TERM/반복TERM **4 PASS,7.29초**. 기존 fixture의2/3초 예산은 변경하지 않았으며 실험/실제unit timeout과 구분한다. 전체 pytest나 이전 Windows controls를 반복하지 않았다.

실제 systemd에서는 새 task-owned slice와 임시 unit을 사용했다. session/restore는 현재 모듈의 실제 코드를 사용하고 원래 서비스 역할은 작은 Python 대기 프로세스의 실제 unit3개로 구성했다. **Docker transport·operational snapshot·health gate·frozen package binding은 합성 fixture/double**이다. 실제운영 서비스/실제Docker 복구를 검증한 것은 아니다. unit의 timeout/kill/restart/file stdio는 생성값 그대로 두었다. 네트워크 격리·AF_UNIX만 허용·source read-only·사용자원본 접근차단을 추가했고 전체 slice hard1280MiB/soft1100MiB·swap0·CPU2·pids128을 적용했다. 기존 자원 기준을 낮추지 않았다.

| 시나리오 | 관측·판정 |
| --- | --- |
| 정상 종료 | finally restore와ExecStopPost restore 모두 실행·복구receipt·잠금해제 **PASS** |
| host 실행 실패 | host 비정상종료 뒤 남은 합성부하 정리·복구 **PASS**. main 실패상태 자체는 유지 |
| 관측 출력 연결 종료 | journal 관측 client 연결종료 후 unit 계속 실행·복구 **PASS**. broken stdout 자체는 위 native closed-pipe 검사로 별도 검증 |
| 감독 TERM | 실제 main PID에 TERM 주입, 자식회수·finally+ExecStopPost **PASS**. main은 중단 실패로 정산 |
| 감독 SIGKILL | finally outcome이 없는 상태에서 cgroup 자식제거 후 **ExecStopPost만으로 복구 PASS**. main의signal 실패를 PASS로 덮지 않음 |
| 중복 복구 | inline→ExecStopPost→추가 순차 restore 재진입,서비스 추가start 없음·잠금재해제 오류 없음 **PASS**. 동시 수동복구 경합은 NOT_RUN |
| 복구 실패 | readiness 실패를 주입해 실제 restore가 실패하고receipt 없음·잠금 유지 **PASS**. 복구 자체는FAIL/REVIEW_REQUIRED이며 성공으로 보고하지 않음 |

7시나리오와 native4개 묶음은81.7537초에 완료했다(실영상 준비 성능 수치가 아님). slice peak59797504B·pids peak6·OOM0. 정확한 PID/start identity18개를 사후 확인해 잔존0개,임시unit/slice 잔존0개·정리오류0개다. unit파일은 등록한 새이름/내용hash를 확인해 해당 파일만 정리했다. 합성실패·source·outcome/receipt·로그는 보존했다. Docker 컨테이너는 만들지 않았으며 보호volume3개의 목록/owner label은 유지했다.

첫 시도는 pytest가 read-only /tmp에서 임시파일을 만들 수 없어 수집 전 종료됐다. 같은 제한을 유지하고 TMPDIR만 task-owned 쓰기 경로로 지정한 새시도에서 검증했다. 첫 실패 기록은 attempt1에 보존했다. 제품하네스·기존 테스트파일의hash는 검증 전후 동일하다. 새하네스 기능이나 timeout 변경은 없다.

### 근거·남은 범위

실제 실행 명령은 로컬 Windows에서 `wsl -d Ubuntu -u root -- /usr/bin/python3 -B /mnt/c/ktc4-chonnam-2/.codex-scratch/linux-recovery-actual-20261105/linux_controller_attempt2.py`였다. 이 스크립트는 이미 닫힌 시도이며 그대로 재사용하지 않는다. 로컬 증거는 `linux-recovery-actual-20261105/attempt2`의 native JUnit,시나리오별JSON/evidence,systemd 유효설정,slice자원,post-cleanup에 있다. 안전한 새 실행은 새owner/evidence와 기존 gate를 먼저 요구한다.

실제운영Docker/SQL/HTTP health·운영snapshot/reader·frozen package 전송/배포 binding·실제 EC2 복구·동시 수동복구·타이머 자연소진/커널 hang·실영상26분/Coarse/provider/Case/Package READY/다운로드는 **NOT_RUN**이다. 이 경계와 이전 자동복구 원인UNKNOWN을 유지한다. AWS/EC2 접속·실영상·provider·제품배포·commit/push는 하지 않았다.
