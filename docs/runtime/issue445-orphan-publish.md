<a id="p-6-orphan-publish--implementation-notes"></a>

# P-6 고아 publish — 구현 참고 사항

IN_PROGRESS · Refs #445 · Related #299. 배포는 보류한다.

<a id="authority-and-starting-state"></a>

## 권한과 시작 상태

2026-10-31: 브랜치 `codex/issue445-orphan-publish-cleanup`, HEAD와 원격
develop은 `326f91334a4878b34135631e6b0e660b2c791b98`; 인덱스/작업 트리는 처음에 깨끗했다.
저장소 AGENTS.md는 발견되지 않았으며, 제공된 AGENTS 지침과 CLAUDE.md 라우터를
적용한다. Issue #445에는 댓글이 없다. #299의 종료 댓글은 P-6을 명시적으로
이관한다. PR #390은 publish를 보존하고 PR #409는 관측만 추가한다. 이들의 과거
테스트 결과는 이번 변경의 증거가 아니다.

<a id="design-and-implementation-choices"></a>

## 설계와 구현 선택

API 업로드만 영속 파일시스템 원본(`source/<uuid hex>`)을 publish한다.
Recording의 `local_source` 메타데이터는 그 상대 locator를 등록하며, 준비된
analysis/incident, frame 및 파생 콘텐츠는 Recording MySQL BLOB을 사용한다. Worker
materializer는 기존 lease 임시 루트 아래에 임시 파일을 만든다.
제품 purge와 BLOB 수명주기는 이번 변경의 범위 밖이다.

공개 Recording capability는 정규화된 관리 대상 상대 publish locator 하나를 받아
REGISTERED, UNREGISTERED 또는 UNKNOWN을 반환한다. SQL/연결 실패는 계속 실패이며
부재로 취급하지 않는다. Runtime은 테이블이 아닌 공개 인터페이스를 사용한다.
저장소는 일관된 스냅샷이 아니라 local-source 메타데이터의 현재 잠금 읽기를 사용한다.
NOWAIT 경합은 안전하게 차단되며, 연결이 끊긴 클라이언트의 아직 살아 있는
트랜잭션도 포함한다. 트랜잭션 완료는 호출자가 책임지며, runtime은 새로운 짧은
트랜잭션을 사용하고 파일 삭제 전에 연결을 반환한다.

루트 수준 OS lease를 재사용한다. API는 업로드 전부터 등록 commit/rollback과
취소 정리까지 공유 publish lease를 유지한다. 스캐너는 조회와 신원을 검증한
삭제가 끝날 때까지 비차단 배타 lease를 유지한다. 살아 있는 producer는 전체
루트의 처리를 연기한다. 잠금은 제거하거나 교체하지 않는다. OS 충돌로 잠금이
해제되더라도 DB rollback이 입증되지는 않는다. 현재 잠금 쿼리도 성공해야 한다.
쿼리 후 unlink만으로는 원자적이지 않으며, 협력하는 writer 프로토콜과 고정한
파일시스템 신원은 각각 별도의 필수 보호 장치다.

고정한 source 안의 직속 정규 UUID 파일만 후보가 된다. 기존 staging/temp publish
보호는 유지한다. 링크, reparse point, 여러 hardlink, 변경된 신원/버전 및 입증할 수
없는 루트 관계는 거부한다. locator로 신원을 추론하지 않는다. 정규 상대 등록은
저장된 root-key 표기와 관계없이 이름을 보호하며, 정규형이 아닌 저장 locator는
부재를 불확실하게 만든다(전체 루트의 처리를 연기할 수 있음).

검토한 대안: 나이만으로는 정체된 등록을 보호할 수 없고, 새로운 영속 publish
타임스탬프/테이블은 스키마를 불필요하게 확장하며, 파일별 lease에는 alias에 안전한
새 잠금 신원이 필요하다. 거친 루트 lease를 재사용하면 기존 절충이 유지된다.
활성 작업이 관계없는 정리까지 연기할 수 있다.

B-C2는 86400초, B-C4는 시작 시 실행과 3600초 고정 지연을 유지한다. 기존 정리와
일치하는 구현 선택으로 mtime을 채택하며, 경계값이 같으면 보존한다. 시스템 시계가
뒤로 가면 정리가 지연되고, 앞으로 뛰면 나이 조건을 더 빨리 충족할 수 있지만
등록/lease/신원 검증을 우회할 수는 없다. 새로운 운영 프로필, 보존 정책 또는
바이트 제한은 선택하지 않는다.

POSIX advisory lease에는 협력하는 writer가 필요하며, 임의 SQL/직접 파일 writer와
mount namespace/bind alias는 그 보장의 범위 밖이다. Windows는 기존 고정 handle과
OS가 확인한 alias 정규화를 사용한다. 정확한 플랫폼 실행, 한계, 리뷰 및 인수
증거는 아래에 기록한다.

<a id="capability-and-ownership"></a>

## Capability와 소유권

| 경계 | 의미 |
| --- | --- |
| 공개 진입점 | `RecordingService.read_publish_registration(locator)`; 내보낸 `PublishRegistration` enum |
| 입력 | 정확히 `source/[0-9a-f]{32}`. 잘못된 namespace, 표기, 타입 또는 traversal은 저장소 접근 전에 UNKNOWN 반환 |
| REGISTERED | 영속 local-source 메타데이터 행이 이 상대 locator를 가리킴; 삭제 금지 |
| UNREGISTERED | 성공한 현재 읽기에서 일치하는 행과 모호한 저장 locator가 없었음; 독립적인 삭제 허가는 아님 |
| UNKNOWN / 예외 | 잘못되었거나 지원하지 않는 결과 또는 locator는 UNKNOWN; DB/연결/잠금 오류는 전파. Composition은 정확한 enum만 True/False/None으로 매핑하며, 스캐너는 `is False`일 때만 삭제 |
| 트랜잭션 | 호출자가 소유한 열린 MySQL 트랜잭션. `SELECT payload ... WHERE kind='local_source' FOR UPDATE NOWAIT`; 이 메서드에서 BLOB fetch, DML, commit, rollback, 재시도 또는 파일 조회 없음 |
| Runtime composition | 기존 RC/UTC API 엔진에서 새로운 `run_api_transaction` 실행, unlink 전에 연결 반환. Runtime에 새 Recording 테이블/스키마 쿼리 없음 |
| 오래된 호출자 | 호출자가 이미 오래된 일관 스냅샷을 설정했어도 현재 잠금 읽기는 REPEATABLE READ에서 더 최근에 commit된 데이터를 확인 |
| Mock | 메모리 저장소는 UNKNOWN 반환: 프로세스 간 영속 부재를 입증할 수 없음 |

이번 P-6 구현 요청은 capability 추가를 허용한다. 이전 Plan이 이미 이를 요구한
것처럼 조용히 취급하지 않고 Recording README에 이 결정을 드러낸다.
Runtime/Recording Owner와 PR 리뷰는 문서화한 범위와 보수적 절충을 확인해야 한다.
여기서는 Owner 인수나 Issue 종료를 주장하지 않는다.

<a id="synchronization-failure-and-deletion-conditions"></a>

## 동기화, 실패 및 삭제 조건

1. API는 staging 생성 전에 공유 orphan lease를 얻으며, 단조 증가 idle/total
   시계는 이 대기 전에 시작한다. 기존 staging lease는 staging 생성/수신/fsync/
   close/publish 전체에 계속 적용된다. 실제 운영 파일시스템 writer는
   `api.upload.publish`이며 Worker는 이 원본들을 publish하지 않는다.
2. staging open 전과 publish 전후에 루트 신원을 확인한다. 라우트는 asyncio
   cancel 이후에도 등록 worker를 shield하고 기다린다.
   `ApiComposition.register_source`는 직접 호출에도 lease를 적용하고,
   preprobe 후 루트를 검증하며 기존 Case + Recording 트랜잭션을 완료한다.
3. orphan 스캐너는 비차단 배타 루트 lease를 얻는다. source는 독립 경로를 다시
   여는 방식이 아니라 **lease가 적용된 media 디렉터리를 통해** 연다.
   삭제 전에 현재 media/source 신원을 다시 확인한다. 링크가 하나이고
   `mtime_ns < cutoff`인 직속 일반 UUID 파일만 후보가 된다.
4. 조회는 commit된 부재를 확증해야 한다. 보류 중인 등록 행은 NOWAIT 실패와
   보존으로 이어진다. API는 COMMIT 제출 전에 local-source 메타데이터를 삽입하므로,
   프로세스 충돌/commit 응답 유실로 진행 중인 등록이 안전한 부정 쿼리로
   바뀔 수 없다. 테스트는 OS lease 해제와 이후 서버 트랜잭션 확정을 구분한다.
5. 조회/트랜잭션 종료 후 leaf를 다시 열고 device/inode, 크기, mtime/ctime,
   일반 파일 타입, 링크 수 및 디렉터리 항목 버전을 비교한 다음 기존 Windows
   delete handle 또는 POSIX unlinkat을 사용한다. 배타 lease는 계속 유지한다.
   이후 협력하는 등록은 기다린 다음 이미 삭제된 파일을 거부한다.
   등록된 이름은 바이트가 변경됐더라도 보존한다.

잠금 순서는 orphan lease → staging lease(수신) → 파일 준비 → Case lock →
Recording DML(등록)이며, staging은 DB 전에 해제한다. 스캐너는 orphan exclusive →
짧은 Recording 전용 쿼리를 사용하며 Case/staging lock은 사용하지 않는다.
파일시스템 lease 대기나 바이트 삭제 중에는 DB 트랜잭션이 없다. 기존 저장소
생성자/준비된 등록은 기존의 짧은 파일시스템 메타데이터 검증을 유지하며, 비용이
큰 probe/hash/encode는 checkout 밖에 남는다. `FOR UPDATE NOWAIT`는 다른 루트의
등록과 경합해 정리를 보수적으로 연기할 수 있다. 전체 local-source payload
스캔은 후보마다 O(registrations)이며 새 스키마/인덱스를 의도적으로 피한다.
목록이 크면 업로드와 정리가 지연될 수 있다. 이는 문서화한 구현 한계다.

Windows orphan은 native `LockFileEx` 공유/배타 byte-range lock을 사용하며,
중첩 route/composition lease와 동시 producer를 허용한다. 기존 staging/temp CRT
잠금 동작은 바뀌지 않는다. POSIX는 `flock`을 사용한다. 제품은 영속 lease 파일을
삭제하지 않는다. 프로세스가 죽으면 OS 잠금은 해제되지만, 불명확한 DB 상태는
현재 읽기가 계속 보호한다. 접근 실패는 일반 잠금 경합과 다르며 무한 반복하지
않는다. 정리는 시작 시 실행, 완료 기준 간격, 로컬 중복 스캔 배제 및 소유한
종료 join을 유지한다. 파일시스템/DB 정체는 여전히 join을 지연시킬 수 있다.

| 관측 | count / bytes / failed |
| --- | --- |
| 실제 일반 파일 제거 | +1 / 신원 재확인 후 스냅샷 바이트 / 0 |
| 등록됨, 살아 있는 루트, 젊음/같은 나이, 안전하지 않은 링크 또는 바뀐 leaf 신원 | 0 / 0 / 0 |
| 동시 파일시스템 소멸 | 0 / 0 / 0 |
| FileNotFoundError를 포함한 UNKNOWN 또는 모든 조회 예외 | 후보마다 0 / 0 / +1 |
| 메타데이터/삭제 오류 | 해당 항목에 0 / 0 / +1; 다른 항목 계속 처리 |
| 루트/lease 신원 또는 접근 실패 | 삭제 없음 / 0 / 루트 수준 실패는 +1, 항목 처리 중 발견하면 후보마다 +1 |

이벤트는 기존 정수 count 필드를 사용하는
`storage.cleanup.orphan.{count,bytes,failed_count}`다. 빈 Context 제출은 timestamp,
level, service, event, count만 유지하고 locator/path/filename/Case ID/예외 텍스트는
포함하지 않는다. API 시작 이벤트 테스트는 이제 정확히 **아홉** 개의 정리 이벤트를
요구한다(기존 staging/temp 이벤트는 여섯 개). 기존 assertion은 완화하지 않았다.

<a id="direct-verification-and-retained-failure-history"></a>

## 직접 검증과 보존한 실패 이력

아래 증거는 이 작업이 직접 실행한 결과이며, 서로 다른 실행의 수를 합산하지
않는다. 원시 출력/JSON/JUnit/내부 runner는
`.codex-scratch/issue445/`에 무시된 상태로 보관한다. 모든 media와 DB 스키마는
합성 데이터이며 이 작업이 소유한다.

| 실행 | 직접 결과 |
| --- | --- |
| `red1b.txt` → `green1b.txt` | capability/스캐너 부재: 23 FAIL → 23 PASS |
| `red2.txt` → 첫 focused | API 연결/lease: 2 FAIL; 이후 focused1 192 PASS |
| `red3.txt`, `posix1.raw` | 조회 FileNotFoundError의 failed-count 결함 재현; Windows 1 FAIL/4 PASS 및 POSIX 1 FAIL/162 PASS/7 플랫폼 skip |
| `posixred.raw` → `posix2.raw` | lease 루트와 쿼리 후 교체: 2 FAIL, 이후 182 PASS/7 기존 플랫폼 skip |
| `red4.txt` → focused3 | deadline에서 lease 대기 누락: 1 FAIL; 수정 후 focused3 210 PASS |
| `red5.txt` → `green5.txt` | Windows 중첩 CRT lease: 외부 lease를 유지한 상태에서 child 10초 timeout → native 공유 잠금 회귀/API 5 PASS |
| `mysql2.raw` | 새 MySQL 테스트 16개 완료 후 첫 기존 HTTP 테스트가 중첩 Windows lease에서 정체. 소유한 pytest PID 종료 확인; 부분 원시 출력/실행 보존, PASS 아님 |
| `mysql3.raw/.json/.xml` | MySQL 8.4.7: 50 PASS(신규 16 + 기존 API 업로드 34), skip/xfail 0, 150개 phase report 모두 PASS |
| `focused4.txt` | Windows: 246 PASS, 기존 Starlette deprecation warning만 있음 |
| `posix3.raw` | WSL Ubuntu POSIX: 185 PASS, 기존 Windows 전용 skip 7개, 같은 warning |
| `mysqlposix.raw/.json/.xml` | WSL Python + 실제 MySQL 8.4.7: 신규 16 PASS, skip/xfail 0 |
| `red6.txt` → `finalstorage.txt` | 잠금 접근 실패를 경합으로 잘못 집계: 1 FAIL → 최종 Windows orphan 33 PASS |
| `posixfinal.raw` | 최종 잠금 접근 변경분과 POSIX orphan 경계: 31 PASS, skip 0 |
| 품질 | 최종 `quality4.txt`: Ruff + mypy linux/win32(각 소스 파일 87개) PASS |
| 경계/Contract/diff | `boundary2.txt`: 위반 0; Contract 구조 62/JSON 26/의미 104 검사 PASS; `git diff --check` PASS |

`red1.txt`에는 scratch 접근 오류, `green1.txt`에는 sandbox가 거부한 hardlink
생성이 있었다. 이는 환경 실패이며 제품 GREEN이 아니다. 이후 테스트는 소유한
basetemp와 승인된 native 파일시스템 접근을 사용했다. 첫 경계 스크립트는 cp949로
em dash를 출력하다 실패했고, 같은 검사는 Python UTF-8로 통과했다.
초기 mypy Optional cleanup guard 오류는 suppression 없이 수정했다.

음성 대조군은 합성 파일에 실제로 위험한 동작을 수행한다. lease를 우회하면 등록
전 활성 파일이 삭제되고, 잠금 쿼리를 일반 일관 읽기로 바꾸면 commit 전 등록
파일이 삭제된다. RR snapshot 테스트는 일반 쿼리가 나중 commit을 놓치는 반면
공개 capability는 이를 확인한다는 점도 입증한다. Thread Events/IPC Pipe
handshake로 경쟁 지점을 제어하며 sleep 기반 경쟁 assertion은 없다. 별도 spawn
프로세스는 DB 전 publish, uncommitted/commit/rollback, DB 전 충돌 및 트랜잭션이
있는 충돌을 다룬다. 명시적인 테스트 전용 DB lock barrier가 죽은 세션의 확정을
관측한다.

<a id="platform-scope-and-remaining-limits"></a>

## 플랫폼 범위와 남은 한계

- Windows 실행은 로컬 NTFS 합성 파일, 일반/확장 namespace,
  대소문자/구분자/dot/실제 8.3 alias, junction, hardlink, readonly,
  고정 handle 및 프로세스 경계를 사용했다. 기존 storage sharing/metadata/lifecycle
  테스트도 실행했다. focused4에서는 Windows skip을 추가하거나 사용하지 않았다.
- POSIX 소스 checkout은 WSL `/mnt/c`(v9fs)에 있으며, storage/lifecycle 테스트
  basetemp는 ext4의 `/tmp/issue445-posix*`로 stat/findmnt로 확인했다. MySQL POSIX
  테스트는 `/mnt/c`의 scratch basetemp를 사용한다. 이는 WSL Linux 프로세스/
  파일시스템 결과이며, 별도 배포된 native Linux 호스트나 컨테이너의 테스트가 아니다.
- 최종 신원 확인과 syscall 사이에 임의의 **비협력** POSIX 디렉터리/파일 rename이
  발생하는 것을 advisory lease로 원자적으로 배제할 수 없다. 탐지된 교체는
  안전하게 차단한다. 이를 악의적인 직접 파일시스템 writer, 직접 SQL insert,
  bind mount, mount namespace, UNC/network 파일시스템 또는 미검증 Windows
  파일시스템에 대한 보편적 안전성으로 해석해서는 안 된다.
- 정규형이 아닌 legacy/local-source locator는 관계없는 이름의 부재도 UNKNOWN으로
  만든다. root-key 표기를 무시하고 루트 전체 활성 보호를 적용하면 전체 루트를
  보존할 수 있다. 정리 처리량이나 디스크 압력에 대한 보장은 없다.
- 외부 행위자의 루트/잠금 교체와 같은 media 루트를 가리키는 여러 DB 간 조정은
  지원하지 않는다. 배포된 모든 writer는 같은 DB와 lease 프로토콜을 사용해야
  하며, 이전 바이너리는 이 lease 없이 동시에 publish해서는 안 된다.
  혼합 버전 배포는 실행하지 않았다.
- 전체 pytest/전체 MySQL inventory/엄격한 전체 suite gate나 Docker build는
  실행하지 않았다. 필수 inventory/checker/timeout/skip/xfail 정책은 바꾸지 않았다.
  최종 통합 전체 suite와 원격 CI는 사용자 push 이후의 조건으로 남는다.

<a id="fresh-review"></a>

## 새로운 리뷰

새 `GPT-6.1 Sol` 리뷰는 reasoning high, 대화 이력 fork 없이 읽기 전용으로
수행했다. 초기 P1 루트 재열기와 P2 deadline/실패 집계 지적은 재현하고 수정했다.
같은 reviewer가 변경분과 새 Windows 공유 잠금 수정도 점검했다. 이후 판단에서는
협력 writer 모델 안에서 추가로 조치할 결함을 찾지 못했다. reviewer는 작성자
증거를 점검하고 직접 실행한 것은 `git diff --check`뿐이며, 테스트 suite는
실행하지 **않았다**. 최종 문서/작은 잠금 오류 변경분 리뷰에서 남은 조치 가능한
코드 지적은 없었다. 관측 표에 대한 사소한 수정(루트 수준 대 후보별 신원 실패
집계)은 코드 변경 없이 적용했다. 같은 reviewer가 이 정확한 문서 변경분을
확인했고 남은 지적은 없었다.

<a id="complete-candidate-file-list"></a>

## 전체 후보 파일 목록

| 영역 | 파일 |
| --- | --- |
| API | `src/daesingo/api/composition.py`, `routes_sources.py`, `upload.py`, `README.md` |
| Storage | `src/daesingo/common/storage/_filesystem.py`, `cleanup.py`, `src/daesingo/common/README.md` |
| Recording | `src/daesingo/recording/__init__.py`, `mysql_repository.py`, `repository.py`, `service.py`, `publication.py`, `README.md` |
| API 테스트 | `tests/api/test_api_cleanup.py`, `test_orphan_upload.py` |
| Storage 테스트 | `tests/common/storage/test_orphan_publish.py` |
| Recording 테스트 | `tests/recording/test_publish_registration.py`, `test_publish_registration_mysql.py` |
| Runtime 문서 | `docs/runtime/README.md`, `issue445-orphan-publish.md`, `runtime-implementation-log.md` |

<a id="issue-acceptance-evidence-and-prowner-checks"></a>

## Issue 인수 증거와 PR/Owner 확인

| #445 완료 기준 | 증거 / 남은 확인 |
| --- | --- |
| 등록 파일 보존 | MySQL committed/현재 RR 읽기, 기존 API commit/unknown-commit 회귀 |
| 활성 파일과 젊은 파일 보존 | 정확한 나이 경계 동등성, 시스템 시계 테스트, route/producer lease, 프로세스 IPC 및 취소 테스트 |
| 조회 실패 / 불확실한 신원 보존 | UNKNOWN/오류 테스트, 실제 NOWAIT 경합, alias/link/root/leaf 교체 테스트 |
| 오래된 미등록 publish만 제거 | 엄격한 mtime 조건 + 관리 UUID 직속 파일 + 성공한 정확한 판정 + 최종 신원 검증 |
| Runtime이 Recording 스키마를 쿼리하지 않음 | 공개 facade composition 및 변경 없는 경계 gate PASS |
| 안전/트랜잭션/경쟁/개인정보 테스트 | 위 집중 Windows/POSIX + 실제 MySQL/프로세스 증거; 원격 전체 CI 대기 |
| 참고 사항/Log/P-6 결정 | 이 문서, Recording README, 추가한 Implementation Log; Owner 인수 대기 |

PR/Owner는 거친 루트/legacy alias 보수성, mtime 구현 선택, 공통 DB/전체 writer
프로토콜 및 현재 읽기 잠금 비용을 확인한 다음 push 후 전체 통합 CI를 검증해야
한다. 이 세션에서는 staging, commit, push, PR, 외부 댓글, merge, Issue 종료,
provider/AWS 호출, workflow dispatch 또는 배포를 수행하지 않는다. RT14 변수는
변경하지 않았다. 자동 승인 검토가 provider 호출이라는 이유로 읽기를 거부하여
현재 원격 값을 다시 읽을 수 없었다. 과거 false 증거를 새 검증으로 제시하지 않는다.

<a id="owned-resource-cleanup-and-handoff"></a>

## 소유 리소스 정리와 인계

종료 전 작업 소유 MySQL 서버를 정확히 기록된 datadir로 식별했다.
감사 외 클라이언트, InnoDB 트랜잭션 및 data lock은 모두 없었다.
포트가 닫혔으며, 정확한 `/tmp/issue445-<generated UUID>` 디렉터리와 명시적으로
이름을 지정한 POSIX 테스트 임시 루트 다섯 개를 제거했다. 컨테이너/이미지는
생성, 제거 또는 재빌드하지 않았다. Windows 작업 임시 루트 열여덟 개를 제거했고
일치하는 루트는 남지 않았다. 최종 Git 감사는 인계 증거에 기록했다.
RAW/실패 원본/JSON/JUnit 및 작은 진단 스크립트는 계속 무시된 상태로 남기며,
다른 작업의 scratch/cache/image는 그대로 보존했다.
