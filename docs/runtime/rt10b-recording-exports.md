<a id="rt-10b-recording-exports--implementation-notes"></a>

# RT-10(b) Recording 내보내기 — 구현 메모

Refs #297, #47, #351. 작업일: 2026-10-29 KST.

<a id="authority-and-provisional-decisions"></a>

## 권한 근거와 잠정 결정

구현 요청의 PM 위임은 최소한의 되돌릴 수 있는 Runtime 연결 결정을 허용한다.
기존 Contract, Evidence 정책, #351 시점은 구속력을 가지며 #47 Owner 확인은
구현 전 gate가 아니라 연기된 검토다.

plate 요청은 `incident_clip_ref`, `frame_ref`, `plate_bbox_xywh`,
`max_byte_size`다. crop 식별자나 연결된 vehicle region은 사용하지 않는다.
제한은 기존 Evidence 첨부 정책(30_000_000바이트)에서 전달하며 Case가 계산하거나
해석하지 않는다. 모든 요청 필드가 fingerprint에 참여한다. Recording은 한 번의
capability 호출 안에서 한정된 PNG crop/downscale을 시도한다. 일반 실패와 출력
크기를 맞출 수 없는 실패는 서로 다른 코드를 가진다. 제한 실패에는 동일 입력
재시도 action이 없다.

Report 입력은 선택한 clip과 Evidence의 post-stamp 결정/값을 고정한다.
Case는 선택한 situation 응답 및 evidence 조립 이후, READY 이전에 입력당 한 번
export를 발행한다. command와 observation T2는 이 gate를 공유한다.

Export 입력은 별도 추가 전용 Case map과 공개 읽기 메서드를 사용한다. Worker는
짧은 트랜잭션에서 분리된 Recording 스냅샷을 미리 읽고 DB 작업 없이 정확히 한 번
export를 호출한 뒤 해당 호출 밖에서 불변 출력을 게시한다. 기존 produced receipt,
T1, reconciliation, T2가 재실행을 소유한다. 영속 T1 이전 프로세스 종료에 대해
전역 exactly-once를 주장하지 않는다.

<a id="implementation-plan-and-verification-ledger"></a>

## 구현 계획과 검증 기록

- [x] Recording 공개 capability: 실제 미디어 RED, 한정된 실패, provenance,
  실제 크기, 불변 재생성, 안전한 오류, 이후 GREEN.
- [x] 분리된 Worker 입력/context/handler와 완전한 JOB_KINDS registry:
  RED 후 GREEN; 취소와 인프라 경계.
- [x] Case #351 자동 순서, 불변 입력/fingerprint, 재시도/notice,
  현재 입력 asset projection: RED 후 GREEN.
- [x] 실제 MySQL T1/T2 롤백/COMMIT 손실, reconciliation, 중복 전달,
  취소, 재시작, 별도 API/Worker process E2E.
- [x] 집중 및 관련 회귀, 경계, Contract fixture, diff 검사.
- [x] 전체 미커밋 diff의 새 읽기 전용 검토자, P1/P2 수정/재검사.

사용자는 현재 branch와 staging/commit/push/PR 금지를 요구한다. 전체 로컬 pytest와
전체 필수 MySQL 목록은 원격 분리 CI에 남겨도 되며 생략 사항을 기록한다.
Scratch, 미디어, 자격 증명, RAW/JSON/JUnit, 임시 DB는 제외한다.

<a id="results-file-manifest-and-remaining-risks"></a>

## 결과, 파일 manifest, 남은 위험

시작 gate: branch `codex/rt10b-recording-export-handlers`, 깨끗한 tree/index,
HEAD `85dd30b91b82711a4d56bbc3ea916a3bd3c2a355`. 기존 checkout이 명시적으로
요청됐으며 worktree나 branch 전환은 없다. 구현은 새 의존성 없이 기존 Python,
SQLAlchemy, Pydantic, ffmpeg, MySQL 스택을 사용한다.

<a id="red--green-and-direct-execution-overlapping-snapshots"></a>

### RED / GREEN과 직접 실행 (겹치는 스냅샷)

| 실행 | 관측 결과 |
| --- | --- |
| Recording 최초 RED | setup 오류 10개: export 모듈 없음; 명시적 missing-capability assertion으로 반복한 실행도 10개 모두 setup에서 실패 |
| Recording GREEN | 10 passed, 15.12 s; 실제 생성 MP4/PNG, crop, limit/downscale, 불변 ref, stamp |
| Handler/order RED | 29 failed: 구현 모듈 누락 |
| Handler/order GREEN | 29 passed, 0.24 s |
| Export-input 불변성 RED | 2 failed, 12 passed: 변경/삭제가 수락됨 |
| 집중 inputs/handlers/orders GREEN | 46 passed, 0.29 s |
| 기존 notice + 최초 연결 | 39 passed, 0.31 s |
| 첫 관련 오프라인 실행 | 35 failed, 1739 passed, opt-in skip 17개, 657 deselected, 180.61 s; 통과 실행 아님 |
| sandbox 밖 native media 부분 모음 | 74 passed, opt-in skip 6개, 29.93 s; media 실패 16개가 sandbox 기본 temp 접근 때문임을 확인 |
| Entrypoint/READY 호환성 수정 실행 | 81 passed, tmp-directory 권한 setup 오류 1개, 22.18 s; 전체 GREEN 실행 아님 |
| 실제 MySQL export 결함/취소 실행 | 20 passed, 56.30 s, MySQL 8.4.13, skip/xfail 없음 |
| 별도 API/Worker process E2E | 2 passed, 82.81 s; command-triggered와 observation-T2-triggered 자동 순서 모두 |
| 경계 / Contract fixture / diff | PASS, 경계 위반 0; 구조 62 / JSON 26 / 의미 검사 104개 |

중간 실패는 무시되는 `.codex-scratch/rt10b-exports-20261029/` 아래에 별도 보존한다.
UTF-8 script decoding, OpenedDerivedAsset을 context manager로 잘못 사용한 문제,
localhost preflight sandbox 거부, FrameRef 모델 대 ref-string fixture 오류,
MySQL 불변성 query를 save 대신 insert에 실수로 배치한 문제, 잘못된 table 이름을
대상으로 한 fault probe가 포함된다. 모두 수정했으며 실패 실행을 PASS로 바꾸지 않는다.
경계 검사는 처음에 금지된 domain 단어가 포함된 report 오류 메시지를 거부했으며,
checker를 약화하지 않고 메시지를 일반화했다.

첫 관련 회귀에서는 여기서 도입한 제품 회귀 두 가지도 발견했다. export 조합이
가벼운 기존 entrypoint 테스트 설정에서 전체 RuntimeConfig를 즉시 요구했고,
observation T2는 export request port가 없는 adapter에도 불필요한 전체 view를
조립했다. 두 문제를 수정하면서 해당 adapter의 기존 READY 동작을 보존했다.
이 기록에서 전체 관련 재실행과 확장 MySQL은 pending이다.

<a id="boundaries-and-deferred-review"></a>

### 경계와 연기된 검토

- #47 Owner 연기 검토: 요청 필드 이름/버전, image output-limit 코드,
  fingerprint framing, transform 메타데이터 표현, PNG crop/downscale 전략.
  기존 `best_frame.plate_bbox_xywh`, source 소유권, Case 응답 시점, Evidence 정책
  의미는 구속력을 유지한다. crop_ref나 vehicle associated_region은 사용하지 않는다.
- Report 오류는 `REPORT_VIDEO_EXPORT_FAILED`와 기존 점 구분 notice 매핑을 유지한다.
  Plate는 `PLATE_IMAGE_EXPORT_FAILED`와 잠정
  `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE`를 구분하며 후자에는 retry action이 없다.
- Export service/encoder는 연결이나 트랜잭션 없이 분리된 불변 바이트를 사용한다.
  capability는 게시 전에 반환한다. 게시 재시도는 같은 신규 DerivedAsset과
  transform을 재사용한다. T1 결과 ref는 execution별이며 Recording ref와 별개다.
  T1/T2/reconciliation 핵심은 변경하지 않는다.
- Case 선택은 현재 전체 요청과 일치하고 성공 후 반영된 produced ref를 사용하므로
  stamp/crop/limit 변경 시 이전 출력을 조용히 선택하지 않는다. 실제 출력 크기를
  저장해 Evidence에 전달한다. Recording transform 사실이 `post_stamp_applied`를
  제공하며 Case는 요청만으로 pixel 작업을 추론하지 않는다.
- 각 E2E 단계는 새로 spawn한 OS Worker다. API는 ASGI TestClient를 사용하는 별도
  영속 child다(TCP API listener가 아님). Search HTTP/OCR은 provider 경계에서
  offline이다. Recording ref, frame, encoding, 저장소, T1/T2, MySQL은 실제다.
  Export T2를 의도적으로 롤백한 뒤 media process 없이 재전달한다.

전체 pytest, 완전한 필수 MySQL/중첩 변이 목록, 원격 CI, Linux/교차 플랫폼 ffmpeg,
실시간 provider/OCR, 대형 미디어, 배포, 영속 T1 이전 강제 process-kill은 여기서
미검증이다. 원격 분리 CI가 전체 regression/mysql/test gate를 계속 담당하며,
이 미커밋 diff에는 원격 CI 결과가 없다.
Recording 게시 후 T1 전에 프로세스가 종료되면 고아 미디어가 남고 후속 STALE
execution이 다시 인코딩할 수 있다. Exactly-once는 진입한 execution 및 커밋된
terminal 재실행별 의미이며 충돌에 안전한 전역 미디어 실행이 아니다.
새 retention 또는 정리 정책은 도입하지 않는다. PNG downscale은 가독성을 줄일 수
있으며 새 OCR/품질 판단이나 내부 바이트 목표를 부과하지 않는다.
Report stamp는 Recording의 잠정 H.264 전략 및 ffmpeg에 설치된 font와 함께 고정된
전달 시간값을 사용한다. 배포 font 일관성은 운영 위험으로 남는다.

실행 중인 검사가 끝난 뒤 최종 테스트 결과, 전체 파일 manifest, 독립 검토,
자원 정리를 추가한다.

<a id="related-regression-after-compatibility-fixes"></a>

### 호환성 수정 후 관련 회귀

`python -m pytest tests/worker tests/recording tests/case tests/common/jobs -m
'not mysql' -q -p no:cacheprovider --basetemp=<ignored task scratch>
--junitxml=<ignored task scratch>/regression-final.xml`: **1774 passed, 기존
opt-in skip 17개, 660 deselected, 134.91 s**. 이는 관련 모듈 선택 실행이며 전체
pytest가 아니다. upstream Starlette TestClient/httpx deprecation warning 하나를
보존한다. 첫 실행 실패 35개는 이 성공 재실행에서 모두 다룬다.

MySQL export 테스트 20개 실행과 process 테스트 2개 실행을 교차 확인했다.
MySQL 8.4.13; 수집/선택/JUnit 식별자가 정확히 일치하고 각각 완전한
setup/call/teardown phase 60개와 6개, skip/xfail/error/failure는 없다.
이 범위 검사로 전체 필수 목록 gate 통과를 주장하지 않는다.

<a id="expanded-mysql-and-canonical-fact-follow-up"></a>

### 확장 MySQL과 정규 사실 후속 처리

확장 선택 실행은 **56 passed, 206.21 s**, MySQL8.4.13, skip/xfail 영이었다.
export 테스트 23개, 독립 API/Worker process 테스트 2개, Case 조합 테스트 4개,
IncidentClip 테스트 9개, Readout 테스트 18개다. JSON/JUnit은 식별자 56개와
setup/call/teardown phase 168개에 일치했다. 게시/T1/T2 deadlock 롤백 및 COMMIT
ACK 손실, T2 중단/재전달, reconciliation 중단, 실제 capability 취소,
plate 일반 실패 대 크기 소진, MySQL 추가 전용 입력 강제를 포함했다.

이 실행 뒤 작성자는 직접적인 정규 AssetFacts assertion을 추가했다. 새 export는
list-case fallback에서 보였지만 직접 조회는 UNKNOWN_REF를 반환했다(**1 failing
test**). 이제 `lookup_asset_facts`는 이 새로운 export-transform 기반 class에
한해서 메타데이터/content 사실을 계산하며 기존 fixture 조회 규칙은 유지한다.
후속 집중 실행 **102 passed, 31.87 s**, 모든 export MySQL **23 passed, 55.37 s**;
후자는 정확히23/69 식별자/phase가 일치한다. 1774/56 행은 이전 소스를 기술하며
후속 변경 이후 실행으로 조용히 바꾸지 않는다. 관련 변경 동작은 직접 재실행했다.

<a id="fresh-reviewer-first-finding-and-fix"></a>

### 새 검토자: 최초 지적과 수정

검토자 한 명에게 `fork_turns=none`, 전체35-file manifest, 요구사항, SoT 포인터를
제공하고 DB/테스트 변경 없이 읽기 전용으로 배정했다.
검토자는 P2를 독립 재현했다. A export 실패 후 B가 발행되고 선택이 A로 돌아오면
보이는 A notice가 최신 B job을 호출했다. 수정은 command 처리 안에서 현재 전체
export 요청으로 retry 기준을 선택하며 기존 adapter는 이전 동작을 유지한다.
report와 plate command 회귀는 둘 다 **RED2** (clip 대신 clip-B)였고, 이후
`test_export_ordering.py` 및 `test_command.py`는 **63 passed, 0.46 s**였다.
같은 검토자가 이 차이와 전체 diff 나머지를 검사 중이다. 새 검토자나 상속된 이력의
검토는 사용하지 않는다. 여기서 최종 검토 판정은 pending이다.

<a id="final-fresh-read-only-review-and-resource-state"></a>

### 최종 새 읽기 전용 검토와 자원 상태

같은 새 검토자는 전체35-file diff와 관련 Contract를 검토하고 P2 수정을 재검사했다.
파일을 만들지 않는 `python -B` probe로 실제 execute_command를 독립 실행했다.
report와 plate는 모두 A→B→A 이후 A를 재시도했다. 같은 clip의 bbox를 변경한
StoredObservationAdapter도 probe했다. 이전 이미지는 제외하고 현재 image/report는
유지했다. **미해결 P1/P2 없음**으로 판단했다. 검토자는 pytest, DB/media 테스트를
실행하거나 모든 원시 JSON/JUnit을 감사하지 않았다.

P3 검증 개선은 연기하며 계속 드러낸다. (1) bbox/stamp 변경에 대한 운영 adapter
보정/재읽기 회귀를 영구 테스트로 남긴다. (2) 실제 stamp 프레임 pixel 변화와
비활성 시 바이트 보존을 assert한다. 이는 테스트 강도 격차이며 독립 pixel 검증을
주장하지 않는다. T1 이전 강제 process 종료, Linux/font 일관성, 대형 미디어,
전체 필수 CI, #47 최종 연결 검토는 명시적으로 판단하지 않았다.

P2 수정 후 API/Evidence 비 MySQL 회귀 **335 passed, 248 deselected, 95.34 s**,
기존 Starlette/httpx deprecation warning 하나. 앞선 sandbox 시도는 첫 API 정리
테스트에서 완료 없이 멈췄으며 확인된 작업 process ID로 종료했다. 원인은 확정되지
않았고 sandbox 밖의 같은 선택 실행은 통과했다. 새로 생성된 zero-byte 루트 정리
lock 두 개는 단독으로 열 수 있음을 검증하고 테스트 프로세스 종료 후 제거했다.
이 테스트 환경 때문에 제품이나 timeout 정책을 변경하지 않았다.

작업 소유 MySQL 컨테이너와 검사한 익명 /var/lib/mysql volume은 autocommit 감사에서
예상 밖 schema0, 다른 client0, InnoDB transaction0, data lock0을 확인한 뒤 제거했다.
컨테이너/volume 목록으로 부재를 확인했다. RAW/report와 생성된 테스트 media/env는
무시되는 작업 scratch 루트에만 둔다. 소스 트리 자격 증명/config는 생성하거나
수정하지 않았다. source helper에는 offline provider 데이터만 있다.
Scratch/media/RAW/JSON/JUnit은 전달 파일이 아니다. index/HEAD/remote 변경이나
Issue/PR 작업은 없었다.

<a id="complete-changed-file-manifest-35-files"></a>

### 전체 변경 파일 manifest (35개 파일)

- `docs/modules/case/decisions/report-video-export.md`
- `docs/modules/recording/decisions/failure-taxonomy.md`
- `docs/runtime/rt10b-recording-exports.md`
- `docs/runtime/runtime-implementation-log.md`
- `src/daesingo/api/composition.py`
- `src/daesingo/case/command.py`
- `src/daesingo/case/domain.py`
- `src/daesingo/case/exports.py`
- `src/daesingo/case/jobs.py`
- `src/daesingo/case/real_e2e.py`
- `src/daesingo/case/reflection.py`
- `src/daesingo/case/service.py`
- `src/daesingo/case/store.py`
- `src/daesingo/case/store_mysql.py`
- `src/daesingo/case/store_state.py`
- `src/daesingo/case/stored_observation.py`
- `src/daesingo/recording/README.md`
- `src/daesingo/recording/exports.py`
- `src/daesingo/recording/mysql_repository.py`
- `src/daesingo/recording/queries.py`
- `src/daesingo/recording/repository.py`
- `src/daesingo/recording/service.py`
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/export_composition.py`
- `src/daesingo/worker/export_handlers.py`
- `src/daesingo/worker/export_inputs.py`
- `tests/case/test_export_ordering.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_export_process_mysql.py`
- `tests/recording/test_exports.py`
- `tests/worker/export_support.py`
- `tests/worker/test_export_handlers.py`
- `tests/worker/test_export_inputs.py`
- `tests/worker/test_export_mysql.py`


같은 검토자의 최종 문서 차이 재검사: 미해결 P1/P2나 증거 불일치가 없다.
검토자는 두 문서의 정확한35-file manifest, 소스 수정, 변경 없는 HEAD/빈 index,
원본 Log 바이트 prefix, git diff --check를 검증했다. 검토자 파일/테스트/DB 변경은
없다. P3 테스트 강도 두 항목 및 #47/CI/운영의 연기된 경계는 명시한 대로 남는다.
최종 상태는 미커밋/unstaged이며 staging, commit, push, PR, Issue 작업은 없다.


<a id="issue-425-mixed-time-base--2026-10-31-kst"></a>

## Issue #425 혼합 시간 기준 — 2026-10-31 KST

상태 IN_PROGRESS · Refs #425 · 관련 #452, #460. 로컬 unstaged 구현.
[설계, 수치 경계와 계획](../modules/recording/mixed-timebase-plan.md)이 이 변경의
규칙 참조다. Owner 결정과 재현 댓글을 직접 읽었다.
시작 branch `codex/issue425-mixed-timebase`, 깨끗한 tree/index, 전체 HEAD
`6d8dbc9485b9060938e2036ff4874de7985bff1c`; live origin/develop은 같았다.
worktree, staging, commit, push, PR, merge, 배포, dispatch, provider/AWS,
공유 EC2 접근은 없다. 저장소 AGENTS.md는 없었으며 제공된 지침과
CLAUDE.md/문서 router를 읽었다.

<a id="author-execution-evidence"></a>

### 작성자 실행 증거

| 검사 | 관측 결과 |
| --- | --- |
| 최초 합성 RED | 개별 성공 후 혼합 clock 연결에서 네 건 실패; clock 쌍 두 개, 공개 capability 둘 다 |
| 앞선 VFR 설정 시도 | veryfast 단일 변환이 coverage를 거부함; 별도 기록하며 연결 RED에 포함하지 않음 |
| 집중 합성 GREEN | 49 passed (최종 packet-bound 테스트 세 개 이전); 정확한 source/output 프레임, 디코딩 색 순서, B-frame 이음새, 부정 대조, remux 바이트/timeout/취소 정리 포함 |
| 관련 FFmpeg 8.1 회귀 | 946 passed, 기존 opt-in/platform skip 16개, MySQL 126 deselected; Recording 및 선택한 Worker, execution, 정리 테스트; 68.94 s |
| 검증 우회 변이 | 예상 테스트 실패 두 건 (DID NOT RAISE), source-coverage guard를 메모리에서만 변이; 소스 파일은 변경하지 않음 |
| 추가 정수 경계 | RED 3 missing-helper 실패, 이후 해당 3개를 포함한 순수 연산 검사 11개 통과; 이 Windows 검사에서는 native media 실행 없음 |
| 경계/Contract/ruff | PASS: 경계 위반 없음; 구조 62, JSON 26, 의미 fixture 검사 104개; 변경된 신규 코드 lint clean |
| 실제 로컬 목록 | 사용 가능한 AVI 파일 10개를 메타데이터 우선으로 검사; 명시적 VIDEO index 0 선택, camera 역할 추론 없음 |
| 실제 적격 쌍 | 공개 AnalysisSource COMPLETE; 짧고 명시적인 실험 배치, 프레임 12개 정확히 보존, clock 1/900390, 출력 155798바이트, provenance와 원본 SHA-256/size/mtime 불변; 정리 확인 |
| 실제 strict/fallback | 성공 쌍: 최초 strict encode 두 건 성공, fallback 없음; 앞서 선택한 source는 source coverage에 실패하고 UNSUPPORTED_MEDIA 유지 |
| 원래 Issue 미디어 | 원래 AVI 아홉 파일 / MP4 두 파일 재현 세트는 확립되지 않음; 완료 증거는 미검증으로 남음 |

실제 쌍은 기존 480/ultrafast/23 설정을 사용했다. 처음 메타데이터로 선택한 쌍에 대한
앞선 480/veryfast/23 및 짧은 ultrafast 시도는 두 번째 source의 원래 frame coverage가
불연속적이어서 실패했다. 이후 source 전용 coverage 검사에서 해당 source를 거부하고
적격 쌍을 선택했다. source를 보정하거나 전체 변환하지 않았다. 좌표는 명시적 테스트
배치이며 실제 촬영 연속성을 주장하지 않는다. 공개 증거에는 원본 이름, 식별자,
경로, 프레임을 포함하지 않는다. 출력 비디오는 작업 컨테이너 tmpfs에만 존재했으며
종료 시 제거했다.

재사용 로컬 이미지는 `daesingo-issue452:local`, 실제 image ID는
`sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`다.
FFmpeg와 ffprobe 모두 8.1, GCC 12 Debian 12.2.0-14+deb12u1, libavutil
60.26.100, libavcodec 62.28.100, libavformat 62.12.100을 동일 build configuration으로
보고한다. Windows PATH 미디어 결과로 이 검증을 대체하지 않는다.
이미지에 pytest가 없어 기존 로컬 순수 Python pytest 의존성을 작업 scratch로
복사해 mount하고 plugin autoload를 비활성화했다. 이미지나 공유 cache는 변경하지
않았다. 네트워크는 비활성화하고 원본 미디어는 읽기 전용 mount했다.

보존한 중간 실패에는 pytest `py` 의존성 누락, UTF-8 수정/console 오류,
내부 필드 수정 누락, 잘못된 중첩 offset 표현식, 잘못된 테스트 전용 clip-open
메서드, B-frame 이음새 duration이 포함된다. 성공으로 바꾸지 않는다. B-frame
사례를 계기로 decode-clock projection을 분리했으며 최종 정확한 frame/packet
검증이 잘못된 offset을 탐지했다.

UNSUPPORTED_MEDIA terminal/notice 정책은 설계에 기술된 별도 Owner 항목으로 남는다.
새 Runtime 분류 체계를 추론하지 않았다. AnalysisSource와 IncidentClip은 모두 내부
미디어 수정을 물려받으며 prepared store 및 provenance 스키마는 변경하지 않았다.
DB 구현 변경이 없어 MySQL은 로컬에서 실행하지 않았다.
전체 pytest, 전체 필수 MySQL/변이 목록, 실제 원래 Issue 세트, API/Worker provider
E2E, 배포는 미실행이다. 전체 원격 통합은 별도 승인된 push 이후의 조건이며 이 작업의
결과가 아니다.

후보 파일: `src/daesingo/recording/{chain_clock,materialization,multi_analysis}.py`,
`tests/recording/{test_mixed_timebase,test_multi_span_incident_clip}.py`,
`docs/modules/recording/{mixed-timebase-plan,multi-span-analysis-source,multi-span-incident-clip}.md`,
이 Notes 파일과 `runtime-implementation-log.md`. PR 제외:
`.codex-scratch/issue425/` runner, 복사한 테스트 의존성, XML, 익명화 요약.
미디어, 원본 식별자, runtime 자격 증명은 PR에 들어가지 않는다.
새 검토, 최종 차이 검증, prefix 감사, 정리는 아래에 기록한다.


<a id="issue-425-fresh-review-and-final-delta-evidence"></a>

### Issue #425 새 검토와 최종 차이 증거

GPT-6.1 Sol / High가 구현 대화 이력 없는 새 context에서 검토하고 Issue/Owner
댓글을 직접 읽었다. P2 지적 두 건을 재현하고 수정했다. (1) 선형 깊이 setts 표현식이
약 99개 segment에서 실패했다. 균형 packet-ordinal lookup으로 이 depth 의존성을
제거했다. (2) 사용하지 않는 stream tick의 LCM이 성기지만 정확히 표현 가능한 입력을
거부했다. 이제 clock 선택은 실제 frame 및 packet timing 분모를 사용한다.
따라서 명목상 AVI-clock LCM 자체로 해당 파일이 unsupported임을 확립하지 않는다.
실제 Issue 세트 관측은 여전히 필요하며 미검증이다.

작성자 증거: depth-red 한 번 실패. flat-sum 중간 구현도 FFmpeg AVExpr depth에
실패했으며 별도 보존한다. 균형 표현식과 집중 테스트는 53개 통과했다.
성긴 public RED는 개별 변환이 모두 통과한 뒤 한 번 실패했다.
성긴 사례를 포함한 최종 집중 모음은 **54** 통과, skip/xfail 없음, 8.50 s.
새 mixed-remux 실패 테스트는 실제 cleanup scanner를 실행한다. 활성 lease가
의도적으로 오래되게 만든 파일 제거를 막고, 실패가 lease를 해제하면 정리가 진행된다.
바이트 소진, timeout, 취소는 기존 코드를 유지한다. source fingerprint와 부분 게시
부재도 검사한다.

검토자 직접 실행(작성자 XML 검토와 별개): 정확한 image 식별자, 원래 parser-depth
재현, 균형 99/101/1024-expression probe, 성긴 공개 경계 실패와 정확한 clock의 성공
반사실 대조. 마지막으로 FFmpeg 8.1에서 성긴 public, packet 정밀도, 수치 경계,
표현식 회귀 **13 passed, 22 deselected**를 실행했다. 검토자는 작성자 946-pass 및
최종 54-pass XML을 검사했고 해당 모음을 독립 재실행하지는 않았다.
코드 차이 판정: 남은 조치 가능한 지적 없음. 검토자는 비공개 미디어, DB, 원격
호스트를 사용하지 않았다. 문서 보정은 별도 최종 차이 검사로 제출한다.

`media-identity.json`은 전체 버전/configuration 및 binary hash를 기록한다.
FFmpeg `19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a`,
ffprobe `ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975`.
Notes와 Log의 기존 바이트 prefix를 SHA-256으로 검사하고 보존했다.
기존 LF 줄바꿈을 유지했다. 검토 단계 집중 재실행은 아래에 이어진다.


최종 검토 후 작성자 실행: **244 passed, 변경 없는 opt-in/platform skip 4개**,
36.66 s, FFmpeg/ffprobe 8.1. 혼합/동일 clock AnalysisSource와 IncidentClip,
단일 입력 미디어, frame-duration/tail 엄격성, budget/process 정리,
Worker limit 매핑/multisource 사용, 실제 cleanup lease를 다룬다.
실제 적격 쌍을 최종 코드로 반복했다. 정확한 프레임 12개, 1/900390,
155798바이트, 같은 provenance, 불변 source fingerprint와 temp 정리.
두 encode 모두 strict-first로 성공했으며 fallback은 없다. native PATH9.0.1
미디어 실행은 없다.


<a id="issue-425-final-local-handoff"></a>

### Issue #425 최종 로컬 인계

같은 검토자가 보정된 문서를 확인했고 남은 조치 가능한 코드/문서 지적이 없었다.
원본 Notes/Log 바이트 prefix, LF 보존, 빈 index, diff 검사도 독립 확인했다.
실제 미디어 결과 검토는 작성자의 익명 JSON만을 대상으로 했으며 직접 비공개 미디어를
사용하지 않았다. 실제 최종 파일은 `.codex-scratch/issue425/real-pair.json`이다.
앞선 검토 메시지는 이를 `real-pair-eligible.json`으로 잘못 불렀다.
중간 실제 미디어 요약은 포착한 도구 출력에서 `real-attempt-history.json`으로
재구성했다. 앞선 시도들이 동일 출력 파일 이름에 썼기 때문이다.
그 실패는 계속 보고하며 최종 PASS 주장으로 대체하지 않는다.

작업 컨테이너는 --rm, network none, tmpfs를 사용했고 잔여 작업 컨테이너는 없다.
작업 volume은 생성하지 않았다. 성공한 중간 미디어는 호스트에 남아 있지 않다.
복사한 pytest 의존성 디렉터리는 작업 scratch 아래 절대 경로를 확인한 뒤 제거했다.
남은 ignored 증거: 작은 파일 36개, 정리 측정 시 357075바이트
(XML, runner, prefix hash, 익명 요약).
공유 image/cache와 다른 작업 자료는 보존했다. C: 여유 공간은 시작 시 약 2.12 GiB,
정리 시 9283850240바이트(약 8.65 GiB)였다. 여유 공간 변화가 이 작업만의 결과라고
귀속하지 않는다.

Branch/HEAD는 `codex/issue425-mixed-timebase` /
`6d8dbc9485b9060938e2036ff4874de7985bff1c`를 유지한다. 후보 파일 열 개는 unstaged이며
index는 비어 있고 diff 검사가 통과했다. staging/commit/push/PR/merge는 없었다.
상태는 IN_PROGRESS로 유지한다. 원래 Issue AVI/MP4 재현 증거와 합의된
UNSUPPORTED_MEDIA terminal/Case notice 매핑은 열린 항목으로 남는다.
승인된 push 후 전체 원격 CI에서 정책 완화 없이 저장소 regression, strict MySQL/
변이 목록, 경계/Contract/quality gate를 실행해야 한다. 이 로컬 결과는 Issue 종결,
한 시간 분석 지원, 배포 완료를 뜻하지 않는다.


<a id="pr-499-ci-follow-up-duration-observability-2026-10-31"></a>

### PR #499 CI 후속 처리: duration 관측 가능성 (2026-10-31)

상태: IN_PROGRESS · Refs #425 · 관련 #452, #460. 시작 branch
`codex/issue425-mixed-timebase`, HEAD
`4369bdc668435d432440a77006fdb6f73538edab`, 깨끗한 worktree/index.
[원격 실패](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41185698185/job/124492062285)는
Ubuntu FFmpeg/ffprobe `6.1.1-3ubuntu5`, Python 3.12.15로
PR merge ref `8a32827548b059d1b853b5e17a3d6fb8aa33f276`를 실행했다.
실패 node는
`test_multi_span_incident_clip.py::test_different_actual_time_bases_preserve_clip_provenance`였다.

작성자는 변경하지 않은 node를 재현했다. **1 failed**, 동일한 마지막 프레임 duration
누락 오류였다. 계측 결과 두 번째 encode, 공통 clock 정규화, concat 이전에 첫 개별
encode의 `output_validate`에서 실패함을 확인했다. 원본 MP4는 프레임 20개이며
time base 1/10240에서 관측 duration은 1024다. 선택한 한 초 veryfast 출력은 프레임
10개다. 6.1.1은 모든 packet에서 duration을 보고하지 않고 마지막 디코딩 프레임에
대해서도 duration과 pkt_duration을 모두 보고하지 않는다. 이 일반 MP4에는 검증된
coverage 예외가 적용되지 않는다. 기존 #425의 개별 성공 입력 범위에서는 strict
거부가 올바르다.

동일한 합성 파일의 6.1.1 생성 버전과 8.1 생성 버전을 교차 probe하면 reader 차이를
분리할 수 있다. 6.1.1은 출력 packet 열 개의 duration 전체와 tail duration을 놓치고,
8.1은 duration 1024를 보고한다. 두 reader 모두 원본 duration을 관측한다.
이는 encoded 프레임 손실이나 concat bug의 증거가 아니다.
n6.1.1 [MOV reader](https://github.com/FFmpeg/FFmpeg/blob/n6.1.1/libavformat/mov.c#L8386-L8401)는
CTTS branch에서 packet duration을 지정하지 않는다. n8.1
[MOV 최종화](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/mov.c#L10494-L10505)는
CTTS 처리 전에 sample duration을 읽는다. trace-header 관측은 source/output H.264
time_scale 20/20480, num_units_in_tick 1, fixed_frame_rate_flag 0도 보여 준다.
n6.1.1 [duration 계산](https://github.com/FFmpeg/FFmpeg/blob/n6.1.1/libavformat/demux.c#L610-L650)에는
이 세밀한 encoder clock과 관련된 codec-rate 경계가 있다. 결정적 증거는 FPS에서
도출한 대체 duration이 아니라 측정한 frame/packet 출력이다.

최소 fixture 보정: 이 성공 테스트의 출력 profile을 ultrafast로 설정하고 source 생성
rate 10/12 및 실제 clock 1/10240과 1/12288은 유지한다.
이제 두 개별 출력 모두 양쪽 reader에 duration을 노출한다. 제품 코드, strict 검사,
fallback 범위, 수치 경계, API/Worker/receipt contract, workflow/의존성은 변경하지
않는다. 6.1.1에서 관측 불가능한 veryfast 출력에 대한 새 지원 약속은 없다.
Runtime UNSUPPORTED_MEDIA 전용 terminal/Case 매핑은 이 변경 밖의 기존 미해결
Owner 항목으로 남는다.

테스트는 이제 실제 혼합 정규화 호출을 관측하고 source/output PTS와 duration을
독립 probe하며, clock 1/60과 프레임 22개 전체의 순서를 요구한다. 한 초에서의 정확한
경계 coverage 및 두 초 endpoint를 확인하고, 디코딩된 red/blue segment 순서,
provenance, 원본 SHA-256/size/mtime 보존을 검사한다.
테스트 probe helper는 duration을 합성하지 않는다. 기존 VFR, 거부, overflow,
timestamp 변이, 동일 clock, 정리 테스트도 실행한다.

작성자 직접 결과(새 skip/xfail이나 정책 변경 없음):

| 환경 | 집중 미디어 (실패 파일 전체를 포함한 여섯 파일) | 집중 Safety/Worker (여섯 파일) |
| --- | --- | --- |
| Ubuntu FFmpeg/ffprobe 6.1.1-3ubuntu5 | 155 passed, 기존 skip 4개; 95.80 s | 88 passed, 기존 platform skip 1개; 41.97 s |
| 기존 동일 빌드 FFmpeg/ffprobe 8.1 | 156 passed, 기존 skip 3개; 29.55 s | 88 passed, 기존 platform skip 1개; 18.07 s |

6.1.1의 추가 skip은 해당 binary에서 strict encode 실패를 관측하지 않는 변경 없는
합성 AVI 테스트다. 기존 정책을 유지하며 이는 fallback 성공 증거가 아니다.
변경한 node는 두 버전 모두 통과하고 모든 정확성 assertion이 실행된다.
보정 전 작성자 8.1 진단 실행에서는 수정하지 않은 veryfast node도 통과했다.

6.1.1은 작업 전용 Ubuntu 24.04 컨테이너의 `/repo`, `/usr/bin/ffmpeg`,
`/usr/bin/ffprobe`, `/tmp/ci-venv/bin/python`의 Python 3.12.3으로 실행했다.
실제 binary SHA-256: ffmpeg
`ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41`,
ffprobe `272f6ebc634a63d9c8b4ca68e964119d980f25154e5aa2c35e5487da48e9a58f`.
8.1은 `daesingo-issue452:local`, image
`sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`를
재사용하고 `/repo`, binary `/usr/local/bin/ffmpeg`, `/usr/local/bin/ffprobe`,
`/app/.venv/bin/python`의 Python 3.12.16으로 실행했다. binary hash는 앞선 #425
증거와 일치한다. 전체 도구 식별자와 임시 Python 의존성 버전은 ignored 증거에 있다.
Python/의존성이 원격 runner와 같다고 주장하지 않는다.
Windows PATH media binary는 사용하지 않았다. native Runtime quality
(ruff 및 mypy linux/win32, 각각 87개 파일), 경계, Contract fixture (62/26/104)가
통과했다. 변경된 전체 테스트 파일에 대한 선택적 lint는 HEAD와 같은 기존 지적
17개(F401/F811 fixture import 및 E701)를 보고하며 Runtime gate는 완화하지 않았다.

현재 비공개 입력 목록은 사용자에게 남은 일곱 파일과 일치한다.
이 CI 수정에서는 비공개 미디어를 decode/reprobe하지 않았고 제거된 파일을 찾거나
복원하지 않았다. 앞선 열 파일 목록과 실제 쌍의 8.1 실행은 원래 입력/도구에 대한
과거 증거로 남으며 일곱 파일 목록에 대한 새 증거가 아니다.
여기서 pending 검증 중 제거된 입력에 의존하는 것은 없다. 측정 없이 현재 혼합
clock을 단정하지 않는다. 원래 Issue AVI-아홉/MP4-두 세트는 계속 미확인이다.

전체 후보 파일 목록: 이 Notes 파일, `runtime-implementation-log.md`,
`tests/recording/test_multi_span_incident_clip.py`. PR 제외 자료는 무시되는
`.codex-scratch/issue499-ci` 아래에만 있다. 원본 테스트 스냅샷, RED XML,
stage/cross-probe JSON, 도구 식별자, 집중 XML, runner, prefix hash다.
앞선 `.codex-scratch/issue425` 증거는 보존한다. 비공개 식별자나 프레임은 공개
문서에 추가하지 않는다. 새 검토 및 정리 결과는 아래에 이어진다.
전체 pytest, 필수 MySQL, 전체 변이, Docker OCR 인수 검사는 로컬에서 반복하지
않으며 모두 후속 승인 push의 원격 CI 조건으로 남는다.


<a id="pr-499-fresh-review-and-local-cleanup"></a>

### PR #499 새 검토와 로컬 정리

구현 대화 이력이 없는 새 GPT-6.1 Sol / High 검토자는 세 파일 차이에서 조치 가능한
지적을 찾지 못했다. 변경 node를 6.1.1과 8.1에서 직접 실행했다.
**각각 1 passed, skip 없음** (reviewer61.xml/reviewer81.xml).
작성자의 더 넓은 XML 및 진단 증거는 검토했으며 전체 집중 그룹이나 비공개 미디어를
재실행하지 않았다. source/clock assertion, strict 경계, 문서 prefix/LF,
branch/HEAD/index, diff 검사를 독립 확인했다.
코드 보정 요청은 없었다. native checker 실행은 저장소 .venv/Scripts/python.exe의
Windows Python 3.12.14를 사용했고 media 검사는 위에 기록한 Linux 도구를 사용했다.

작업 Ubuntu 컨테이너 및 설치한 의존성/중간 산출물은 제거했다.
임시 8.1 컨테이너는 --rm을 사용했다. 작업 container/volume은 남아 있지 않다.
복사한 pytest 의존성과 성공한 모든 중간 비디오는 작업 scratch 내부 대상 경로를
확인한 뒤 삭제했다. 작은 합성 source/실패 output MP4 두 개는 cross-probe 진단
재현 용도로만 작은 JSON/XML 증거와 함께 남긴다.
공유 image/build cache, 다른 작업, 원본은 보존한다. 이전 issue425 증거는
파일 36개 / 357075바이트로 남는다. C: 여유 공간은 시작 시 약 8.48 GiB,
정리 시 10903822336바이트(약 10.16 GiB)였다. 이 변화를 이 작업에만 귀속하지 않는다.

최종 후보는 위에 나열한 테스트와 추가 전용 문서 두 개 그대로이며
unstaged/미커밋 상태다. index는 비어 있고 git diff --check PASS다.
Branch/HEAD는 codex/issue425-mixed-timebase /
4369bdc668435d432440a77006fdb6f73538edab를 유지한다.
외부 쓰기, push, workflow dispatch, 배포는 없었다. 후속 승인 push 이후 전체 원격
CI가 계속 필요하며 병합 준비 완료나 Issue 종결을 주장하지 않는다.
