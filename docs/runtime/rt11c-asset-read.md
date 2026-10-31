<a id="rt-11c--stored-derivedasset-http-read"></a>

# RT-11(c) — 저장된 DerivedAsset HTTP 읽기

상태: **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))** · Related #387.
이 문서는 구현/리뷰 참고 사항이며 Contract 또는 Owner Decision이 아니다.

<a id="sources-and-prerequisite"></a>

## 출처와 선행 조건

Issue #298; HTTP Contract §3.5, §5.2, §5.5, §5.6, §7-6–§7-9;
Runtime Tech Spec §13; Provisional Baseline B-U1/B-U3/B-U4/B-F1/B-F2/§2.8;
Runtime Implementation Plan RT-11/REC-1; Recording REC-1(a)/(b)/(c) 및
현재 공개 capability를 확인했다. asset 경로는 정확히
`GET /cases/{case_id}/assets/{asset_ref}`다. cache 정책은 Contract의
`private, no-store`이며 frame 설정은 asset에 적용하지 않는다.

PR #388은 `1f830afeac93309e9ef9c8eb90fcfaced0f97ae0`로 merge됐다. 원격
[boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758821)와
[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758715)는
MySQL execution gate를 포함해 성공했다. 이는 선행 결과이며 현재 미커밋 구현의
증거가 아니다.

초기 조사는 `owns_asset`이 여전히 PAD SPACE 소유권 비교를 사용해 편집 전에
중단했다. 이후 PR #394가 `2ffd67ebcf62a974a165942c911c27468fb7f0ce`로 merge됐고,
이는 재개 시 로컬 HEAD, origin/develop 및 새 원격 develop SHA 확인과 일치했다.
[boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802597)와
[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802621)는
성공했으며 후자의 전체 pytest와 MySQL execution gate 단계도 성공했다.
Issue #387은 GitHub에서 closed/completed로 확인했다. 여기서 CI는 다시 실행하지 않았다.

사용자 지시에 따라 기존 untracked #387 계획의 내용을 읽거나 재사용하거나
편집하지 않고 `docs/superpowers/plans/2026-10-23-recording-exact-ownership.md`에서
`.codex-scratch/issue387-20261023/2026-10-23-recording-exact-ownership.md`로 옮겼다.
이동 전후 SHA-256:
`9A43517890F3DCA4306F75464525CF272EF5A0DB83A17993D733FEAE71E7EADD`.
이동 후 `git status --short`는 비어 있었으며 archive는 무시된다.

<a id="design-and-boundaries"></a>

## 설계와 경계

`ApiComposition.load_asset`은 기존 Case validator로 Case ID를 검증한 다음 기존
공개 CaseStore 존재 검사를 사용한다. 호출자 Connection에 트랜잭션 로컬
RecordingService를 만든다.
`owns_asset(case_id, ContractRef(kind='derived_asset', ref=asset_ref))`를 확인한 뒤
`open_derived_asset(asset_ref)`를 호출한다.
PR #394의 이진 정확 연관 residual과 복원 asset 신원 검사를 이 capability로
재사용하며, API에 SQL/스키마/테이블 검사를 추가하지 않는다.

읽기 실패를 포함해 callback 안에서 stream을 읽고 닫는다. Callback은 바이트와
content type만 반환하며 호출자 Connection을 commit, rollback 또는 close하지
않는다. 기존 `run_api_transaction`이 이 경계를 소유하며 타입이 지정된 오류
동작을 유지한다. Header 구성은 commit과 연결 checkin 후에만 시작한다.
ASGI send는 DB나 stream 리소스를 보유하지 않는다. 요청 취소 시 동기 읽기가
worker thread에서 마무리될 수 있지만, 그 thread는 여전히 stream을 닫고
트랜잭션을 끝낸다. 애플리케이션 소유 lifetime manager가 필요한 분리 task는 없다.

Recording은 저장 바이트/descriptor를 검증하고 실제 형식을 제공한다. API는
읽은 길이를 공개 byte size와 대조한다. 현재 지원하는 Recording 출력은 PNG와
isom MP4다. API는 실제 MIME type을 고정 ASCII 이름
`daesingo_asset.png` / `daesingo_asset.mp4`로 매핑하며, 알 수 없는 타입은
확장자를 추측하지 않고 안전하게 차단한다. Content-Length는 반환 바이트의
길이다. ref 텍스트, 원래 filename, 차량 번호 또는 locator는 header나 log에
들어가지 않는다. 형식 signature 검사는 전체 codec decode 가능성을 보장하지 않는다.

알 수 없거나 다른 소유자이거나 kind가 잘못된 참조는 `404 http.not_found`를
사용한다. Recording `UNAVAILABLE`은 `404 http.ref_unavailable`,
`TEMPORARY_FAILURE`는 `503 http.dependency_unavailable`를 사용한다.
예상 밖/검증 실패와 불명확한 commit 결과는 기존 500 동작을 유지한다.
Case 검증 실패는 404다. 오류 텍스트, traceback 및 DB 상세는 렌더링하지 않는다.

Asset은 frame permit을 소비하지 않는다. Range 요청에는 완전한 200 body를
반환한다. provider, decoder, 재생성, 생성 endpoint, Case 변경,
schema/migration, RT-10 연결, retention 또는 cleanup 정책 변경은 포함하지 않는다.
기존 불변 연관은 Recording에 구현된 대로 사용하며, 이번 작업은 동시
재할당/변경 프로토콜을 추가하지 않는다.

<a id="direct-verification-and-review-material"></a>

## 직접 검증과 리뷰 자료

변경 목록(최종 Implementation Log 항목을 포함해 15개 파일):

| 영역 | 파일 |
| --- | --- |
| API | `src/daesingo/api/app.py`, `composition.py`, `errors.py`, 새 `routes_assets.py`, `README.md` |
| Asset 테스트 | 새 `tests/api/test_assets.py`, `test_assets_mysql.py`, `test_assets_network_mysql.py`, `asset_process.py` |
| 필수 증거 | 새 `tests/asset_acceptance.py`; `scripts/check_mysql_test_report.py`; `tests/common/db/test_mysql_gate.py`; `tests/common/db/integration/test_migration_gate.py` |
| 구현 기록 | 새 `docs/runtime/rt11c-asset-read.md`; 추가한 `docs/runtime/runtime-implementation-log.md` |

현재 실행 명령, RAW 출력, JSON/JUnit 및 hash는
`.codex-scratch/rt11c-20261024/`에 보존하며 PR에서 제외한다. 테스트와 독립 필수
inventory는 버전 관리하고 checker도 일치하는 요구사항을 독립 선언한다.
중첩 actual-report mutation 테스트는 각 asset parameter, metadata 누락 및
전체 family 누락을 다룬다. Workflow 30분, 중첩 MySQL 900초, skip/xfail 거부 및
엄격한 JSON/JUnit 의미는 그대로다. 기존 checker/fixture 최적화 회귀 테스트를
유지한다.

현재까지의 직접 검증:

- PR #394 선행 조건: 선택한 실제 MySQL 테스트 33개 통과(3개 deselected).
- RED: 경로 부재로 unit 9 failed/5 passed; 실제 MySQL
  11 failed/5 passed/29 deselected. 기존 안전한 404를 기대한 테스트는 이미
  통과했으며, 이를 모든 테스트가 실패한 것으로 제시하지 않는다.
- 초기 GREEN 시도: 57 passed/2 failed. Unicode Case alias로 새 loader가 기존
  Case ID validator를 사용하지 않은 점이 드러났다. loader는 이제 이를 호출하며
  Case 모듈은 바꾸지 않았다.
- 확장 HTTP/ASGI/MySQL: 69 passed. TCP와 추가 filename/header 검사를 포함한
  최종 asset suite: 72 passed, MySQL 테스트 58개와 setup/call/teardown
  phase 174개 포함. 선택한 MySQL 테스트 모두 통과, skip/xfail 0.
- Strict checker RED: 이전 checker는 누락된 asset family 8개를 모두 잘못
  허용했다. checker 확장 후 family 검사 8개와 valid-evidence/optimization
  테스트 4개가 통과했다.
- 경계 및 Contract fixture 통과. 첫 경계 호출은 성공 줄을 출력하다 console
  encoding 오류가 났으며 Python UTF-8 모드로 재실행해 통과했다.
  이 환경 문제 때문에 checker 정책을 바꾸지 않았다.

<a id="final-execution-record"></a>

### 최종 실행 기록

아래 실행 중 모든 product/test Python 소스는 바꾸지 않았다.
선행 보고서를 현재 실행의 대체 증거로 사용하지 않았다.

| 실행 | 결과 |
| --- | --- |
| 선택 필터 없는 전체 pytest | **11,969 passed / 2 failed / 26 skipped**; pytest 시간 2,703.03 s |
| 해당 전체 실행 안의 gate unit | **8,106 passed**, skip/실패 없음 |
| 자체 반복 gate 모듈을 제외한 독립 전체 MySQL inventory | **1,004 passed / 3,012 phases / MySQL skip 0, xfail 0**; strict JSON/JUnit CLI PASS |
| 첫 중첩 자체 반복 | 변경 없는 900 s subprocess 제한에서 실패; 완전한 child JSON/JUnit 없음 |
| 격리 중첩 재확인 | child가 **999 passed / 1 failed**여서 실패; child는 900 s 안인 618.60 s에 완료 |
| 소유 임시 XML 공간 확보 후 업로드 크기 재확인 | **2 passed**, assertion/제한 동일 |
| 업로드 프로세스 중단 재확인 | **4 passed**, 시작 예산 8 s 유지 |
| 현재 actual-report mutation 본문 재실행 | **8,116 parameter mutations** 및 **1,404 metadata/family omissions** 거부; asset 부분집합 **754 + 240** |

전체 실행 실패는 정확히 다음과 같다.

1. `tests/api/test_sources.py::test_default_one_gib_exact_and_next_byte_are_streamed_without_whole_body_buffer[False]`:
   한 바이트 초과 요청이 413 대신 503을 반환했다. 같은 실패를 한 번 재현했으며,
   진단 시 여유 디스크 약 1 GiB를 관측했다. 이 작업의 완료된 gate RED 임시
   XML만 삭제한 뒤 원래 parameter 두 개가 모두 통과했다. 디스크 공간은 근거가
   있는 가설이며 확인된 errno/근본 원인은 아니다.
2. `tests/common/db/integration/test_migration_gate.py::test_actual_report_rejects_each_missing_migration_check`:
   첫 child는 900 s에 timeout됐다. 이후 격리 재확인 child는 프로세스가 살아
   있는 상태에서 기존 소유 API 시작 예산 8 s를 초과하여
   `tests/api/test_sources_interruption_mysql.py::test_owned_process_kill_keeps_file_before_row_order[before_publish]`에
   실패했다. 나중에 source나 예산을 바꾸지 않고 중단 모드 네 개가 모두 통과했다.
   실패한 중첩 실행 두 개 모두 성공으로 재분류하지 않는다.

전체 실행 MySQL 보고서는 선택 테스트 1,005개 / phase 3,015개와 실패 phase
하나(중첩 parent)를 포함한다. strict checker 결과는 **FAIL**이다.
격리된 실패 child도 checker가 거부한다. 별도 1,004-test 보고서는 새 직접
실행이며 변경 없는 strict 의미로 통과한다. 실패/성공 보고서를 이어 붙인 것이
아니다. collection skip 네 개는 관련 없는 비 MySQL Typer 의존 모듈이며 MySQL
skip이 아니다. 전체 실행 skip26개는 이 네 모듈과 사용할 수 없는 외부
video/archive 입력으로 구성된다.

중첩 child가 mutation loop 전에 실패했으므로 버전 관리된 gate 테스트의 변경
없는 mutation/assertion 본문을 현재 직접 실행한 1,004-test JSON/JUnit에 별도로
실행했다. mutation 8,116개와 omission 1,404개를 모두 거부했으며 원래
report/source SHA-256은 바꾸지 않았다. 이는 명시적으로 actual-report 재실행이며
**성공한 중첩 subprocess 인수가 아니다**. 정확한 replay helper와 수는
독립 점검할 수 있도록 scratch에 남긴다.

경계, Contract fixture(구조 62 / JSON 26 / 의미 검사 104), 기존 workflow 두 개의
actionlint 및 `git diff --check`를 통과했다. Workflow 30분, 중첩 900초,
시작 8초, 필수 inventory, skip/xfail 거부 및 기존 최적화 회귀 테스트는
보존한다. 현재 diff의 원격 CI와 완전히 통과한 전체 pytest는 확보하지 **못했다**.
중첩 인수 실패는 merge blocker로 남으며, startup/초기 timeout 원인과
CI 30분 여유는 독립 후속 조사가 필요하다. 이 실패를 green으로 만들기 위해
upload, startup, cleanup 또는 CI 정책 소스를 바꾸지 않았다.

<a id="resources-and-handoff"></a>

### 리소스와 인계

소유 MySQL 8.4.7 프로세스 두 개와 helper 프로세스가 모두 종료됐다.
생성한 `/dev/shm/rt11c-<uuid>` datadir 두 개를 모두 제거했고 Linux 포트는
연결을 거부했다. 최종 Windows netstat에는 두 소유 포트의 항목이 없었다.
최종 검증 전의 Windows connect 검사는 실패했으며, 정확한 원인은 입증되지
않았고 실패를 보존한다.

종료 전 감사 두 번 모두 감사 외 client, transaction 또는 data lock이 없었고
기본 계정 네 개만 있었다. 첫 서버의 clean-schema assertion은 강제 timeout된
pytest가 일회용 테스트 스키마 하나를 남겨 실패했다. 서버 finally block은
소유 datadir 전체를 여전히 제거했다. 두 번째 서버의 스키마 다섯 개 감사는
통과했다. assertion 실패나 정리를 첫 감사 성공으로 보고하지 않는다.
공유 WSL/relay 서비스는 바꾸지 않았다.

테스트가 만든 저장소 루트의 zero-byte cleanup lock artifact 두 개는 모든
DB/process 테스트가 끝난 뒤 hash를 기록하고 제거했다. Source/증거 snapshot,
RAW, JSON/JUnit, mutation inventory, runner, CA/log 및 archive한 #387 계획은
PR에서 제외한다. 개인 원본 video는 추가하지 않았다. endpoint는 저장 바이트를
메모리에 buffer하며 새 streaming/size 정책이나 전체 codec 검증 보장을
도입하지 않는다. 기존 선행 cleanup/disconnect/import-watchdog 불확실성이
해결됐다고 주장하지 않는다.

이 구현 대화에는 reviewer/subagent, commit, staging, push 또는 PR 생성 권한이
없다. 독립 재리뷰는 미커밋 diff와 추가한 최종 기록의 증거/한계에서 시작해야 한다.


<a id="p2-follow-up--2026-10-24-incomplete-observation-semantics-pending"></a>

## P2 후속 조치 — 2026-10-24 (미완료; 관측 의미 대기)

상태는 **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**로 유지한다. 앞선
실행 기록은 과거 기록이며 전체/중첩 실패는 그대로 실패다.
이번 후속 조치에서는 P2 수정 두 개나 최종 인수를 모두 완료하지 못했다.

| 항목 | 이번 후속 조치의 직접 증거 |
| --- | --- |
| P2-1 제품 RED | `p2-red-network`: 1 failed, 구체적으로 body-send OSError 후 `api.asset.bytes` 및 `api.asset.download_latency_ms` 부재. 테스트는 실제 body send가 보류 중일 때 공통 `api.request.completed(status=200)`가 있음을 먼저 입증한다. 공통 이벤트나 제품 관측 동작은 바꾸지 않았다. |
| P2-1 미정의 의미 | Plan §RT-11과 Baseline은 두 이벤트 이름만 나열한다. 공통 logging은 `status`, `count`, `duration_ms`를 허용한다. Frame은 FAILED/CANCELLED를 사용하지만 disconnect와 send error를 구분하지 않는다. 사용자는 확장 전에 정의되지 않은 이름/의미를 보고하도록 요구했다. 종료 상태 네 가지와 성공적으로 반환된 ASGI-send payload 바이트에 대한 명시적 질문이 대기 중이다. schema/의미를 몰래 만들어내지 않았다. 새 제품 테스트는 의도적으로 계속 RED다. |
| P2-2 음성 대조군 | `tcp-negative`: scratch 전용 plugin이 FlowControl.drain을 즉시 반환하게 하면 “no actual downstream drain wait observed”에서 1 failed. 진입/완료한 send만으로는 인정하지 않는다. |
| P2-2 GREEN | 초기 실제 TCP probe 통과; 엄격한 `ASGI ended >= transport disconnect observed` 순서를 추가한 뒤 `tcp-order-green`: 1 passed. Socket send/receive buffer와 transport watermark는 제한되며 실제 Uvicorn drain task는 scheduler 한 회전 후에도 보류 중이어야 한다. server loop의 snapshot으로 body send 보류, lifetime 미종료, write paused, checkout 0을 입증한다. 이후 client close가 transport disconnect와 요청 종료를 일으켜야 한다. 모든 Uvicorn request task/connection과 server thread가 종료돼야 한다. 기존 payload 크기와 timeout은 유지하며 asset/frame permit은 도입하지 않았다. |
| 독립 회귀(최종 인수 아님) | `independent-regression`: 129 passed, 실제 MySQL 테스트 58개 / phase 174개 포함, skip/xfail 0. Asset HTTP/ASGI/TCP/MySQL 및 Frame lifetime, 공통 access 관측, API cleanup. P2-1의 알려진 RED 파일은 명시적으로 이 독립 실행 밖에 있다. |
| 구조 검사 | 경계 PASS (0); Contract fixture PASS (62/26/104); workflow 두 개 actionlint PASS; diff 검사 PASS. Workflow 30분, 중첩 900초, 시작 8초, inventory 및 strict 정책은 그대로다. |

<a id="failure-investigation-facts-and-unavailable-historical-evidence"></a>

### 실패 조사: 사실과 확보할 수 없는 과거 증거

- **Upload 503:** 원래 실패한 `[False]` 테스트의 계측 실행 한 번은 통과했다
  (1 passed, 7.38 s). `_storage_call` 주변 scratch 계측은 각
  open/finish/close/publish 경계, 실제 staging/source 크기, 디스크 여유 및
  발생한 모든 예외의 traceback/errno capture를 보존했다. OSError는 없었다.
  여유 공간은 시작 시 7,740,743,680바이트, 두 번째 요청 전에는
  6,664,900,608바이트였다. 정확한 크기 요청은 저장 payload
  1,073,741,694바이트를 finish/publish했다. 한 바이트 초과 요청은 staging을
  열었고 parser.finish/publish에는 도달하지 않아 기존 413 assertion 통과와
  일치했다. 과거 실패의 원래 errno/traceback 및 disk/staging 상태는 수집되지
  않았고 재구성할 수 없다. 디스크 압력은 가설이며 확인된 원인이 아니다.
  Upload receiver/body-limit/publication 소스에는 diff가 없다. RT-11(c)는
  GET 경로와 loader만 추가하지만 직접 upload diff가 없다는 사실만으로
  timing/resource 영향을 배제할 수는 없다.
- **Nested 900 s:** 과거 timeout에는 명령과 parent traceback이 보존돼 있지만
  node별 실시간 trace, child PID 또는 완전한 child 보고서는 없다.
  timeout 당시 마지막 완료/활성 node와 child DB/bootstrap/import/cleanup/relay
  상태는 입증할 수 없다. 과거 프로세스 상태를 만들어내지 않는다.
- **Startup 8 s:** 원래 `before_publish`의 집중 계측 실행 한 번은 통과했다
  (1 passed, 5.14 s; call 4.0176805 s). launcher PID 22780,
  interpreter PID 35332, poll 상태, import/function trace 및 stdout/stderr를
  보존했다. Interpreter-site부터 첫 API import까지는 0.797 s였으며,
  create_app은 613510.531에 시작, bootstrap은 613510.578에 반환,
  compose_api는 613510.781에 반환, create_app은 613510.921에 반환했다.
  이 timestamp는 통과한 이번 계측 실행만 설명한다. 처음 도달 가능한 listener
  뒤에 checkpoint와 소유 프로세스 kill이 이어졌으며 startup timeout이나 예상
  밖 오류는 재현되지 않았다. Cleanup.start는 thread에서 실행되고(이 main-thread
  profile 범위 밖), relay scheduling은 별도로 계측하지 않았다. 따라서 이전의
  >8 s 구간과 900 s timeout의 관계는 확인되지 않았다. 제한은 그대로였다.
- **Inventory 실행 시간 기여(과거, 측정값):** 보존한 실패 중첩 child의 JUnit은
  testcase 합계613.385 s / pytest 실시간618.60 s 중 asset 테스트58개에
  testcase 합계45.957 s를 배정한다. asset이 없는 반사실적 실행이 아니며,
  두 제한 중 어느 것의 원인인지도 입증하지 않는다.
- **별도로 유지하는 새 harness 문제:** 제한된 실행 환경의 초기 minimal-RED
  시도 두 번은 테스트 coroutine 전에 정체됐다. 저장한 5초 faulthandler stack은
  fallback socketpair.accept의 Windows asyncio loop 생성이다. 정확한 테스트
  command/PID로 중지했으며 제품 RED로 세지 않는다. loopback 활성화 실행이
  위 실제 제품 RED를 만들었다. 과거 startup timeout의 원인을 입증하지 않는다.

<a id="remaining-work-and-acceptance-boundary"></a>

### 남은 작업과 인수 경계

P2-1은 대기 중인 event/field 의미 결정 후 구현,
네 결과/bytes/latency/privacy/error/non-asset 회귀 GREEN 및 제품 음성 대조군이
필요하다. 현재 minimal 테스트는 계속 RED다. P2-2 테스트 개선에는 직접 음성
대조군과 실제 network 증거가 있지만 두 수정이 함께 완료된 것은 아니다.
따라서 이번 후속 조치에서 **final whole pytest = 0 runs; final nested = 0
runs**다. 최종 strict unit/mutation/JSON/JUnit 인수도 대기 중이다.
요청한 정확히 한 번의 최종 실행을 소모하지 않았고, 독립 129-test 실행이나
과거 증거로 대체하지 않았다.

남은 merge blocker는 P2-1, 최종 인수 및 과거 전체/중첩 실패의 미확인 원인이다.
기존 비차단 한계(전체 asset 메모리 buffering, 선택적 외부 video/archive 검증,
best-effort event sink)는 위에 계속 문서화한다. 독립적으로 새 P1으로
재분류한 P1 리뷰 지적은 없다.

<a id="resource-and-pr-exclusion-record"></a>

### 리소스와 PR 제외 기록

소유 MySQL 8.4.7 server/helper는 종료됐고 정확히 생성한 datadir는 제거했으며
Linux connect는 111을 반환했다. 종료 감사: system+base schema만 존재,
기본 계정 네 개, 감사 외 client, transaction 또는 data lock 없음.
Windows 정리에서 소유 테스트 Python 프로세스와 listener/활성 TCP 연결은
발견되지 않았다. 해당 snapshot에 TIME_WAIT 항목57개가 남았다(PID 0이며 활성
DB checkout이 아님). TCP 테스트는 request-task/connection/server-thread
정리를 검증한다. 루트 cleanup lock artifact는 남지 않았다.
RAW/JSON/JUnit/trace를 보존한 뒤 소유 진단 임시 디렉터리를 제거했다.
공유 WSL/relay 서비스는 건드리지 않았다.

`.codex-scratch/rt11c-p2-20261024/` 아래 모든 scratch 자료(변경 전 source
snapshot, 원래 RED, 음성 대조군, 진단 및 manifest 포함)는 PR에서 제외한다.
앞선 scratch 증거와 #387 archive 계획은 재사용/수정 없이 보존한다.
staging, commit, push, PR 또는 reviewer/subagent 호출은 없다.


<a id="current-complete-changed-file-inventory-16-files"></a>

### 현재 전체 변경 파일 목록 (16개 파일)

- `docs/runtime/runtime-implementation-log.md`
- `scripts/check_mysql_test_report.py`
- `src/daesingo/api/README.md`
- `src/daesingo/api/app.py`
- `src/daesingo/api/composition.py`
- `src/daesingo/api/errors.py`
- `tests/common/db/integration/test_migration_gate.py`
- `tests/common/db/test_mysql_gate.py`
- `docs/runtime/rt11c-asset-read.md`
- `src/daesingo/api/routes_assets.py`
- `tests/api/asset_process.py`
- `tests/api/test_asset_lifetime.py`
- `tests/api/test_assets.py`
- `tests/api/test_assets_mysql.py`
- `tests/api/test_assets_network_mysql.py`
- `tests/asset_acceptance.py`


<a id="owner-approved-p2-implementation--2026-10-24"></a>

## Owner 승인 P2 구현 — 2026-10-24

상태: **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**.
앞선 P2 의미 대기 기록은 보존한 이력이다. 이번 후속 조치에서 직접 가져온
[Runtime/Ops Owner 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6380891047)로
결정은 이제 해결됐다.

<a id="implementation-notes"></a>

### 구현 참고 사항

- 전용 pure-ASGI AssetLifetimeMiddleware는 정확한
  GET /cases/{case_id}/assets/{asset_ref} 요청(root_path 포함)에 대해
  access/BaseHTTPMiddleware를 둘러싼다. semaphore, database operation,
  provider 호출, generation 인터페이스, Case/Recording/schema/migration 또는
  retention 정책을 추가하지 않는다. 기존 소유권과 호출자 트랜잭션 loading은
  그대로다.
- download_latency_ms.duration_ms는 외부 진입부터 최종 downstream body send의
  반환 또는 예외/취소 종료까지의 단조 증가 시간을 사용한다.
  정상적인 final 이후 애플리케이션 정리는 download duration을 연장하지 않는다.
- api.asset.bytes는 **성공적으로 반환된 downstream send 바이트이며, client가
  수신한 바이트가 아니다**. 정상 반환된 partial send와 오류 응답 바이트를
  포함하고 실패한 chunk는 제외하며 Content-Length는 절대 사용하지 않는다.
  client 수신이나 TCP ACK가 아니다. 서버는 client disconnect 후에도 정상 반환할
  수 있다.
- 일치하는 요청마다 기존 bounded best-effort ApiEvents를 통해 각 종료 metric을
  정확히 한 번 시도한다. 정상 완료는 실제 HTTP status 텍스트, 모든 예외는
  FAILED, task cancel 또는 final body 없음은 CANCELLED를 사용한다.
  DISCONNECTED 상태나 새 logging field는 추가하지 않는다. middleware는 HTTP
  status를 재작성하지 않고 raw case/ref/filename/locator/error 텍스트를 포함하지
  않는다. 서버 발급 trace는 asset에 한해 공통 access event와 공유하며,
  api.request.completed는 전역 response-creation 의미를 유지한다.
- 실제 MySQL send 종료 사례는 이제 이 metric을 검증한다. 새 partial_failure
  parameter는 세 바이트 chunk의 성공 뒤 send가 실패하면 count=3을 요구한다.
  필수 inventory는 독립적으로 asset 테스트59개로 확장하며,
  checker cache/copy 최적화와 기존 strict 정책을 모두 유지한다.

<a id="direct-verification-before-the-single-final-whole-run"></a>

### 단 한 번의 최종 전체 실행 전 직접 검증

- 기존 branch/HEAD와 16파일 source SHA-256 manifest는 정확히 일치했고,
  staging은 비어 있었으며 보존한 #387 계획 hash도 일치했다. 이전 단계는 전체
  RAW/JSON/JUnit hash manifest를 제공하지 않았으므로 모든 증거 바이트의 과거
  동일성을 주장하지 않는다. 재개 시 원래 top-level/child artifact158개를 별도로
  hash하고 동결했다. mutation XML 재귀 읽기는 과도한 I/O로 중단했으며 해당
  XML 파일은 바꾸지 않았다.
- 초기 제품 RED: 24 failed. 스무 개는 metric 부재 assertion까지 도달했고,
  정상 경로 네 사례에는 test-helper 반환값 실수도 있었다(request는 None이
  아니라 messages를 반환). 초기 GREEN 시도: 20 passed / 해당4개 failed.
  제품 metric을 우회한 수정 assertion은 metric 부재로 정확히 24 failed;
  같은 assertion에 구현을 적용하면 24 passed. 모든 원시 결과를 보존한다.
- 확장 집중 최종 source: 166 passed, 실제 MySQL 테스트59개 /
  phase177개 포함, MySQL skip/xfail 0. incomplete/cancel/fatal 종료,
  정확한 final-send timing, 오류 HTTP status, partial bytes,
  ownership/정확한 신원, commit/checkin, send cancellation 및 실제 TCP
  backpressure/disconnect, 기존 Frame lifetime/access 관측/API cleanup 회귀를
  포함한다.
- 새 strict-parameter RED: 이전 checker가 partial_failure의 완전 삭제 또는
  node/parameter metadata 누락을 허용해 3 failed / 8 passed.
  독립 inventory 확장 후: 11 passed.
- 아래 전체 선택 필터 없는 pytest 호출은 중첩 MySQL gate를 정확히 한 번
  포함한다. 독립 중첩 재실행은 계획하지 않는다. 실패한 최종 호출은 실패로
  남기며 재실행하거나 성공 결과와 이어 붙이지 않는다.


<a id="final-exactly-once-execution-and-independent-handoff"></a>

### 최종 정확히 한 번 실행과 독립 인계

| 최종 source 실행 | 전체 결과 |
| --- | --- |
| 전체 선택 필터 없는 pytest, 한 번 호출 | **12,016 passed / 3 failed / 26 skipped**; pytest 2,099.93 s; startup/report 완료 포함 runner 2,125.828 s |
| 전체 실행 MySQL inventory | **1,006 tests / 3,018 phases, 모두 passed**, MySQL skip/xfail 0; strict JSON/JUnit CLI **PASS** |
| 전체 pytest 안에서 한 번 호출한 중첩 child | **1,001 passed / 3,003 phases**, skip/xfail 0; 변경 없는 900 s 아래 pytest 597.26 s; strict JSON/JUnit CLI **PASS** |
| actual-report mutation을 포함한 중첩 parent | **PASS**, call 819.498782 s(child 및 strict/mutation assertion); 두 번째 child 호출이 아님 |
| 전체 실행의 strict gate unit | **8,117 passed** |
| 전체 실행의 asset 테스트 | **109 passed**, 실제 MySQL 테스트59개 포함; 독립 집중 실행은 166 passed로 유지하며 전체 수에 합산하지 않음 |
| actual-report 부정 증거 | **8,129 parameter mutations + 1,408 metadata/family omissions 거부**; asset 부분집합 **767 + 244** |

전체 실행 실패는 보존하며 집중 PASS 또는 MySQL PASS로 대체하지 않는다.

- `tests.api.test_process_safety::test_keyboard_interrupt_distinguishes_startup_from_serving[server-0]`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')
- `tests.api.test_process_safety::test_cli_cleanup_failure_is_quiet_and_restores_signals[RuntimeError]`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')
- `tests.api.test_process_safety::test_actual_server_cleanup_failure_exit_and_listener_release`: Failed: owned child exceeded 5s (stdout=b'', stderr=b'')

세 개 모두 stdout/stderr가 빈 상태로 기존 **5초 전체 child-process deadline**에
실패했다. parent traceback과 원래 child source는
full.raw/full.xml/full-failures.txt에 보존한다. 이 `-c` child 세 개에는 phase별
trace가 없어 import/startup/cleanup 위치와 RT-11(c)와의 인과 관계는
**미확인**이다. asset GET을 수행하지 않지만 이 source에는 새 import와 app
연결이 존재한다. 이 사실만으로 timing 영향을 입증하거나 배제할 수 없다.
이 실패 후 source/timeout/assertion 변경, 단독 재시도 또는 두 번째
전체/중첩 호출은 없었다. MySQL report gate 두 개가 통과해도 이번 전체 실행은
**FAIL**이며 계속 **merge blocker**다.

skip26개는 Typer 의존 collection 모듈 네 개와 사용할 수 없는 외부
video/archive/명시적 opt-in 입력22개다. 선택 MySQL skip은 없다.
이전 전체 503/900 s 실패 및 실패한 중첩 8 s startup은 과거 실패로 남긴다.
누락된 원래 errno/phase별 증거는 재구성할 수 없다. 현재 업로드 크기 테스트와
업로드 프로세스 중단 두 집합은 모두 통과했지만 과거 원인이 해결됐음을 입증하지
않는다. 기존 단일 호출 upload/startup 진단 결과는 앞선 P2 기록에 보존한다.

**환경 정정:** compact.exe는 소유 full-temp 디렉터리에 상속 NTFS compression을
표시했다. 이는 text report뿐 아니라 fixture 파일에도 영향을 주었으며,
“text evidence only”라는 runner 주석은 너무 좁은 설명이었다. 논리 media 바이트와
assertion은 그대로지만 물리 disk allocation/pressure는 다르다. 이번 전체 실행은
이전 디스크 압력 조건을 재현했다는 증거가 아니다. 공유 디렉터리, MySQL datadir
또는 production/CI 정책은 바꾸지 않았다. diagnostics plugin은
progress/PID/stdout/stderr와 선택적인 6초 owned-child stack만 기록한다.
테스트를 select/deselect하거나 예산을 바꾸지 않는다.

최종 실행 내내 **버전 관리/untracked Python source hash583개**가 모두 같았다.
**재개 시 고정한 원래 artifact hash158개**가 모두 유지됐으며 archive한 #387
계획 hash도 계속 일치한다. 이전 보고서와 새 전체/중첩 JSON/JUnit을 이어 붙이거나
편집하지 않았다. 전체/중첩 호출 원장은 정확히 **1 / 1**이다.
Workflow 30분, 중첩 900 s, 소유 업로드 startup 8 s, process-safety 5 s를
유지하며 inventory, skip/xfail, JSON/JUnit 의미 및 gate 최적화를 약화하지 않았다.

**현재 diff의 원격 CI는 실행하지 않았다**. staging, commit, push 또는 PR 생성이
없다. Windows 로컬 전체 실행2,099.93초는 30분을 초과하지만 Ubuntu CI runner를
측정한 것은 아니다. CI 30분 여유는 미검증이다. 선행 PR #388/#394 원격 성공은
선행 조건 이력으로만 유지한다.

**정리:** 소유 MySQL 8.4.7/helper 종료; 정확히 생성한 datadir 제거;
Linux port 연결 거부. 종료 감사에는 system schema 네 개 + base 하나,
기본 계정 네 개, 감사 외 client/transaction/data lock 없음이 기록됐다.
Native Windows 감사에는 auditor/launcher 프로세스 두 개만 있고 살아남은
test child는 없었다. 소유 포트 활성 connection/listener0개, 해당 snapshot의
PID-0 TIME_WAIT 항목209개였다. 실행 후 강제 Python kill은 필요하지 않았다.
TCP 테스트는 request task, drain task, connection 및 server thread 정리를
검증한다. 새로 생성된 zero-byte 루트 cleanup lock 두 개는 모든 프로세스 종료 후
hash를 기록하고 제거했다. 원래 보고서, mutation inventory 및 JSON interruption
증거를 보존한 뒤 소유 임시 테스트 tree를 제거했다. 공유 WSL/relay 서비스는
건드리지 않았다.

**Merge blocker:** 미해결 전체 실행 process-safety 실패 세 개와 미확보한 현재
diff의 원격 CI. P2-1 의미/구현 차단은 해결됐으며, P2-2는 현재 source 실제 TCP와
MySQL 회귀 증거를 갖췄다. 알려진 비차단 한계는 전체 asset 메모리 buffering,
bounded best-effort event delivery 및 사용할 수 없는 외부 media/archive 검증이다.
client 수신/ACK는 승인된 metric 의미 밖이다. 과거 timeout/disk 원인이 해결됐다고
주장하지 않는다.

PR 제외 증거는 `.codex-scratch/rt11c-owner-20261024/`에 있다.
Owner 승인, resume/frozen/review hash, RAW, JSON/JUnit, 실패 child traceback,
progress, mutation inventory, process/DB cleanup, runner 및 snapshot이다.
이전 scratch와 #387 계획은 계속 제외하며 건드리지 않았다. reviewer/subagent는
호출하지 않았다. 상태는 **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**로 유지한다.


<a id="complete-final-changed-file-inventory-17-files"></a>

### 최종 전체 변경 파일 목록 (17개 파일)

- `docs/runtime/runtime-implementation-log.md`
- `scripts/check_mysql_test_report.py`
- `src/daesingo/api/README.md`
- `src/daesingo/api/app.py`
- `src/daesingo/api/composition.py`
- `src/daesingo/api/errors.py`
- `tests/common/db/integration/test_migration_gate.py`
- `tests/common/db/test_mysql_gate.py`
- `docs/runtime/rt11c-asset-read.md`
- `src/daesingo/api/asset_lifetime.py`
- `src/daesingo/api/routes_assets.py`
- `tests/api/asset_process.py`
- `tests/api/test_asset_lifetime.py`
- `tests/api/test_assets.py`
- `tests/api/test_assets_mysql.py`
- `tests/api/test_assets_network_mysql.py`
- `tests/asset_acceptance.py`


<a id="process-safety-root-cause-investigation--unresolved-2026-10-24"></a>

### Process-safety 근본 원인 조사 — 미해결 (2026-10-24)

상태는 **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**로 유지한다. 이번 조사를
위해 product, fixture, test assertion, child 5초 제한, sleep, workflow 또는
gate를 바꾸지 않았다. 이 문서와 implementation log에만 후속 기록을 추가하며
전체 PR 후보 목록은 17개 파일로 유지한다.

**재개 검증:** 조사 전 브랜치 `codex/rt11c-derived-asset-read`, HEAD
`2ffd67ebcf62a974a165942c911c27468fb7f0ce`, 빈 staging, 동일한 후보 경로17개와
hash, 인계 증거 hash115개 및 앞선 증거 hash158개가 모두 일치했다.
원격 develop은 직접 읽은 결과 `a89a57020f36d7bfef1d62e1af8ba9ef9a28627a`였으며,
HEAD와 다른 변경은 Case decision 문서 두 개뿐이었다. dirty checkout을
switch/reset/stash하지 않았다. 별도 `git archive` snapshot을 사용했다.
하나는 HEAD에 정확한 현재 17파일 overlay를 적용한 것이고 다른 하나는 깨끗한
원격 develop이다. 동결 Python hash583개가 모두 현재 snapshot과 바이트 단위로
일치했으며 실행 후에도 모든 snapshot file hash가 일치했다. Process-safety
테스트, CLI, API events, common logging, frame lifetime 및 storage cleanup은
두 snapshot 사이에 바이트 단위로 동일하다.

원래 전체 raw log, JUnit 및 progress 기록에서 테스트 순서와 기록된 실행 환경을
포함해 읽었다. 실패 세 개 모두 Windows `subprocess.py:1630`에서 발생했다.
`_communicate()`가 남은 deadline까지 **stdout reader**를 join했으나 여전히
살아 있었다. 이후 `process.wait()`에서 timeout된 것이 아니다. 테스트의
kill/reap 후 두 pipe는 모두 비어 있었다. 표시된 `Popen returncode=1`은 정리 후
traceback 표현이며 kill 전 child 상태를 입증하지 않는다. 해당 `-c` child
세 개의 과거 phase/stack/PID 증거가 없으므로 빈 출력으로 내부
import/startup/cleanup/atexit phase를 복구할 수 없다. 원래 전체 결과는
**12,016 PASS / 3 FAIL / 26 SKIP**로 유지한다.

Scratch 전용 진단은 child source에 파일 전용 phase 관측을 추가한 것 외에는
같은 `Popen` 인수, 원래 assertion 및 `communicate(timeout=5)`를 유지했다.
parent spawn/communicate, 두 pipe reader와 wait, 실제 interpreter PID,
import별 및 top-level/local statement 경계, 선택한
main/composition/cleanup/server 호출 및 atexit 진입/tail을 기록했다.
보조 채널 파일은 stdout/stderr를 절대 대체하지 않았다. 더 가벼운 후속
진단에서는 product profiling을 빼고 3.5초에 파일 전용 stack dump 한 번을
예약했으며 발동한 stack dump는 없었다. 계측은 동등성 증명이 아니며 scheduling에
영향을 줄 수 있다. 따라서 비계측 child도 실행했다. Async profiler call/return
항목은 coroutine suspension/resumption을 포함하므로 별개 요청이나 최종 종료로
세어서는 안 된다.

직접 직렬 비교는 두 source에 동일한 Python 3.12.14 환경과 소유
MySQL 8.4.7 require-mode preflight를 사용했다. 아래 A/B/C는 원래 보고된
순서의 실패 node 세 개를 뜻한다.

| 직접 비교, 각 source 별도 실행 | 현재 RT-11(c) | 깨끗한 develop |
|---|---|---|
| phase 관측을 포함한 A, B, C 격리 | 각각 1 PASS | 각각 1 PASS |
| phase 관측을 포함한 원래 순서 최소 선행 묶음 | 6 PASS | 6 PASS |
| 관련 child에 phase 관측을 적용한 전체 process-safety 모듈 | 45 PASS | 45 PASS |
| 원래 비계측 child의 동일 최소 묶음 | **5 PASS / 1 FAIL (C)** | 6 PASS |
| 원래 직전 frame TCP, health 및 소유 MySQL 모듈 다음 process-safety; 비계측 child | 53 PASS | 53 PASS |
| 사전 선언한 최소 묶음 paired 실행 세 번, 경량 관측 | 3회 각각 6 PASS | 3회 각각 6 PASS |

최소 묶음은 A 직전 선행 항목, A, B 선행 항목, B, C 선행 항목, C를 선택해
원래 상대 순서를 유지했다. 리소스 묶음은 source마다 실제 MySQL node 여섯 개 /
성공 phase18개를 포함하며 skip/xfail은 없다. 이 부분집합 보고서는 새 필수
inventory strict gate나 새 전체/중첩 결과가 아니다. node별 진단 관측은 현재
source에서 A **0/8 timeouts**, B **0/8**, C **1/8**이며 develop은 각각
**0/8**이다. 수는 지정한 진단 모드를 합친 것으로 독립 통계 시행이 아니다.
이전 전체 실패는 제외하며 운영 실패 확률을 추정하지 않는다. 새 C RED
raw/JUnit은 `current-control/` 아래 변경 없이 보존한다. 해당 5초 실패도
stdout-reader join에서 발생했고 pipe는 비어 있었다. 그 실행은 의도적으로
child phase 계측을 하지 않았다.

관측한 성공 수명주기 경계:

| 경계 | A | B | C |
|---|---|---|---|
| Import와 app composition | SQLAlchemy/API import, 실제 create_app/compose_api | API import; 가짜 app/composition | Uvicorn/API import; CLI main 전 실제 create_app |
| Ready/serving | Mock serve 진입, listener나 ready handshake 없음 | Mock run 진입, listener나 ready handshake 없음 | 실제 startup/bind, 기존 main_loop hook이 listener 확보; 추가 ready handshake 없음 |
| Signal 동작 | Handler 설치, Python으로 발생시킨 KeyboardInterrupt, 복원 handler assertion | 주입한 close 실패 전후 handler 설치와 복원 | Uvicorn signal capture/복원; 외부 전달 OS signal 없음 |
| Shutdown/cleanup | Composition close, event close, 두 engine disposal 반환 | 주입한 close가 예외 발생; CLI가 예상 실패로 조용히 반환 | 실제 Uvicorn shutdown, composition cleanup 실패 유지, listener-close와 연결 거부 assertion 통과 |
| Finalization | atexit 진입/tail, 두 reader EOF, process wait 반환 | 동일 | 동일 |

과거 **실패한** A/B/C와 새 비계측 C에서 확인된 것은 parent stdout-reader
deadline phase뿐이며 child phase는 여전히 알 수 없다. 누락된 실패 stack을
성공한 수명주기 관측으로 대체해서는 안 된다. 계측 대상 child는 atexit tail에서
main thread만 남은 채 종료됐으며 asset load 호출이나 HTTP asset scope는 없었다.
C의 asset/frame middleware scope는 기존 우회 동작에 따라 `lifespan`이었다.
이 테스트 경로에는 asset metric send, frame permit 확보 또는 asset DB
트랜잭션이 없다. 새 subprocess는 parent permit 상태를 격리한다. 이번 조사로
CLI, logging, semaphore 및 DB/server cleanup 구현은 바뀌지 않았으며
resource-prefix 비교도 두 source 모두 통과했다. RT-11(c)는 여전히
import/router 구성과 lifespan middleware dispatch를 추가하므로, 이 사실들은
timing 기여가 없음을 입증하지 **않는다**.

**가설과 한계:** phase 관측은 전체 예산이 shutdown이 아닌 import/startup에서
소모됐는지 검사했다. 성공 실행은 모든 경계에 도달했지만 timeout된 child를
phase/stack 기록으로 포착하지 못했다. 가설은 여전히 미확인이다. 과거 host
scheduling, cache 및 전체 OS 환경은 수집되지 않았고 재구성할 수 없다.
새 MySQL port/datadir, snapshot 경로 및 비압축 fixture tree는 과거 전체 실행과
다르며 비교 변형 두 개는 이 조건을 공유했다. host/disk 경합, Windows
launcher/pipe 동작, 관측 효과 또는 RT-11(c) timing 회귀 중 어떤 것도 원인으로
입증되지 않았다. develop에서는 재현되지 않았으므로 **확인된 기존 develop
버그의 증거가 아니다**.

**수정 없음 / RED→GREEN 주장 없음:** 원래 실패와 추가 C RED는 미해결로 남는다.
이후 대상별 통과는 관측이며 복구나 전체 pytest PASS가 아니다. 여기서는 전체
pytest, 중첩 필수 MySQL gate 또는 원격 CI를 다시 실행하지 않았다.
앞선 1,006-node 전체 MySQL과 1,001-node 중첩 strict 성공은 보존한 증거로
남긴다. 전체 FAIL과 미확보한 현재 diff 원격 CI는 계속 merge blocker다.
미해결 timing/관측 효과는 조사 한계로 남으며 기존 buffering/best-effort
telemetry 한계도 유지한다.

**정리/증거:** 소유 비교 MySQL/helper는 종료됐고 정확히 생성한 datadir를 제거했으며
포트는 연결을 거부했다. 감사: system schema 네 개와 base schema,
기본 계정 네 개, 감사 외 client/transaction/data lock 없음.
native 소유 테스트 프로세스 감사에서 잔여물은 없었다. 모든 report 및 snapshot
source hash를 보존했다. 생성된 zero-byte snapshot cleanup lock은 hash로 보존하고
프로세스 종료 후에만 제거했다. 진단, snapshot, 실패/성공 raw/JUnit, 환경과 순서,
phase JSONL, 선택적 stack file, manifest 및 리소스 감사는
`.codex-scratch/rt11c-process-safety-20261024/` 아래 PR에서 제외한다.
기존 증거와 #387 archive 계획은 바꾸지 않았다. reviewer/subagent, staging,
commit, push 또는 PR 생성은 사용하지 않았다.
