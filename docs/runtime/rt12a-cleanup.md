> 2026-10-22 기록은 보존 이력입니다. 현재 후속 수정·PR 후보·검증은 문서 끝의 2026-10-23 절을 참조하세요.

# RT-12(a) cleanup 구현·독립 리뷰 인계

**Status: IN_PROGRESS · Refs #299 (RT-12(a)) · PR/merge SHA pending**

이 문서는 이번 구현자가 직접 실행한 증거와 남은 검증을 구분한다. 독립
reviewer/subagent를 호출하지 않았고, 이 문서를 독립 리뷰 결과로 취급하지 않는다.
Contract·Accepted Decision·Baseline 의미/값은 변경하지 않는다.

## 기준과 변경 파일

시작 확인: `codex/rt12a-cleanup`, HEAD와 로컬 `origin/develop` 모두
`1f830afeac93309e9ef9c8eb90fcfaced0f97ae0`, worktree/index clean.
[Issue #299](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/299)는 원격에서
직접 읽었다. Plan RT-12/§9/§12.8과 Baseline B-C1–B-C4/§9 Cleanup을 우선한다.
이번 세션은 원격 ref를 fetch하거나 remote branch를 갱신하지 않았다.

PR 후보 전체 목록:

| 구분 | 파일 |
| --- | --- |
| 제품 | `src/daesingo/common/storage/__init__.py` |
| 제품 | `src/daesingo/common/storage/_filesystem.py` |
| 제품 | `src/daesingo/common/storage/cleanup.py` |
| 제품 | `src/daesingo/common/storage/media.py` |
| 제품 | `src/daesingo/api/app.py` |
| 제품 | `src/daesingo/api/composition.py` |
| 제품 | `src/daesingo/api/upload.py` |
| 제품 | `src/daesingo/common/jobs/worker_loop.py` |
| 제품 | `src/daesingo/worker/composition.py` |
| 문서 | `src/daesingo/common/README.md` |
| 문서 | `src/daesingo/api/README.md` |
| 문서 | `src/daesingo/worker/README.md` |
| 테스트 | `tests/common/storage/test_cleanup.py` |
| 테스트 | `tests/common/storage/test_cleanup_lifecycle.py` |
| 테스트 | `tests/common/storage/test_media.py` |
| 테스트 | `tests/api/test_api_cleanup.py` |
| 테스트 | `tests/worker/test_worker_cleanup.py` |
| 문서 | 이 파일 |
| 문서 | `docs/runtime/runtime-implementation-log.md` |
| 문서 | `docs/superpowers/plans/2026-10-22-rt12a-cleanup.md` |

`.codex-scratch/rt12a-20261022/**`의 RAW 출력·JSON/JUnit·runner·진단·임시 root는
모두 제외한다. 기존 다른 작업의 scratch/RAW/테스트 자원은 정리하지 않는다.

## 구현 경계와 흐름

- `configured_cleanup`은 API의 `media_root/staging`과 service별 명시적
  `temp_root`만 조립한다. `source` publish root 및 하위 경로를 temp target으로
  주입하는 구성은 시작 조립에서 거부한다. publish 등록 조회/DB 접근은 없다.
- 기존 CleanupSettings의 나이/주기를 그대로 소비한다. 기본값은 staging/temp
  3600초, startup 1회 + scan 완료 뒤 3600초 interruptible wait이다. 나이가
  경계와 같으면 보존하고, mtime이 cutoff보다 오래된 대상만 삭제한다.
- API lifespan은 startup scan 후 요청을 받고 종료 때 cleanup thread를 join한
  뒤 기존 readiness/engine을 닫는다. Worker는 cleanup startup → 기존 sweep
  startup → claim 순서이며, startup/claim 실패에서도 sweep과 cleanup을 모두
  닫는다. 원래 실패가 secondary close 실패로 바뀌지 않게 한다.
- upload는 shared filesystem lease 획득 → staging 생성/수신 → fsync → close →
  publish까지 보호한다. publish 뒤 기존 DB 등록 순서는 그대로다. abort는
  row 없는 staging을 남기되 descriptor/lease를 반환한다. asyncio 취소가
  파일 작업 await를 끊어도 소유 thread 작업이 끝난 후 descriptor를 닫는다.
- producer shared lease는 서로 공존한다. scanner는 exclusive lease를
  nonblocking으로 시도하므로 활성 producer가 있으면 root 전체를 보수적으로
  미룬다. thread 내 중복 scan과 다른 process의 scan도 같은 lock으로 배제한다.
  persistent `.runtime-cleanup-{staging,temp}.lock`은 지우거나 교체하지 않는다.
  process kill 뒤에는 OS가 lock을 반환하므로 다음 aged scan이 회수할 수 있다.
- staging의 기존 `upload-` + Python tempfile suffix 파일만, temp의 기존
  `recording-analysis-`/`recording-chain-` + suffix 디렉터리만 진입한다. 현재
  Python tempfile 구현의 suffix는 `[a-z0-9_]{8}`로 직접 확인했다. prefix만
  비슷한 일반 파일/디렉터리·temp root의 일반 파일은 보존한다.
- tree의 각 파일과 디렉터리에 나이를 적용하고, 변경된 identity/mtime/size,
  새로 생긴 자식, 사라진 파일, hardlink, symlink/reparse point를 보수적으로
  처리한다. 디렉터리 나이는 진입 전에 검사한다. 자신의 자식 unlink로 바뀐
  디렉터리 mtime은 삭제 작업의 일부로 처리하며, 비어 있는 기존 디렉터리만
  제거한다. count는 제거한 일반 파일 수이며 빈 디렉터리를 세지 않는다.
- Windows는 ancestor를 delete sharing 없이 pin하고 leaf를 공유하지 않는
  handle로 열어 재검증 후 handle로 삭제한다. 열린 reader의 delete-pending을
  성공으로 집계하지 않는다. POSIX는 dir fd + O_NOFOLLOW/openat/unlinkat와
  cooperating root lease를 사용한다. 재귀 pathname rmtree는 사용하지 않는다.
- cleanup catalog는 `storage.cleanup.{staging,temp}.{count,bytes,failed_count}`다.
  기존 logger의 정수 `count` 필드로 각 값을 기록한다. empty context에서
  제출하므로 request/execution ID가 상속되지 않는다. API는 기존 bounded
  ApiEvents queue, Worker는 기존 best-effort structured logger를 재사용한다.

## temp producer 연결의 정확한 범위

API composition과 WorkerLoop에 service별 `MediaRoot`를 주입했다.
`media.materializer(existing_factory, ...)`는 기존 constructor의 `temp_root`를
명시적으로 주입하고 기존 동기 method 호출 전체를 lease로 감싼다. exception과
BaseException 취소에서도 반환하며, domain 코드/공개 surface는 수정하지 않는다.

**현재 기본 API RecordingService에는 media materializer가 없고 Worker
entrypoint의 실제 handler registry도 비어 있다.** 이번 구현은 profile/encoding
숫자나 RT-10 실제 handler를 만들지 않는다. 그러므로 기본 API/Worker가 실제
ffmpeg temp를 생성한 뒤 cleanup과 경합하는 E2E를 구현했다고 주장하지 않는다.
기존 ffmpeg media lifecycle은 변경하지 않았으며, 실제 handler를 등록할 때 이
factory로 기존 materializer를 만들도록 연결해야 한다. bypass한 별도 producer는
lease로 보호되지 않는다. 이 연결 상태는 독립 리뷰에서 특히 확인할 항목이다.

**추가 직접 smoke:** `media_smoke.py`는 기존 CI 합성 영상 설정만 재사용해 API와
Worker의 주입 factory로 각각 실제 공개 Recording analysis/incident bytes를
생성했다. 실제 TemporaryDirectory 진입 때 mtime을 오래되게 만들어 scan과
경합시켰으며 API 2회/Worker 2회 모두 활성 보호를 확인했다. 각 서비스 startup의
old temp 회수·다른 서비스 root 보존·young temp 보존, 정상 close 후 잔여 없음과
두 cleanup thread 종료도 PASS다(`media-smoke.json`). 이는 기본 entrypoint의
실제 handler 등록/production profile 정책을 추가하거나 검증한 결과는 아니다.

## TDD와 직접 검증

모든 아래 원본은 `.codex-scratch/rt12a-20261022/`에 있다. 과거 PR CI나 과거
보존 결과를 이번 직접 실행 결과로 재사용하지 않았다.

| 단계 | 직접 실행과 결과 |
| --- | --- |
| RED 1 | `red1b.txt`: cleanup 모듈 부재로 20 failed. 최초 `red1.txt`도 보존 |
| GREEN 1 | `green1c.txt`: 20 passed, 실제 Windows junction 포함 |
| RED 2 | `red2.txt`: lifecycle/catalog 부재로 8 failed |
| GREEN 2 | `green2b.txt`: 8 passed |
| RED 3 | `red3d.txt`: API/Worker 연결·temp_root adapter 부재로 14 failed |
| GREEN 3 | `green3b.txt`: 42 passed |
| RED 4 | `red4b.txt`: lookalike 삭제와 secondary close의 primary 덮어쓰기로 2 failed; 기존 hardlink/readonly 보호 확인 2 passed |
| GREEN 4 | `green4b.txt`: 46 passed |
| 관련 회귀 | `regression1.txt`: 363 passed, 101.10초. 마지막 reader/target 검증 추가 전 실행 |
| RED 5 | `red5.txt`: 열린 Windows shared-delete reader를 삭제 성공으로 세는 1 failed |
| GREEN 5 | `green5.txt`: 47 passed |
| RED 6 | `red6.txt`: publish 경로의 잘못된 temp 주입을 받아들이는 4 failed |
| 최종 focused | `green6.txt`: 51 passed, 1 existing Starlette TestClient deprecation warning |
| 전체 pytest | `full.txt`/`full.xml`/`full-attempt.json`: **정확히 1회**, exit 0, **9800 passed / 937 skipped / 1 warning**, pytest 412.20초 |
| 추가 직접 smoke | `media-smoke.json`: API/Worker 실제 합성 analysis·incident bytes, 활성 temp 2회씩 보호, startup root 분리·young 보존·close/stop/join PASS. pytest 호출 아님 |

전체 pytest의 skip은 MySQL URL 미설정 911개, 로컬/실제 영상 opt-in 미설정
22개, `typer` 미설치에 따른 기존 collection skip 4개다. JUnit 10,737 cases에서
failure/error 0을 확인했다. **skip 0 MySQL mandatory gate PASS는 주장하지 않는다.**
이 작업은 해당 gate/inventory를 수정하지 않았다. 전체 재시도는 하지 않았다.

전체 실행은 `python -X utf8 -B -m pytest`로 selection 없이 수행했고, evidence와
temp 위치만 환경 변수로 지정했다. Windows 경로의 backslash가 PYTEST_ADDOPTS
파싱에서 제거되어 JUnit이 checkout의 다른 이름으로 생성됐다. 원본 SHA-256
`dd8296a523995e378ae219ff09e821654185fea477f7ead9e9e6c836787666fe`를 검증해
`full.xml`로 이동했으며 내용 변경이나 테스트 재실행은 없다. 시작 C: 여유는
13,746,589,696 bytes, 예상 추가 공간은 약 3 GiB(추정)로 기록했다.

실패 원본/환경 이력도 숨기지 않는다. sandbox는 junction 생성과 Windows asyncio
socketpair를 제한하여 처음 focused 실행 일부가 실패/정지했다. socketpair stack을
확인한 뒤 해당 focused 실행만 중단하고 로컬 허용 실행으로 진행했다. PowerShell
built-in module 부재로 최초 출력 리다이렉션과 fixture 변환 command가 실패했고,
이후 Python file I/O로 보존했다. 테스트 수집 파일명 충돌/patch 구문 오류와
buffered close의 mtime 갱신을 확인해 fixture를 바로잡은 중간 실행도 보존했다.
이 중간 출력들을 기능상 RED나 전체 pytest 결과로 합성하지 않는다.

## 미실행·남은 위험과 리뷰 판단 항목

- Linux/POSIX syscall 경로의 직접 실행과 원격 CI는 미실행이다. 기존 WSL Ubuntu의
  Python 3.12.3에는 pytest/pydantic/SQLAlchemy가 없어 설치 없이 확인을 끝냈다.
  직접 테스트 환경은 Windows, 기존 `.venv` Python 3.12.14/pytest 8.4.2다.
- 실제 MySQL 환경은 추가하지 않는다. cleanup은 DB를 사용하지 않고 mandatory
  inventory/gate를 수정하지 않는다. 전체 실행의 기존 opt-in skip은 별도 보고한다.
- cleanup root는 서비스가 소유하는 local filesystem 디렉터리여야 하며 배포가
  provision한다. producer factory는 임의 ancestor를 만들거나 global temp로
  fallback하지 않는다. 실제 materializer/handler 연결은 위 범위를 참조한다.
- POSIX lease는 advisory다. 협력하지 않는 외부 writer가 마지막 identity 확인과
  unlink 사이에 entry를 바꾸는 적대적 동작까지 원자적으로 차단하는 보장은 없다.
  이러한 writer와 root를 공유하는 배치는 이 구현의 안전 전제가 아니다.
- 활성 producer 하나가 있으면 같은 root의 오래된 다른 잔여도 다음 scan으로
  미뤄진다. 긴 local filesystem I/O는 join을 지연시킬 수 있다. 새 shutdown
  timeout이나 daemon 방치로 이 한계를 숨기지 않는다. 기존 로그 sink 정책도 유지한다.
- tempfile naming 변경 시 matcher도 함께 검증해야 한다. 알 수 없는 이름은
  자동 삭제하지 않아 잔여가 보존될 수 있다. 이는 user file 보존을 위한 선택이다.
- orphan publish(P-6), RT-12(b) 집계·전체 catalog, retention/purge/disk guard,
  #387·RT-11(c)·RT-10(b)는 이 diff에 없다. RT-12 전체 DONE/issue close를 주장하지 않는다.
- 독립 재리뷰와 해당 환경의 검증이 남아 있으므로 merge-ready/Owner acceptance를
  주장하지 않는다. 검증에서 발견된 실제 차단 문제는 최종 결과에 이름으로 남긴다.

## 자원·Git 최종 인계

`cleanup.json`의 정확한 allowlist 경로를 resolve 검증한 후, 이번 세션의 focused/
전체 pytest TEMP root를 정리했다. 실패/잔여 root 0이다. 기존 API fixture가 root를
checkout으로 지정해 새로 만든 zero-byte lease 파일 2개도 exclusive 획득을
확인한 뒤 제거했다. 추가 media smoke의 단일 root도 생성한 script가 검증 후
정리했다. 원본 RAW·JUnit·실행 메타데이터·실패 기록·진단 runner는 제외 자료로
보존한다. 기존 다른 작업 자료를 삭제하지 않았다.

완료된 pytest/media smoke의 소유 Python/ffmpeg process와 cleanup thread가
남지 않았고, 기존 실제 API process 테스트는 자신의 listener 종료를 확인했다.
DB/server/datadir는 새로 생성하지 않았다. 기존 WSL 환경에는 패키지를 설치하지
않았고 다른 세션/서비스를 종료하지 않았다.

branch는 `codex/rt12a-cleanup`, HEAD/로컬 origin/develop은 시작 SHA 그대로다.
index는 비어 있고 모든 제품·테스트·문서 변경은 unstaged/uncommitted다.
commit/push/PR 생성과 reviewer/subagent 호출은 0회다. PR/merge SHA는 pending이다.

직접 실행에서 남은 실패는 0이다. 별도 독립 재리뷰, Linux 배포 경로/원격 CI의
미검증 판정이 남았으며 이를 자동 PASS 처리하지 않는다. 기본 실제 handler/
materializer 등록은 RT-10 후속이라는 기존 경계이고, root 단위 지연·외부 writer·
명명 규칙 변경·filesystem/sink 한계는 비차단 운영 위험으로 인계한다.

## 2026-10-23 — 독립 리뷰 P1/P2 후속 수정 (구현자 직접 실행)

이 절은 앞선 구현/리뷰 이력에 **추가**하는 후속 기록이다. 앞선 `9800 passed /
937 skipped`와 reviewer의 결과는 보존 증거이며 이번 수정의 GREEN으로 재사용하지
않는다. 독립 재리뷰의 P1/P2를 기존 PASS로 재분류하지 않는다. 새 reviewer/subagent는
호출하지 않았고 최종 승인 판단도 하지 않는다.

### 시작 무결성과 범위

시작 시 branch/HEAD/로컬 origin/develop은 앞선 값 그대로이고 index는 비어 있었다.
reviewer `git-after.json` 및 구현 manifest와 **변경 20개 SHA-256 모두 일치**했다.
index SHA-256도 reviewer와 일치했다. 보존 JUnit의 위 SHA-256은 그대로다. 기존 구현
증거 파일 37개와 reviewer 최상위 증거 10개의 hash를 이번 작업 전 기록했고 이후
변경 여부를 다시 확인한다. 새 증거는 `.codex-scratch/rt12a-followup-20261023/`에
분리한다. 기존 실패·중단·리뷰 원본은 수정하지 않는다.

### P1 — 재현 → 원인 → 수정 → 검증

1. **직접 재현:** `temp_root=<owned temp>`,
   `media_root=<owned temp>/recording-analysis-abcdefgh`,
   `publish=<media>/source/registered-media`를 오래되게 만든 테스트에서 Windows와
   native Linux `/tmp` 모두 파일을 삭제하고 `count=1, bytes=9, failed=0`을 반환했다.
   `p1-windows-red.txt`, `p1-posix-red.txt` 각각 **11 failed / 7 passed**다. 통과한
   7개는 기존에 안전했던 경계이며 실패한 결함과 합성하지 않는다.
2. **원인:** 기존 구성 검사는 publish와 같은/그 아래 temp만 거부하고 반대 방향을
   허용했다. temp 이름에 맞는 media ancestor에 들어가면 재귀가 publish까지 갔다.
   startup의 staging lease 생성이 우연히 media mtime을 갱신해 특정 API 시작 경로에서
   재현을 숨길 수도 있었으나, 직접 temp scan에서는 API/Worker 모두 재현됐다.
3. **수정:** 기존 동일·하위 temp 구성 거부를 유지한다. 상위 temp 구성은 기존 API
   fixture/조립의 `temp_root=media_root` 사용을 깨지 않도록 허용하되, scanner에
   보호 publish 경로를 주입하고 동일·상위·하위로 겹치는 **가지 전체를 진입 전
   제외**한다. 비어 있는 publish와 그 조상도 삭제하지 않는다. 기존 구성 요소의
   symlink/junction/reparse/비디렉터리나 확인 불가능한 경로는 cleanup lifecycle을
   만들기 전에 fail-closed한다. 상대/`.` 정규화에도 같은 보호를 적용하며 기존
   `..` 거부를 유지한다. 순회 시 no-follow pin을 다시 수행한다.
4. **대안:** 모든 ancestor temp 구성을 시작 오류로 바꾸면 기존 root 공유 조립을
   넓게 변경해야 한다. subtree 제외는 해당 조립을 유지하면서 publish에 대한
   소유권 판단·등록 조회 없이 보존한다. 보호 가지 안의 다른 오래된 temp도 남길
   수 있는 보수적 비용은 허용한다. P-6/orphan cleanup·DB 조회는 추가하지 않는다.
5. **GREEN:** `p1-windows-green.txt` **69 passed**, `p1-posix-green.txt`
   **57 passed**. Windows junction/Linux symlink, 두 service의 경로 관계 4종,
   상대 경로, 거부 시 lifecycle 미할당, 허용 구성의 stop/join을 포함한다.

### P2 — 재현 → 원인 → 수정 → 검증

1. **직접 재현:** root와 nested directory에서 첫·중간·마지막 metadata만 각각
   PermissionError/OSError/FileNotFoundError를 내게 했다. 기존 리스트 선적재로
   정상 aged 파일도 남았다. OSError 계열은 `count=0, bytes=0, failed=1`, 소실은
   `failed=0`으로 root/가지 전체를 끝냈다. 100,000개 열거 시험은 첫 소비 전에
   metadata 100,000개를 적재했다. Windows/native POSIX RED는 각각 **21 failed**다.
2. **수정:** `Pinned.entries()`는 한 항목씩 metadata를 가져오는 generator다.
   FileNotFoundError는 정상적인 동시 소실로 건너뛰며 실패/삭제 수·bytes에 세지
   않는다. 다른 metadata OSError는 원문 예외를 보관하지 않는 실패 표시를 yield하고
   scanner가 **항목당 failed 1**을 기록한 뒤 다음 항목으로 진행한다. root와 nested
   순회가 같은 처리를 사용한다. iterator는 명시적으로 close한다.
3. **빈 디렉터리:** `is_empty()`는 metadata를 읽지 않고 이름 최대 1개만 확인한다.
   재귀 뒤 전체 목록·metadata를 다시 적재하지 않는다. 실제 rmdir도 원자적인
   최종 판정을 유지한다. 디렉터리 자체의 scandir/open 오류는 해당 root/가지의
   오류로 남긴다. 열거 자체가 불가능한 디렉터리에서 항목별 성공을 만들지 않는다.
4. **대안:** bounded batch도 가능하지만 한 항목 generator로 충분하다. 단순히 바깥
   except에서 오류를 무시하면 정상 대상의 starvation과 누락 집계가 남으므로
   채택하지 않았다. 실제 삭제 handle·identity/age 재검사·lease는 유지한다.
5. **GREEN:** P1 포함 Windows focused **90 passed**,
   native POSIX storage focused **78 passed**다. 오류 위치 3종×오류 3종×root/nested,
   정확한 count/bytes/failed, privacy, 100,000개 lazy 열거, 최대 1개 이름의 empty
   확인 및 기존 readonly/sharing·교체·hardlink·path escape 회귀를 포함한다.

### 이번 직접 검증과 과거 증거 구분

- Windows 관련 회귀: `windows-regression.txt` **407 passed**, 기존 warning 1,
  102.40초. upload 수신→fsync→close→publish→등록, timeout/disconnect/process 종료,
  API/Worker lifecycle, logger/config 및 전체 cleanup focused를 직접 실행했다.
- native POSIX는 reviewer의 기존 wheel을 읽기 전용으로 복사해 새 native `/tmp`
  임시 venv에만 풀었다. 시스템 패키지는 설치하지 않았다. 소스/테스트 복사본의
  hash가 현재 checkout과 일치함을 실행 전 확인했고 각 native root를 제거했다.
  이 결과를 Windows lifecycle 또는 POSIX HTTP/process 전체 검증으로 확대하지 않는다.
- 공용 순회와 시작 구성 검증이 여러 소비자에 영향을 주므로 이번 revision에서도
  선택 없는 전체 pytest를 새 증거 폴더에서 1회 실행한다. 기존 전체 결과로 대체하지
  않는다. 실제 MySQL 및 원격 CI는 추가하지 않으며 skip을 gate 성공으로 보지 않는다.
- 전체 결과·최종 정적 검사·자원/증거 hash/manifest는 완료 뒤 아래에 추가한다.

### P3 판단 — 이번 제품 변경 없음

| 리뷰 위험 | SoT와의 관계 및 유지 이유 |
| --- | --- |
| POSIX 비협력 writer/ancestor rename | no-follow와 cooperating lease만으로 외부 writer를 강제하지 못한다. 서비스 전용 local root·모든 Runtime producer의 lease 참여 전제를 유지하며, 악의적/비협력 rename 뒤의 root 밖 삭제 안전성은 보장하지 않는다. 강제 격리는 filesystem/배포 소유권 또는 별도 설계가 필요하다. |
| 멈춘 filesystem I/O와 상한 없는 join | B-C4는 scan 주기이고 새 shutdown hard deadline은 아니다. 소유 thread를 버리지 않는 join을 유지한다. I/O 취소/별도 process/새 timeout 정책을 이번 수정에서 만들지 않는다. 완료가 지연될 수 있다는 한계는 남는다. |
| 예상 밖 비-OSError의 periodic thread 종료 | 이 경우 다음 scan이 사라져 정상 cadence를 유지하지 못한다. 알려진 filesystem OSError는 P2에서 격리했다. 그 밖의 programming/fatal 오류를 무조건 숨겨 반복하는 복구 정책 근거는 없으므로 기존 failure 보관·close 시 전달을 유지한다. 이 실패 상태를 정상 주기 실행으로 승인하지 않는다. |
| 활성 producer 때문에 root 전체 보존 | 활성 파일 미삭제를 우선하는 기존 보수적 선택이다. Baseline은 잔여물 회수 완료 deadline을 정하지 않는다. 항목별 lease/capability로 확장하지 않고 지연 위험을 유지한다. |
| wall clock 급전진/역행 | Baseline은 mtime 나이 조건을 사용한다. clock-jump 억제 threshold나 별도 지속 시각 정보의 정책 근거가 없으므로 새 숫자/정책을 만들지 않는다. 급전진의 조기 포함·역행의 정리 지연 위험은 남는다. |

### PR 범위 판단

저장소 지침에서 내부 실행 계획의 납품 의무는 확인되지 않았다. 기존
`docs/superpowers/plans/2026-10-22-rt12a-cleanup.md`는 원본 hash를 유지해 이번
ignored scratch의 `internal-plan/`으로 이동했으며 PR 후보에서 제외한다. 위의
20개 목록은 최초 구현 당시 기록이다. 최종 후보는 제품 9·테스트 7·문서 5의
**21개**이며 새 테스트는 `test_cleanup_publish_safety.py`, `test_cleanup_metadata.py`다.
이번 후속의 제품 수정은 `_filesystem.py`, `cleanup.py` 두 파일뿐이다. note/Log는
이력 추가로 갱신한다. Implementation Log 기존 CRLF bytes는 유지해 부수적인
전체 줄바꿈 변경을 피한다. RAW/JUnit/JSON/runner/wheels/임시 자료는 모두 제외한다.

상태는 계속 **IN_PROGRESS · Refs #299 (RT-12(a))**, PR/merge SHA pending이다.
staging·commit·push·PR·reviewer/subagent 호출을 하지 않는다. 새 P1/P2가 없다는
자체 최종 승인 대신 기존 독립 리뷰 대화에서 후속 재리뷰할 수 있게 인계한다.

### 2026-10-23 후속 최종 직접 실행 결과

- 이번 revision의 bare 전체 pytest는 **1회**, exit 0, **9839 passed /
  937 skipped / 1 warning**, 501.82초다. 시작/종료 제품·테스트
  hash 일치를 확인했다(`full-attempt.json`). skip은 MySQL 911·media
  22·collection 4이며 실제 MySQL mandatory gate와
  원격 CI는 미실행이다. 이전 전체 결과를 이번 결과로 대체하지 않았다.
- Windows focused90/관련 회귀407 및 native POSIX focused78은 이번 직접 실행이다.
  P1 RED11/7→GREEN, P2 RED21→GREEN의 원본은 그대로 보존한다. native POSIX는
  hash가 일치하는 복사본을 사용했고 최신 실행의 소스가 현재 checkout과 같다.
- boundary·Contract fixture·workflow30분/nested900초·gate/inventory 불변 및
  diff/신규 파일 whitespace/AST 검사를 최종 확인한다. Contract·Accepted Decision·
  Baseline은 의미/파일 변경이 없다. 기존 Log prefix/suffix bytes를 유지했다.
- 이번 Windows 임시 root 7개와 새 zero-byte checkout lease 2개를 exclusive 확인
  후 정리했다. native 임시 root 4개도 각 실행이 정리했다. 실패/소유 root 잔여는
  없으며 RAW/JUnit/JSON/runner/wheels와 내부 plan은 ignored 자료로 남긴다.
  기존 구현 증거 37개와 리뷰 증거 10개의 hash는 그대로다.
- 최종 PR 후보/후속 수정 목록은 이번 증거 폴더의 `manifest.txt`/`manifest.json`에
  기록한다. 제품·테스트·문서는 모두 unstaged/uncommitted이고 기존 branch/HEAD/
  index를 유지한다. 후속 독립 재리뷰에 넘기며 자체 최종 승인하지 않는다.


## 2026-10-23 — 경로 별칭 P1 추가 수정 (구현자 직접 검증)

**IN_PROGRESS · Refs #299 (RT-12(a))**. 앞선 일반 경로 P1 GREEN과 P2 해소
기록은 보존 이력이다. 후속 독립 리뷰는 P2 해소를 판정했으나 경로 별칭으로 P1을
재현했다. 이번 절은 그 남은 P1의 수정이며 reviewer 최종 판정을 대신하지 않는다.

### 시작 무결성

- 후속 reviewer의 `git-after.json`과 현재 PR 후보 **21개 SHA-256**, branch,
  HEAD `1f830afeac93309e9ef9c8eb90fcfaced0f97ae0`, index hash가 모두 일치했다.
  index는 비어 있다. 기존 구현·후속·두 리뷰의 증거 파일 **100개**를 기록했다.
  범위는 각 evidence 폴더의 RAW/JSON/runner 등 최상위 파일 및 후속 wheel/internal
  plan이며 reviewer의 대량 pytest 임시 tree는 제외한다. 옛 구현 증거 37개의
  이전 hash도 다시 검증했다. 새 증거는 `.codex-scratch/rt12a-alias-20261023/`다.

### RED → 원인 확인

- 제품 테스트에서 각 alias가 실제 같은 디렉터리인지 먼저 `os.path.samefile`로
  확인했다. 일반/일반, temp 일반·media 별칭, temp 별칭·media 일반, 양쪽 별칭을
  API/Worker 각각 실행했다. Windows `\\?\` 혼용, Linux `/tmp`·`//tmp` 혼용에서
  publish가 삭제됐다. 외부 aged 파일도 둔 시험은 `count=2, bytes=12, failed=0`,
  미생성 media/source를 composition 뒤 만든 시험은 `count=1, bytes=9, failed=0`이었다.
- 실제 로컬 Windows RED는 **16 failed / 46 passed**(`p1-windows-red-native.txt`),
  native POSIX RED는 **16 failed / 38 passed**(`p1-posix-red-native.txt`)다. 같은 경로
  표기와 기존 case/separator/`.` 경계는 이 실행에서 이미 통과했다. namespace 혼용
  4건, 미생성 suffix 4건, 동일/하위 금지 관계 우회 8건이 실패했다.
- 원인은 `abspath`와 `Path.parents`만으로 namespace anchor를 비교한 데 있다.
  Windows의 drive/extended anchor, Linux의 `/`/`//` anchor가 서로 달라 보호 경로가
  불일치했다. 문자열 prefix 문제나 symlink·비협력 writer의 P3 재현이 아니다.

### 선택한 수정과 대안

- 기존 보호 가지 제외 설계를 유지한다. `configuration_path`는 가장 가까운 기존
  ancestor까지 기존 no-follow `Pinned` traversal로 연다. 링크·junction·reparse·
  비디렉터리·확인 불가능한 요소는 lifecycle 할당 전 고정 메시지로 거부한다.
- Windows는 열린 directory handle의 `GetFinalPathNameByHandleW`에서
  `FILE_NAME_NORMALIZED | VOLUME_NAME_GUID`를 사용한다. drive/extended/실제 8.3 이름을
  같은 volume GUID+정규 이름 형태로 통일한다. Path component 비교의 Windows
  case-insensitive 의미를 사용하며 문자열 prefix 비교는 없다. UNC/extended UNC와
  device namespace는 네트워크 경로를 열기 전에 거부한다. 이 볼륨에서는 8.3 이름이
  실제 제공됐고 OS identity 확인과 삭제 안전성을 검증했다. UNC의 실제 공유
  동등성은 허용된 공유 환경이 없어 실측하지 않았다.
- Linux는 `/`와 입력 anchor를 각각 no-follow로 열어 dev/inode가 같은지 확인한
  경우에만 single-root 표현으로 통일한다. 다르면 구성 오류다. 중복 separator와
  `.`는 기존 ancestor의 실제 pin 검증과 함께 처리한다. `..`는 기존처럼 거부한다.
- 미생성 하위 경로는 pin으로 확인한 기존 ancestor의 canonical 이름에 검증한
  lexical suffix를 붙인다. Windows의 raw trailing dot/space·예약 이름·특수 문자,
  identity를 아직 확인할 수 없는 missing 8.3 suffix는 거부한다. raw component는
  Win32 abspath가 trailing dot을 버리기 전에 검사한다.
- 구성 검증과 보호 scanner의 root/lease/protected 경로는 같은 함수를 사용한다.
  scan 후보는 canonical root 아래의 이름으로만 비교하며, scan/delete 도중
  `resolve`/realpath 또는 새로운 canonical pathname 재추적을 하지 않는다. 기존
  ancestor pin·no-follow·leaf identity 확인·handle 삭제는 그대로다.
- 모든 ancestor 구성을 거부하면 기존 공유 root 조립이 깨지므로 선택하지 않았다.
  단순 namespace prefix 제거/문자열 소문자화만으로는 실제 8.3 identity와 미생성
  suffix의 안전성을 확인할 수 없어 채택하지 않았다. P-6/등록 조회/orphan publish/
  RT-12(b)는 추가하지 않는다. 기존 P2 `Pinned` class와 `_walk` 구현은 재작성하지
  않았다(Pinned AST와 metadata 테스트 bytes를 이전 snapshot과 대조한다).

### GREEN과 추가 경계

- 최초 수정 직후 publish safety는 Windows **62 passed**, native POSIX **54 passed**다.
  namespace 양방향 혼용과 동일/하위 관계 우회 및 미생성 suffix의 RED가 GREEN 됐다.
- 추가 8.3 matrix는 수정 전 두 source 파일의 hash 확인 복사본에서 **10 failed /
  30 passed**였다(`baseline-aliases.*`). namespace 혼용 4건과 short 이름 media/temp/
  양쪽 alias 6건이 publish 삭제를 검출했다. checkout을 되돌리지 않았으며 이 추가
  baseline 재검사를 수정 전 최초 실행이라고 표현하지 않는다. 현재 수정본에서는
  8.3 조합도 모두 통과했다.
- Windows 추가 경계 실행에서는 trailing-dot 정책 RED 1건과 삭제 직후 하위 경로
  `exists()`의 WinError 5가 있었다. raw component 검증을 앞당겨 정책을 수정하고,
  제거 검증은 남아 있는 상위 디렉터리의 실제 이름 목록으로 확인했다. 구성 실패 후
  rename 거부도 2회 관찰됐으나 독립 진단에서 열린 handle 모두 CloseHandle 성공 및
  rename 성공을 확인했다. 이후 같은 진단도 통과했다. 당시 거부 원인을 확정하지
  않는다. 최종 자원 테스트는 Runtime이 연 각 실제 handle을 OS에 조회해 모두
  ERROR_INVALID_HANDLE임을 검증한다. 최초 실패 원본은 남긴다.
- 최종 Windows cleanup/API·Worker lifecycle focused **156 passed / 1 warning**,
  native POSIX storage focused **122 passed / 6 Windows 전용 skipped**다. P2 오류
  위치·소실·집계·streaming·privacy, 기존 hardlink/junction/symlink/교체·readonly/
  sharing 검증을 포함한다. alias의 publish 파일/조상 디렉터리 보존과 0 집계,
  외부 aged temp/staging의 정확한 집계, component prefix 구분, 구성 뒤 rename+link
  교체, lifecycle/lease/handle 잔여 없음도 검증했다.

### 넓은 회귀 실패를 분리해 보존

- Windows 관련 회귀는 **470 passed / 3 failed / 1 warning**, 117.54초다.
  `test_nested_partial_tree_young_child_and_unknown_root_entries`는 삭제 성공 count 뒤
  하위 `exists()`에서 WinError 5, `test_receive_abort_sends_no_status_and_never_registers`
  `[disconnect]`는 40ms idle 제한 선행, `test_failed_sink_with_unread_stderr_does_not_deadlock_interpreter`
  는 기존 9초 subprocess 제한 초과였다. 최초 로그는 `windows-regression.txt`다.
- 동일 테스트/기존 deadline의 선별 진단은 **5 passed**, 5.35초였다. 시험 시간이나
  기존 테스트·upload/logging 제품 코드는 바꾸지 않았다. 이 진단을 넓은 회귀 PASS나
  당시 원인 해소로 합성하지 않는다. 세 실패의 근본 원인은 확정하지 못했다.
  최종 소스 bare 전체 pytest는 별도 원본으로 정확히 1회 실행한다.
- 최초 sandbox junction 권한 오류·WSL 접근 거부, 첫 native runner의 wheel 경로
  오타, 사용 한도로 실행되지 않은 자동 승인 검토도 제품 RED와 구분한다. native
  runner 오류 원본 및 각 owned root 정리 기록은 그대로 남긴다.

### 보장 경계와 범위

- Windows는 canonical GUID 이름을 확인할 수 있는 local volume만 지원한다. UNC,
  device namespace, link/reparse 및 검증 불가능한 missing short 이름은 fail-closed다.
  다른 Windows 파일시스템/원격 공유 동작을 이번 NTFS 실측으로 보장하지 않는다.
- POSIX `/`·`//` 동등성은 native Linux에서 실측했다. 다른 POSIX의 특수 `//`
  의미는 root identity가 다르면 거부한다. bind mount/서로 다른 mount namespace의
  별칭 통일과 privileged mount 변경은 이번 검증 범위가 아니다. 서비스 전용 root와
  안정된 mount topology가 전제이며, 그 배치의 publish 보호를 검증했다고 주장하지
  않는다. 비협력 writer의 ancestor rename 등 기존 POSIX advisory lease 한계도 남는다.
- 기존 P3 다섯 위험과 P2 해소 기록은 유지한다. 새 정책·timeout·P-6 기능을 추가하지
  않았다. PR 후보는 계속 21개, 이번 source/test 수정은 `_filesystem.py`, `cleanup.py`,
  `test_cleanup_publish_safety.py` 세 파일이며 note/Log를 더해 후속 수정은 5개다.
  내부 plan·scratch·RAW/JUnit/JSON/runner/임시 자료는 계속 PR 제외다. 전체 pytest/
  정적 검사/자원·hash 최종 감사 결과는 아래에 추가한다.

### 별칭 후속 최종 직접 실행·감사

- 이번 최종 source의 bare 전체 pytest는 정확히 **1회**, exit 0,
  **========== 9905 passed, 937 skipped, 1 warning in 490.64s (0:08:10) ===========**다. JUnit 실패/error 0개, skip 937개다.
  MySQL 911·media 22·collection 4
  skip을 mandatory gate 성공으로 보지 않는다. 실제 MySQL mandatory gate와 원격 CI는
  미실행이다. 시작/종료 제품·테스트 hash를 확인했으며 전체 재실행은 하지 않았다.
- 위의 broad 470PASS/3FAIL과 선별 진단5PASS는 별개 실행이다. 전체 결과가 앞선
  실패 원인 해소·과거 실패의 PASS 재분류를 뜻하지 않는다. 원본은 모두 보존한다.
- Windows 최종 focused156PASS와 native POSIX122PASS/Windows전용6SKIP는 이번 직접
  결과다. 이전 구현/리뷰 수치로 대체하지 않았다. boundary/Contract fixture/workflow
  30분·nested900초/gate 불변/diff 검사를 최종 실행하고 감사 결과를 `final.json`에
  기록한다. P2 Pinned AST·_walk와 metadata 테스트 bytes는 이전 그대로다.
- 이번 실행이 소유한 Windows 임시 root·native root·baseline 복사본·checkout의 새
  zero-byte lease만 검증 후 정리한다. 기존 증거100개·index hash와 21개 후보 범위를
  확인한다. RAW/JUnit/JSON/runner와 이전 plan은 ignored 자료로 남긴다. 실제 삭제 및
  native root 부재 결과는 `final.json`/`resources.json`에 기록한다.
- 이번 후속은 제품2·기존 테스트1·문서2의 5개 파일이며 최종 21개 목록/hash는
  `manifest.txt`/`manifest.json`이다. 모든 변경은 unstaged/uncommitted, branch/HEAD는
  그대로다. 새 reviewer/subagent와 staging/commit/push/PR 호출은 없다. 상태는
  **IN_PROGRESS · Refs #299 (RT-12(a))**이며 별도 독립 후속 재리뷰를 기다린다.
