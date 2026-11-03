# #544 이후 청크 저장 규모 재검증 — 2026-11-03

최종 상태: **합성 media 38,359,627 B 저장·분할 조회·rollback 대조 PASS**.
담당: 정철원(Runtime/Recording). AnalysisSource/IncidentClip 각각 같은 byte 규모를 검증했다.
최초 disk 부족 및 00:52 KST RAM 부족의 RESOURCE_BUDGET_STOP을 아래에 보존한다.
00:55 KST 이후 자원 기준을 다시 충족해 실행했으며 최종 결과는 마지막 절을 따른다.
실제 영상 decode·20분 탐색·운영 acceptance 증거는 아니다.

## 시작 확인과 근거

- checkout `C:\ktc4-chonnam-2`, 브랜치 `codex/issue452-capacity-recheck`,
  HEAD `52585e38c073e48ea312c9b6510870b4bcac4d92`. 시작 working tree/staging 비어 있음.
- 로컬 `develop`과 `origin/develop`도 같은 SHA다. GitHub 읽기 조회에서
  [#544](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/544)의 merged 상태와
  merge SHA를 대조했다. head `34949d0332d221dbcbc1d65b81cc6cdacd981e5d`의 HEAD 포함을
  `git merge-base --is-ancestor` exit 0으로 확인했다. fetch/merge/rebase는 하지 않았다.
- [#530](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/530)의 merged 상태·본문·댓글을 읽고,
  merge `88e27d422246d310a17d242f933ada2939436e64`의 HEAD 포함도 exit 0으로 확인했다.
  과거 문서의 당시 미병합 상태는 수정하지 않았다.
- 사용자 제공 AGENTS.md 지침을 적용했다. 저장소 파일 검색에서는 별도 AGENTS.md가 발견되지 않았다.
  루트 `CLAUDE.md`, [문서 규칙](../../README.md),
  [구현 메모](../../modules/recording/chunked-prepared-media.md),
  [기존 실패 기록](2026-11-02-local-capacity-probe.md),
  [runner](../../../scripts/recording_capacity_probe.py),
  [MySQL focused 테스트](../../../tests/recording/test_chunked_media_mysql.py)를 읽었다.
- [P2 계획](elice-runtime-capacity-smoke-plan.md)의 0b/0c 및 §9를 적용했다.
  예산 불명·reserve 침범·DB disconnect/Aborted_clients 증가·OOM/restart·계측 누락 시 신규 부하 중단이다.

## 보존한 비교 기준

| 근거 | 당시 결과 | 이번 결과와의 관계 |
| --- | --- | --- |
| 11/02 기존 실패 | media 38,359,627 B → 실제 PyMySQL command 76,721,052 B, packet 67,108,864 B에서 저장 FAIL | 보존. 이번 성공으로 대체하지 않음 |
| #544 작성자 기록 | 각 1MiB 합성 media 저장·분할 조회·rollback·격리 복원 PASS | 과거 근거. 이번 직접 재실행 아님 |
| #544 기존 실패 규모 대조 | NOT_RUN | 이번 동일 byte 규모 합성 입력 PASS. 원래 실영상의 동일 내용 저장은 UNKNOWN |
| 과거 packet128 대조 | DB OOM·감독 timeout, 저장/재조회/rollback 결과 UNKNOWN | 재실행·원인 확정 안 함 |

## 최초 00:38 KST 자원 preflight와 예산 — 당시 RESOURCE_BUDGET_STOP

Windows/C/WSL/Docker를 읽기 전용으로 조회했다. 기본 sandbox의 CIM·WSL·Docker 접근 거부 후
읽기 전용 권한 확장 조회는 성공했다. 이는 DB 실패가 아니다.
아래 최종 preflight 시각은 **2026-11-03 00:38:18 KST**다. 각 명령은 순차 표본이며 동시 측정은 아니다.
ignored `.codex-scratch/capacity-recheck-20261103/preflight.private.json`에 숫자·자원 목록을 보존했다.

| 항목 | 직접 관측 / 계산 | 판단 |
| --- | --- | --- |
| Windows RAM | total 16,281,024 KiB / available 2,699,720 KiB | 순간 가용량. WSL RAM과 합산하지 않음 |
| Docker VM | limit 8,072,269,824 B / 18 CPU; 앞선 MemAvailable 7,008,740 KiB | Windows와 공유하는 VM 메모리. 별도 물리 RAM 아님 |
| WSL Ubuntu | 앞선 available 7,008,268 KiB / swap 사용 0 | Docker VM과 거의 같은 시점의 독립 용량으로 합산하지 않음 |
| C 실제 free | **3,383,267,328 B ≈ 3.15 GiB** | DB/volume/VHDX 성장 판단의 기준 |
| Docker 가상 디스크 논리 available | 앞선 df 1,021,439,414,272 B | 약 1TB 논리 여유가 C 물리 여유를 보장하지 않음 |
| 기존 디스크 reserve | 4,294,967,296 B (4GiB) | 이미 **911,699,968 B ≈ 0.85GiB 부족** |
| 기존 신규 실행 기준 | 6,442,450,944 B (6GiB = reserve4 + 증가 예산2) | **3,059,183,616 B ≈ 2.85GiB 부족** |
| 기존 실행 | Docker 컨테이너 전체 0개; Windows 일반 앱·WSL daemon 실행 중 | 공유 host가 전용/idle이라고 판단하지 않음 |

예산 근거는 기존 실패 기록의 **신규 실행 C≥6GiB / RAM≥2100MiB, C reserve4GiB,
disk 증가2GiB, DB data1GiB, temp512MiB**다. 이 기준을 낮추지 않았다.
#544의 작은 focused 구성은 DB512MiB + runner256MiB = 768MiB hard limit이었다.
host reserve700MiB까지 단순 합하면 1468MiB이나, 이는 대규모 peak·daemon overhead 보장이 아니다.
이번 RAM 표본은 기존 2100MiB 시작 기준을 넘지만 **disk gate가 먼저 실패**한다.

| 비용 항목 | 시작 전 계산 / 한계 |
| --- | --- |
| DB 초기화·저장·undo | 기존 보존 volume은 Docker 표시상 약119.3MB/119.3MB/152.4MB. 신규 DB의 정확한 할당량은 UNKNOWN. 기존 DB data1GiB 감시 경계 안에서 작은 시험으로 재측정 필요 |
| redo | #544 구성의 16MiB를 재사용 후보로 검토. DB data 감시/증가 예산에 포함하며 두 번 합산하지 않음 |
| runner | 기존 image 재사용·소스 ro·추가 pull/build 없이 유한 실행 후보. 256MiB는 작은 시험의 과거 제한이며 큰 입력 적합성은 UNKNOWN |
| 임시 stream | 한 개씩 열 때 media와 같은 논리 길이: 1,048,576 / 8,388,608 / 38,359,627 B. DB에는 별도 사본이 남고 rollback 후 공간 반환은 보장되지 않음 |
| 진단물·cleanup | 기존 2GiB 증가 envelope에서 DB1GiB·temp512MiB를 제외한 산술 잔여는 512MiB. 로그·sampler·VHDX 증가·정리 지연을 수용하는지 작은 시험에서 확인해야 하며 물리 quota/보장이 아님 |
| backup/restore | 이번 예산에 포함하지 않음. 큰 dump의 복수 bytes 할당·별도 target disk/RAM 예산 없이 실행 불가 |

현재는 reserve 자체가 부족하므로 **입력을 1MiB로 줄여도 신규 MySQL을 시작할 수 없다**.
공유 cache/image 삭제·WSL/Docker 재시작·기존 컨테이너 종료로 여유를 만들지 않았다.
현재 호스트에서 가능한 작은 검증은 DB를 만들지 않는 정적 검토·계산이며 아래와 같이 실행했다.

## 최초 preflight의 실행과 미실행 — 후속 DB 실행 전 기록

실행: 브랜치/포함 관계/상태 확인, 원격 PR 읽기, 자원 목록 조회,
runner·MySQL 테스트·제품 저장/조회 코드 4개 파일의 Python AST parse.
기존 `padded_mp4`의 seed 길이 **1,545 B**를 코드에서 산출했다.
이는 seed에 `free` box와 zero padding을 붙이는 방식이며 재encode가 아니다.
큰 합성 bytes나 임시 영상은 생성하지 않았다. 아래 청크 수는 기본256KiB 기준 **계산값**이다.

| 단계 | 후보 media bytes | 예상 청크 수 | 실제 DB 실행 |
| --- | --- | --- | --- |
| 작은 입력 | 1,048,576 | 4 | NOT_RUN — preflight disk gate |
| 중간 후보 | 8,388,608 | 32 | NOT_RUN — 작은 시험/예산 재확인 전 진입 불가 |
| 기존 실패 규모 | 38,359,627 | 147 | NOT_RUN — 같은 이유 |

단계별 계획은 작은 연결·계측·cleanup → 관측 예산 안의 중간 입력 → 실패 규모 대조다.
각각 새 소유 DB/volume/internal network와 유한 runner를 쓰고 session packet64MiB를 직접 확인한다.
stream을 닫은 뒤 다음 stream을 열어 temp 동시 점유를 제한한다.
기존 산출물의 존재·무결성·읽기 권한은 DB 시작 gate 뒤 확인할 사항으로 남겼고 이번에 원본/산출물을 열지 않았다.
합성 container signature 검증과 실제 영상 decode 성공은 별개다. 실제 decode는 NOT_RUN이다.

| 요청된 직접 검증 | 이번 상태 |
| --- | --- |
| session packet64MiB / command 최대 / 결과 row 크기·분할 조회 | NOT_RUN / 측정값 없음 |
| 저장 후 새 연결 길이·SHA-256 / 반환 후 checkout0 / close 후 temp 정리 | NOT_RUN |
| 같은 ref 청크 재전송 없음 | NOT_RUN |
| 유한 중간 실패·caller catch+commit·부분 publish 없음·외부 transaction 작업 보존 | NOT_RUN |
| 정상 rollback·같은 연결 안정성·Aborted_clients 변화 | NOT_RUN |
| runner/DB RSS·HWM/peak·실행 disk 증가 | NOT_RUN / UNKNOWN |
| Search/provider/Case/Web | NOT_REACHED; 전체 흐름 시험은 요청 범위 밖 |
| 큰 backup/restore·원본15개 encode·20분 탐색·AWS·배포/rollback | NOT_RUN |

과거 runner를 그대로 재실행하면 이번 목적에 맞지 않는다. 정적 코드 확인상 재조회는 새 service지만
같은 connection을 사용하고, legacy `recording_entry.content`에서 길이/SHA2를 구하며 stream 전체를
bytes로 읽는다. 이어 Search encode/guard도 수행한다. 청크 행의 legacy content는 NULL이므로
그 조회를 신규 manifest/분할 stream·새 connection 검증으로 교체한 focused harness가 필요하다.
이는 **정적 harness 적합성 판단**이며 실제 DB에서 재현한 실패나 확인된 제품 결함이 아니다.
이번에는 harness·제품 코드·기대값·strict 의미를 변경하지 않았다.

command는 PyMySQL 실제 `_execute_command` SQL 인자의 encoding 후 길이 + command byte로 측정해야 한다.
row packet은 PyMySQL packet payload 길이이며 TCP wire/전체 result allocation과 다르다.
RSS는 프로세스 resident 표본, HWM은 프로세스 전체 고수위이며 driver별 allocation peak가 아니다.
sampled max/cgroup memory/DB RSS도 구분해야 한다. 이번에는 이 값들을 수집하지 않았다.

## 보존·정리·후속 경계

기존 `issue452-capacity-db`(owner `issue452-capacity-probe`),
`issue452-chunks-restore-db`/`issue452-chunks-restore2-db`(owner `issue452-chunked-media`)는
목록/daemon 통계만 확인했다. mount/read/start/reuse/delete하지 않았다.
작업 소유 신규 컨테이너·volume·network·stream은 **0개**이므로 삭제 대상이 없다.
진단 JSON만 ignored scratch에 최소 보존했다. C free의 배경 변화는 이번 시험의 disk 증가로 귀속하지 않는다.

실험 기록과 링크만 추가했다. 제품·테스트·운영 한도·packet·Search cap·Case timeout은 변경하지 않았다.
전체 pytest/mandatory MySQL·CI 재실행은 하지 않았다. 문서 링크·비노출·기록 정합성·diff를 확인한다.
commit/staging/push/PR/외부 댓글은 하지 않으며 HEAD를 유지한다.

종료 확인은 **2026-11-03 00:40:15 KST**: Docker 컨테이너0, 기존 volume3개 목록/owner label 동일,
network는 기존 bridge/host/none뿐이다. C free3,376,988,160 B / host available2,776,596 KiB였다.
이 순간 차이를 실행 disk 증가나 메모리 회수량으로 해석하지 않는다.
문서3개의 로컬 링크22개 누락0, 예산 산술·기존 실패 본문 보존·민감 패턴 검사 PASS를 확인했다.
제품/harness diff 없음·staging 비어 있음도 확인했다. 신규 문서는 untracked로 남긴다.

00:40 KST 당시 다음 직접 검증의 첫 blocker는 **C 물리 disk 예산**이었다. 당시 약2.85GiB가 추가로 있어야
기존 6GiB 문턱에 도달하며, 다시 RAM/disk/작업 충돌을 확인해야 한다. 정리를 자동 수행하거나
여유 확보를 보장하지 않는다. 작은 DB 시험으로 실제 예산/계측/cleanup을 확인한 후 확장한다.
materializer part/최종 bytes, bytes 기반 export, 전체 dump 할당은 여전히 남은 병목이다.
작은 과거 복원 PASS를 대규모 복원 가능성으로 확대하지 않으며, 20분 지원·전체 메모리 bounded·처리량은 미검증이다.

## 00:52 KST 재개 요청 후 자원 재확인

사용자가 C 여유 확보 후 예산 충족 시 DB 검증 재개를 요청했다. 기존 승인 범위는 유지한다.
브랜치/HEAD는 위와 같고, 이전 작업의 문서3개 미커밋 변경을 보존했다.
기존 4GiB reserve·6GiB disk/2100MiB RAM 시작 기준을 낮추지 않았다.

| 2026-11-03 KST 표본 시각 | Windows available KiB | C free B | 시작 gate |
| --- | --- | --- | --- |
| 00:52:30 | 1,563,780 | 7,369,904,128 | disk PASS / RAM 미달 |
| 00:52:33 | 1,584,160 | 7,367,925,760 | disk PASS / RAM 미달 |
| 00:52:35 | 1,624,648 | 7,370,338,304 | disk PASS / RAM 미달 |

C 실제 free는 약6.86GiB로 개선됐다. Windows available은 약1.49~1.55GiB로,
필요한 2,150,400KiB(2100MiB)에 세 표본 모두 미달했다.
마지막 표본의 부족량은 **525,752KiB ≈ 513MiB**이며 직접 뺄셈한 값이다.
앞선 Docker VM available7,023,008KiB·swap 사용0·논리 disk 여유는 host RAM의 대체 예산이 아니다.
Windows 일반 앱과 WSL daemon은 실행 중이다. 프로세스 종료·공유 자원 변경은 하지 않았다.

최종 판정은 **RESOURCE_BUDGET_STOP / HOST_RAM_BELOW_INHERITED_START_THRESHOLD**다.
실제 DB 검증·통과한 최대 입력·계측값은 앞 표와 같이 NOT_RUN/없음이다.
Docker 컨테이너0·기존 보존 volume3개와 owner label을 다시 확인했고 신규 자원은 만들지 않았다.
ignored `resume-preflight.private.json`에 원 표본을 추가 보존했다.
다음 재개에는 Windows available≥2100MiB와 C free≥6GiB를 함께 다시 확인해야 한다.

## 최종 재개·실제 DB 검증 — 00:55 KST 이후

사용자의 RAM 확보 보고 후 실행 직전 다시 조회했다. 00:55:22 KST Windows available3,118,004KiB /
C free7,320,584,192B로 양쪽 기준을 충족했다. setup 직전 00:58:48 KST에는
RAM4,305,993,728B / C free10,917,609,472B였다. 배경 자원 변화가 있어 앞선 값과 합산하지 않는다.

### 격리·예산·입력

- 새 owner `capacity-recheck-20261103-db`의 MySQL·data/temp volume·internal network만 사용.
  공개 port 없음, source/root filesystem ro, image UID10001 유지. provider credential 환경 없음.
  Python socket도 전용 DB IP:3306만 허용했다.
- MySQL8.4.13, buffer pool32MiB·redo16MiB·connections12,
  binary/performance/general/slow log OFF. **각 신규 연결 session packet67,108,864B** 확인.
- DB CPU0.5/RAM512MiB, runner CPU1/RAM512MiB, 각각 memory-swap=memory로 추가 swap 불허.
  이전 작은 시험의 runner256MiB와 구분한다. 이번 runner 예산의 근거는 과거 약85MiB HWM +
  합성 생성 시 약2N(큰 입력 약73.2MiB) 동시 bytes + stream36.6MiB·escaping/cache/collector 여유라는 **추정**이다.
  DB+runner hard limit1GiB + host reserve700MiB = 1724MiB로 기존 시작 기준2100MiB보다 작다.
- runner cgroup384MiB·DB cgroup440MiB에서 soft stop, 기존 host reserve·전체 disk 증가2GiB·DB data1GiB 감시.
  runner alarm180초/host stage210초 및 Docker 호출별 timeout. host는1초 대기+조회 시간,
  runner는100ms 대기 표본이며 짧은 peak 누락 가능성이 있다.
- 기존 작업 scratch 두 곳에서 size38,359,627B 파일0개를 확인했다. 이전 work volume은 빈 것으로 기록됐다.
  기존 `padded_mp4`의 seed 뒤 `free` box/zero padding을 붙였다. 원본15개·기존 실패/복원 volume을 열지 않았다.
  재encode 없음. **합성 container signature 검증과 실제 영상 decode 검증은 별개**다.

### 세 단계 직접 결과

| 각 media bytes | 청크 합계 (두 종류) | 실제 command 최대 B | 결과 row packet 최대 B | stream chunk SELECT 수 | 결과 |
| --- | --- | --- | --- | --- | --- |
| 1,048,576 | 8 (각4) | 524,465 | 262,155 | 10 | PASS (attempt b) |
| 8,388,608 | 64 (각32) | 524,466 | 262,155 | 66 | PASS |
| **38,359,627** | **294 (각147)** | **524,467** | **262,155** | **296** | **PASS** |

큰 단계의 총 청크 content는 두 media 합계76,719,254B, 한 청크 최대262,144B다.
각 stream의 count/index 검증1회 + 개별 청크147회로 조회했다. command 최대는 publish뿐 아니라
normal rollback·세 fault 주입까지 포함한 단계 전체 최대이며, packet은 올리지 않았다.

| 직접 검사 | 세 크기 모두의 결과 |
| --- | --- |
| 새 연결 길이/SHA-256 | writer engine.dispose 뒤 다른 물리 connection ID 확인, 두 stream hash·길이 일치 |
| detached stream | 반환 후 pool.checkedout=0, Analysis service 종료 후에도 유효, offset0·seekable |
| temp cleanup | 두 stream을 순차로 열고 각각 close 후 closed 및 temp directory entries0 |
| 동일 ref 재등록 | 청크 INSERT0, 행 수 불변. metadata count 조회는 수행 |
| 정상 rollback | 신규 ref·청크·case link 없음, 동일 Connection ID·ping 성공·invalidated=false |
| 유한 중간 실패 | chunk_index1 / manifest / case link의 trigger SIGNAL errno1644 각각 확인 |
| caller catch+commit | 부분 publish 없음, 외부 transaction sentinel 작업은 commit 후 보존, 연결 유지 |
| 연결 안정성 | 단계별 Aborted_clients delta0, 최종 절대값0, OOMKilled=false·자동 RestartCount0 |

큰 입력 publish3.518초(두 media 합계), 두 stream open/hash/close1.154초는 단회 로컬 harness elapsed다.
observer/transaction 비용을 포함하며 처리량·다른 내용·동시성 성능 보장으로 확대하지 않는다.

### 실패 이력·harness 보완·독립 리뷰

첫 1MiB attempt는 저장·재등록 후 TemporaryFile **PermissionError로 FAIL**했다.
volume UID0/mode0755에서 image UID10001의 쓰기 거부를 network-none 유한 helper로 직접 재현했다.
이번 소유 temp volume만 UID10001로 바꾸고 같은 쓰기 검사 PASS를 확인했다.
첫 실패 JSON/표본은 보존하고 별도 `-b` 결과에 재실행했다. packet·기대값·strict 의미를 완화하지 않았다.
감독기가 이번 소유 DB를 정상 stop한 뒤 보완 후 같은 신규 DB를 명시적으로 start했다.
이 수동 start와 Docker 자동 RestartCount0은 별개이며 기존 보존 실패 volume의 재시작이 아니다.

독립 read-only reviewer의 감독 지적을 보완했다: setup 기준 누적 disk 증가 비교,
reserve 검사 전 표본 flush, setup DB metric 수집, 실패 시 소유 DB graceful stop,
원래 실패 runner의 증거/exit1을 확인한 정확한 이름·owner 기반 cleanup.
초기 setup은 DB metric 보완 전이었다. TCP ready 시 data127,271,335B / RSS209,928KiB /
cgroup peak275,750,912B는 얻었지만 **초기화 중 DB peak 표본은 없음**이다. 초기 host 표본17개는 보존했다.
보완된 코드를 과거 setup 전체 실행 증거로 사용하지 않는다.

offline focused controls **8 PASS**: 시작 RAM 거부, 누적 disk 증가 거부, 위반 표본 보존,
DB soft memory/data stop 및 정상 경로를 확인했다. 실제 OOM/ENOSPC는 주입하지 않았다.
reviewer는 harness·실패/성공 JSON·host 표본·cleanup 기록을 독립 대조했고 미해결 actionable 지적은 없었다.
reviewer는 Docker/DB/provider를 실행하거나 파일을 편집하지 않았다. 실제 DB는 작성자 실행 증거 검토다.
제품·tracked script/test 코드 변경 없음, 전체 pytest/mandatory MySQL/CI 재실행 없음.

### 자원 관측·cleanup·한계

| media bytes | runner RSS 표본 최대 B / ru_maxrss KiB | runner cgroup peak B | DB RSS 표본 최대 KiB | DB cgroup peak 관측 B | DB 논리 data 최대 B |
| --- | --- | --- | --- | --- | --- |
| 1,048,576 | 86,667,264 / 84,084 | 121,741,312 | 223,784 | 300,695,552 | 132,758,201 |
| 8,388,608 | 94,277,632 / 91,496 | 84,254,720 | 234,620 | 322,916,352 | 157,924,025 |
| 38,359,627 | 123,809,792 / 119,852 | 142,979,072 | 244,600 | 333,524,992 | 261,733,049 |

RSS는psutil resident 표본, ru_maxrss는Linux getrusage 프로세스 고수위다.
두 수집값의 작은 크기 역전이 관측됐으나 원인은 이번 시험에서 확인하지 않았다. 같은 정의의 peak로 취급하지 않는다.
cgroup memory.peak는 과금 메모리로 공유 페이지 등을 포함한 RSS와 다르다.
runner는 각 신규 컨테이너, DB는 명시stop/start 후 관측한 cgroup peak이며 첫 초기화 포함 전체 이력 보장이 아니다.
DB /proc VmHWM 관측 최대는 표의 RSS 최대와 같았다. driver별 allocation peak·TCP wire는 미측정이다.
command는 `_execute_command` SQL 인자의 encoding 후 길이+command byte,
row packet은 PyMySQL packet payload 길이로 전체 result allocation·TCP wire와 구분한다.

큰 입력 host표본14개에서 RAM최소3,862,216,704B / C free최소10,948,136,960B였다.
전체 host표본에서 setup 시작 대비 C free 감소의 양수 최대는3,104,768B였으나 배경 해제가 섞여
**시험의 물리 disk 증가량은 분리 불가**다. DB 표는du -sb의 논리 길이로 실제 할당 증가와 다르다.
DB ready127,271,335B→최종 관측261,733,049B의 논리 증가134,461,714B를 계산했다.
DELETE/rollback 후 DB 파일의 즉시 축소는 가정하지 않았다. reserve 침해·OOM·예상 밖 disconnect는 관측되지 않았다.

01:04:54 KST까지 exact owner/이름·성공3결과·초회FAIL 증거·정지 상태를 확인해 이번 컨테이너5개
(초회FAIL runner1/성공runner3/DB1), data/temp volume2개, network1개를 정리했다.
permission/identity helper는 network-none 유한 실행 후--rm 정리했다.
첫 실패는harness 원인을 재현하고 성공 대조를 얻었으므로 새 실패 DB를 보관하지 않고 최소JSON만 보존했다.
기존 실패DB/복원volume3개의 이름/owner는 불변, 이번 owner 컨테이너 잔수0이다.
종료RAM3,962,404,864B / C free10,942,607,360B. stream별 close 후 temp0, temp volume도 삭제했다.
ignored scratch는 집계 시 약83KB이며 계측 결과에 SQL/BLOB/credential/사용자 식별정보를 저장·출력하지 않았다.

최종 NOT_RUN: 실제 영상decode·원본 재encode·큰backup/restore·20분 탐색·provider·AWS·운영migration/배포/rollback.
NOT_REACHED: Search/Case/Web 실행. UNKNOWN: 원래 실영상을 같은 내용으로 저장한 결과,
driver allocation peak·전체 메모리 상한·처리량/동시 용량·과거packet128 결과/인과.
**최대PASS는 합성38,359,627B/1media의 DB 대조**다. 과거 실영상FAIL과 작은 복원PASS를 덮어쓰지 않는다.
materializer part/최종bytes, bytes기반export, 전체dump의 복수bytes 보유는 계속 남은 병목이다.
문서3개만 미커밋·미스테이징으로 남기며 push/PR/외부 댓글은 하지 않는다.
