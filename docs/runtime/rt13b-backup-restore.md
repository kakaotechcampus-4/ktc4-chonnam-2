<a id="rt-13b--local-logical-backup--restore"></a>

# RT-13(b) — 로컬 논리 백업 / 복원

**IN_PROGRESS · Refs #300 (RT-13(b))**

<a id="implementation-notes"></a>

## 구현 기록

### 구현 결과

`scripts/backup_compose.py`는 현재 Compose의 MySQL 8.4 `daesingo` DB만
논리 backup/restore한다. 실행 전 api·worker·migrate writer를 정지한다.
MySQL container의 기존 read-only password 파일을 container 안의 0600
client option 파일로 전달한다. secret은 argv·export된 environment에 넣지 않는다.
임시 option 파일은 operation lock 안에 만들고 shell trap으로 정리한다.

고정 파일 `logical.rt13`에는 format/database/migration heads/SQL length/SHA256
header와 SQL bytes를 담는다. 파일은 0600·exclusive create이며 기존 파일을
덮어쓰지 않는다. 실패·취소된 backup의 이번 실행 소유 파일은 제거한다.
container 안의 atomic mkdir lock은 다른 artifact 디렉터리의 중복 실행도 거부한다.
stale lock을 임의로 빼앗거나 삭제하지 않는다.

restore는 envelope와 현재 release heads를 먼저 검사하고 table/view/routine/event가
없는 target만 허용한다. 실패를 무시하는 `--force`를 쓰지 않는다. import 뒤 heads와
전체 schema/data re-dump bytes를 비교한 후에만 성공한다. 이 비교는 startup
migration보다 먼저 끝나므로 migration이 restore 실패를 가리지 않는다.

**SQL import는 atomic rollback이 아니다.** MySQL implicit DDL 때문에 실패한
target에 일부 table이 남을 수 있다. 일반 도구는 DB나 Compose 자원을 삭제하지
않는다. 실패한 target은 격리·조사하고, 자신이 소유한 disposable target을 새로
준비한다. 부분 target 재실행은 clean-target guard로 거부된다.

### Plan 대비 변경

기존 RT-13(a)의 migration→ready→HTTP smoke→강제 종료→STALE→attempt 2→
inspect→recreate 뒤에 선택적 callback을 추가했다. 기존 경로·assertion·timeout·
baseline은 유지한다. `scripts/smoke_backup_restore.py`가 callback을 사용한다.
공통 DB/migration·application entrypoint·Compose·Dockerfile·checker/gate/workflow
변경은 없다. test-only probe는 read-only mount하며 image에 넣지 않는다.

### 새로 고정된 implementation detail

| 항목 | 선택과 경계 |
| --- | --- |
| DB | Compose의 `daesingo`만. `--all-databases`/다른 DB 선택 없음 |
| client | MySQL 8.4 mysql/mysqldump; single-transaction·PK 순서·hex BLOB; comments/GTID/tablespace 제외 |
| quiescence | Compose app writer 정지. 실행자는 외부 writer/DDL도 막아야 함 |
| artifact | private 디렉터리의 고정 `logical.rt13`, 0600; durable 값 포함, Git/공유 제외 |
| integrity | length/SHA256와 release heads. 암호화/서명/악의적 교체 인증 아님. 신뢰하는 artifact만 입력 |
| release | source의 모든 module head와 현재 script가 같아야 함. release 간 upgrade/rollback은 RT-14 |
| proof | import exit 0 + heads + 전체 re-dump 동일성. API/Worker/media는 별도 actual acceptance |
| cancel | DB client별 180초, host 호출 600초. host CLI 단절 후 remote exec가 잠시 계속될 수 있고 trap/deadline까지 lock 유지; 즉시 취소/rollback 보장 없음 |

raw SQL은 integrity/DB identity 경계가 없어 envelope로 감쌌다. 물리 volume copy는
승인된 logical 범위와 달라 구현하지 않았다. dump를 memory에 수집하므로 대용량
운영 backup의 streaming/용량·보관 정책을 제공한다고 주장하지 않는다.

### Contract / Decision / Baseline 영향

- Contract 변경: 없음. HTTP·JobExecution·recording ref 의미 유지.
- Decision 변경: 없음. [#300 본문](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300)과
  [Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6433879506)을
  2026-10-28 직접 조회했다. RD-12g local logical slice만 구현한다.
- Baseline 변경: 없음. Plan RT-13/§12, Ops §4·4-1·4-2·5, Tech §4.4·15.2,
  Baseline B-W1/W4/O1/H3·§2.6·§2.10을 따른다.

### Owner 확인 포인트 / 남은 위험 / RT-14

DB backup은 **media volume 자체를 backup하지 않는다**. acceptance는 이미 있는
동일 media volume과 복원 metadata/ref/bytes 관계만 검증한다. media 손실/다른
volume 복구, 운영 일관성·RPO/RTO·retention·remote storage·자동화·EC2/OIDC/SSM·
production migration/rollback/post-deploy는 RT-14다. provider/production credential을
사용하지 않는다. mutable base/apt 입력과 grace 안 handler 완료 비보장은 (a)와 같다.

### Local 실행

먼저 [RT-13(a) Notes](rt13a-docker-compose.md)의 protected 파일 소유권/0400과
Linux host 조건을 따른다. shell에는 기존 세 파일의 경로만 설정한다. backup용
private 디렉터리는 repo/build context 밖에 0700으로 준비한다. 아래 변수는 실행자가
준비한 project 이름/디렉터리다. artifact 파일명에 사용자 정보·원본명을 넣지 않는다.

```sh
docker compose --project-name "$PROJECT" stop api worker migrate
python scripts/backup_compose.py backup --project "$PROJECT" --directory "$PRIVATE_DIRECTORY"
```

restore 대상은 별도로 준비한 **빈 disposable DB**여야 한다. 일반 예시에 기존
volume/DB 삭제 명령을 넣지 않는다. 기존 media volume을 유지하고 복구 대상에
같은 UID/GID/path로 마운트한다. overlay가 있으면 같은 `--compose-file` 목록을
순서대로 전달한다. 성공 확인 전 startup/수동 repair를 실행하지 않는다.

```sh
python scripts/backup_compose.py restore --project "$PROJECT" --directory "$PRIVATE_DIRECTORY"
docker compose --project-name "$PROJECT" up -d api worker
```

출력은 값/path/SQL 대신 고정 판정뿐이다. dump/credential을 `cat`하거나 Git에
포함하지 않는다. 전용 actual acceptance는 Linux host root로 실행하고 app은 계속
UID/GID 10001이다:

```sh
sudo python3 scripts/smoke_backup_restore.py --evidence "$PRIVATE_REPORT"
```

기존 (a) acceptance 전체 후 합성 case/upload·terminal execution ledger·recording
metadata와 모든 table 행의 identity/값/BLOB fingerprint를 준비한다. backup 뒤
이번 project의 MySQL data volume만 정확한 이름+Compose labels로 확인해 교체하고
media는 유지한다. nonempty target·collision·duplicate lock·손상/다른 dump·실제
부분 DDL 실패/재실행 거부를 검증한다. 다시 빈 DB에 restore하고 startup 전
heads/schema/data, startup 후 전체 행·CaseView·media refs/hash·Worker 새 job
처리를 확인한다. 전체 prune/공유 image cache 삭제는 없다. finally는 (a)의
project-scoped cleanup을 재사용한다. 임시 env/option/dump/probe overlay는 정리한다.
report에는 안전한 단계/개수/판정만 기록하며 실패·cleanup 실패를 PASS로 바꾸지 않는다.

<a id="verification--2026-10-28-직접-실행-중"></a>

### 검증 — 2026-10-28 (직접 실행 중)

| 구분 | 이번 세션 결과 |
| --- | --- |
| 시작 | branch `codex/rt13b-backup-restore`, HEAD/GitHub develop `071bbcca53fc7381592abcb0df7bcb3060324aa2`; clean index/worktree; #417 ancestor |
| tool RED→GREEN | missing tool 24 failed → 24 passed. fake Docker transport, actual acceptance 아님 |
| helper RED→GREEN | missing components 4 failed → deploy 전체 107 passed (7.43초) |
| boundary / Contract | 위반 0; JSON 26/의미 104 검사, 실패 0 |
| Compose 구조 | PASS, 실행 증거와 구분 |
| workflow / diff | workflow diff 없음; diff whitespace 검사 exit 0 |
| actual Docker / MySQL / review | 후속 기록으로 추가. 성공을 선취하지 않음 |
| 전체 pytest·전체 mandatory MySQL·strict CLI | 미실행. 공통 DB/migration/gate 변경이 없어 focused + actual로 한정. 최종 전체 gate는 원격 CI에서 확인 필요 |

(a) Notes/PR #417의 과거 검증 수치는 이번 직접 실행에 합산하지 않는다. 이번
RED/GREEN/report/source manifest는 gitignored `.codex-scratch/rt13b/`에 보존한다.
원본 report 재검사는 새로운 acceptance 실행으로 계산하지 않는다.

공식 옵션은 이번 세션에서 [MySQL 8.4 mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)와
[backup/recovery manual](https://dev.mysql.com/doc/refman/8.4/en/backup-and-recovery.html)을
조회했다. single-transaction만으로 외부 DDL/모든 engine 동시 일관성을 보장하지 않는다.

### 직접 actual Docker acceptance 후속 기록

Engine 29.9.2 / Compose 5.6.1 Linux host에서 이번 acceptance 한 번을 직접
실행했다. 2,198개 파일의 bytes/hash를 대조한 Linux source 사본을 사용했다.
Windows NTFS 직접 build 성공으로 표현하지 않는다. 실행 후 변경 code/test 6개가
source manifest와 동일함을 재검사했다(새 acceptance 실행이 아닌 증거 재검사).

| 단계 | 이번 실제 실행 결과 |
| --- | --- |
| (a) 회귀 9단계 | config·clean build·migration 실패 차단·clean migration/ready·upload 공유·command/view·SIGKILL→STALE→attempt2·secret/settings inspect·recreate persistence 모두 PASS |
| representative seed | HTTP case/upload·recording metadata·terminal execution ledger; 모든 table 행의 identity/값/BLOB fingerprint 준비 |
| backup | `daesingo`, 현재 module heads, 0600 envelope 생성 PASS |
| 부정 경계 | nonempty restore·기존 artifact 충돌·동일 container operation lock 거부 PASS |
| clean target | 소유 MySQL data volume만 교체; 기존 media volume 유지 PASS |
| 손상/잘못된 dump | 잘린 envelope·다른 SQL·다른 DB header 거부 PASS |
| 부분 DDL | 실제 SQL import 오류 및 부분 target 재실행 거부 PASS |
| 정상 restore | 새 빈 target import + heads + 전체 schema/data re-dump byte 동일성 PASS; startup migration 전 확인 |
| 복원 runtime/media | API healthy·CaseView 동일·전체 table 행 fingerprint 동일·같은 media volume/ref/bytes·Worker가 복원 DB의 새 test job 처리 PASS |
| 재실행 | writer 정지 뒤 새 artifact 디렉터리에 재backup PASS |
| cleanup | project containers/volumes/networks 잔여 없음, 전용 image 제거 PASS; private env·dump·override는 TemporaryDirectory에서 제거 |

원본 `docker-acceptance1.json`은 성공 stage 19개·result PASS·cleanup PASS,
failure/remaining 0을 보존한다. runtime 중 SIGTERM actual fault injection은
별도로 실행하지 않았다. cancellation artifact 처리는 focused 검증 범위이며,
SIGKILL/host power loss까지의 자동 정리를 주장하지 않는다.

### 관련 MySQL / 증거 구분 후속

전용 MySQL 8.4 container에서 migration runner·recording repository·API health
회귀를 직접 실행했다. 최초 sandbox 시도는 preflight 전에 socket errno 10013으로
차단되어 테스트 수집이 없었다. 최초 console은 대화 tool 기록에 남았지만 retry가
같은 output 파일을 사용해 별도 RAW 파일로 보존되지는 않았다. 이를 성공 실행으로
계산하지 않는다.

권한을 갖춘 실행의 원본 `mysql-focused.txt/xml`은 **85 passed / 1 failed / skip 0**,
144.24초다. 실패는 shutdown readiness helper가 Windows에서 요구하는
`DAESINGO_MYSQL_TEST_BASEDIR`/`DAESINGO_MYSQL_TEST_LIBDIR` 누락(KeyError)이었다.
기존 MySQL 8.4.7 binary/library 경로를 scratch runner에 제공한 뒤 **실패한 1개만
원래 정책으로 재실행해 1 passed**(19.92초)를 확인했다. 최초 86개 실행을 GREEN으로
소급하지 않고 별도 `mysql-shutdown-rerun.txt/xml`로 보존했다. 테스트/timeout/skip/
assertion/gate 정책 변경은 없다. 두 실행은 기존 Starlette deprecation warning
각 1개를 냈다. 전체 mandatory MySQL/strict gate는 미실행이다.

실제 acceptance seed는 12개 table·recording 6행·execution 3행이었다. 확인한 heads는
case_0001 / runtime_0005 / recording_0001이며 restore 후 startup 전에 동일했다.
후속 새 Worker job은 snapshot 비교가 끝난 뒤에 넣어 기존 값 비교를 가리지 않았다.

<a id="fresh-review-최초-판정-및-p2-tdd-수정"></a>

### Fresh 리뷰 최초 판정 및 P2 TDD 수정

이력을 상속하지 않는 reviewer가 diff·SoT·tests·증거를 읽기 전용 검토했다.
최초 판정은 **P1 0 / P2 1**: source에 procedure/function/event가 있으면 기본
mysqldump와 re-dump 모두 누락하여 schema 손실을 놓친다. 현재 migration에는 해당
객체가 없지만 정상 복원 판정을 잘못 내릴 수 있어 수정했다.

상위 정책/권한을 확장하는 대신 **backup 전에 source routines/events가 있으면
거부**한다. 실제 전용 MySQL에 procedure와 event를 각각 생성한 RED는 둘 다
exit 0(잘못 허용)이었고, 수정 후 같은 재현은 둘 다 exit 25(거부)였다. 각 테스트
객체는 finally에서 삭제했다. 영구 focused 회귀 RED2→deploy 전체109PASS(3.90초),
실제 재현은 별도 `schema-objects-red.json` / `schema-objects-green.json`에 보존한다.
이는 기존 19-stage acceptance를 소급 변경하지 않는 추가 직접 실행이다.

reviewer 직접 deploy는 최초 default-temp 권한 문제로 89PASS/18setup errors,
전용 basetemp 재실행107PASS였다. reviewer가 직접 Docker/MySQL을 실행한 결과는
아니며 원본 report를 검토한 것과 구분한다. reviewer는 소유 test 임시 디렉터리를
정리했고 source/index/GitHub를 변경하지 않았다. 동일 reviewer의 후속 판정과
수정된 code의 두 번째 actual acceptance는 완료 후 append한다.

### 수정 후 최종 직접 검증과 정리

P2 수정 후 별도 두 번째 actual acceptance를 **2,199개 파일 hash를 검증한 Linux
사본**에서 직접 실행했다. `docker-acceptance2.json`은 **19 stage PASS / cleanup
PASS / failures 0 / remaining 0**이다. 위 단계별 표와 같은 경계를 새 실행에서
모두 다시 확인했다. 첫 실행19와 두 번째19를 합산한 수치로 표현하지 않는다.
변경 code/test6개가 두 번째 source manifest와 동일함도 별도로 확인했다.

동일 reviewer의 후속 source 검토는 **기존 P2 해결 / 새 P1/P2 없음**, 독립 deploy
**109PASS**(7.05초)였다. Docker/MySQL 재실행이 아닌 source 검토·보존 증거 확인과
구분한다. 두 번째 acceptance와 최종 audit의 증거 검토 판정은 마지막에 append한다.

이번 두 smoke project의 container/migrate·mysql_data/media volumes·default network·
전용 image tag는 각각 finally에서 정리했다. 관련 MySQL 회귀는 별도의 무작위
owner label을 가진 container/data volume을 만들었고, label/정확한 이름을 재확인한
뒤 제거했다. protected password 디렉터리·credential ready 파일·Linux source 사본을
삭제하고, 이번 실행 소유 pytest temp 디렉터리8개와 reviewer 소유 temp도 정리했다.
MySQL shutdown fixture의 별도8.4.7 server는 기존 helper의 shutdown/port-closed/
정확한 UUID 디렉터리 정리 검사를 통과했다.

최종 `final-docker-audit.json` 직접 확인: **containers 0 / volumes 0**, 기본 Docker
network `bridge`/`host`/`none`만 남았다. shared base images·build cache·기존 MySQL
binary/library·다른 작업 scratch는 의도적으로 건드리지 않았다. dump/env/overlay는
임시 디렉터리에서 제거됐고 raw SQL·제품 backup artifact는 Git에 넣지 않았다.

PR 후보는 README, tool/acceptance/probe와 tests, 이 Notes/append-only Log/plan의
총10파일이다. `.codex-scratch/rt13b/**`의 RAW·JSON/JUnit·report·manifest·scratch
runner와 dump/credential/temp는 제외한다. 전체 pytest·전체 mandatory MySQL·strict
CLI 및 원격 CI는 미실행이며 merge-ready/RT-13 DONE을 주장하지 않는다.

마지막 원격 develop 재조회는 HEAD와 같은
`071bbcca53fc7381592abcb0df7bcb3060324aa2`였으므로 그 시점 재반영은 불필요했다.
branch `codex/rt13b-backup-restore`, 미커밋 변경10파일, staging 비어 있음.
commit/push/PR/Issue 변경은 수행하지 않았다.

### 동일 reviewer 최종 증거 검토

동일 reviewer가 두 번째 acceptance의 별도 project/report·exit0·19PASS·cleanupPASS,
code/test6개 hash 일치, 최종 Docker audit와 temp 부재, 정리 script/최종 문서/diff를
읽기 전용 확인했다. **기존 P2 해결, 잔여·신규 P1/P2 없음**이 최종 판정이다.
reviewer의 직접 deploy109PASS와 보존 Docker/MySQL report 검토를 구분한다.
reviewer가 실제 Docker/MySQL acceptance를 실행했다고 표현하지 않는다.

실제 취소 fault injection·전체 pytest·전체 mandatory MySQL·strict·원격 CI는
계속 미검증이다. trusted artifact·외부 writer 통제·partial DDL·remote exec 지속
제한을 유지하며, **IN_PROGRESS · Refs #300 (RT-13(b))**, 미커밋·미스테이징으로
보존한다. merge-ready/전체 gate 성공/Issue DONE 판정은 아니다.
