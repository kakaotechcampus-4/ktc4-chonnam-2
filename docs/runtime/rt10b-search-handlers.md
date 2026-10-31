<a id="rt-10b-search-handlers--implementation-checkpoint"></a>

# RT-10(b) Search 핸들러 — 구현 체크포인트

**IN_PROGRESS · Refs #297 (RT-10(b)) · 2026-10-25**

독립 검토 전의 미커밋 구현 체크포인트다.
전체 RT-10 인수나 merge 권고가 아니다. 검토자/subagent 호출,
staging, commit, push, PR, 브랜치 전환 또는 worktree 생성은 수행하지 않았다.

<a id="verified-baseline-and-agreements"></a>

## 검증한 기준선과 합의

- 현재 브랜치: `codex/rt10b-handler-registry`. HEAD와 새 읽기 전용
  `git ls-remote origin refs/heads/develop`은 모두
  `ea580ac6e1f0a035bf0938fcb8a097394f4b20d1`로 확인된다(병합된 PR #329).
- [#303 Runtime 인수](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/303#issuecomment-6380230633):
  실행의 `UsageSink`를 공개 호출 인자로 전달한다. Search는
  HTTP attempt별로 begin/finish를 수행하고, 재시도 없이 `UsageError`를 전파하며,
  finalize하지 않는다. Worker는 T1 뒤 finalize한다. #303은 여전히 **open**이며,
  #329 밖의 진단 작업은 별도다. open 상태 자체가 이 호출을 막지는 않는다.
- [#297 Case 입력/결과 합의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6381933011)와
  [Runtime 응답](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6384372018):
  `CaseStore.observation_input`을 사용한다. Fine은 `analysis_run`과
  `visual_evidence`를 반환한다. IncidentClip은 별도 `INCIDENT_CLIP_BUILD` 실행이다.
  Worker는 후속 job을 선택하거나 Fine 안에서 clip을 만들면 안 된다.
- PR #385 merge SHA는 `c491a95b8726377c2eca2ac3dad6bcc6ce416670`이다.
  GitHub Actions API는 head `1dd9bd7f...`의 성공한
  [boundary 실행 39552040227](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39552040227)과
  [python-tests 실행 39552040245](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39552040245)를 직접 확인한다.
- 같은 API는 #329 head `91d2778c...`의 성공한
  [boundary 실행 40109830290](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40109830290)과
  [python-tests 실행 40109830291](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40109830291)를 확인한다.
  이는 선행/head CI 결과이며, 이 미커밋 diff의 원격 CI가 아니다.

<a id="selected-slice-and-behavior"></a>

## 선택한 작업 범위와 동작

Search kind 그룹은 `HINT_EXTRACT`, `COARSE_SEARCH`,
`FINE_VERIFY` 어댑터를 구현한다. 입력은 공개 CaseStore 읽기와 ProducedReader를 통해
짧은 caller 트랜잭션에서 얻으며, 이를 해제한 뒤 외부 작업을 시작한다. Fine은
현재 선택한 candidate 대신 job의 고정 generation/candidate/interval을 사용한다.
좌표 네 개의 Case interval은 candidate의
`representative_ms`를 입력 일부로 취급하지 않고 비교한다. Fine은 source를 정확히 하나 resolve하고
scope의 명시적 latency budget을 전달하므로 새 SearchService가
앞선 Coarse 프로세스의 cache를 갖고 있을 필요가 없다.

각 공개 호출은 `context.usage_sink`를 받는다. fallback sink나 handler
finalize는 추가하지 않는다. 입력 읽기, 리소스 획득, resolver,
기능 경계 전후에 checkpoint를 둔다. 제공된 media service context는 취소와
예외 시 종료한다. 향후 Recording factory는 RD-09a에 따라 실행별로
RecordingService를 생성/종료해야 한다. 이 범위는 이를 생성하거나 수명주기를 입증하지 않는다.

각 Search 결과는 불투명한 produced payload 하나다. Coarse/Fine은 실제
`analysis_run` ref를 object와 terminal receipt 모두에 사용한다. 이에 따라
기존 ProducedReader는 wrapper dictionary 하나를 반환하고 T1 후 reconciliation은
usage를 해당 Run과 연결할 수 있다. Intent는 payload에서 SearchLedger usage를 제외하며,
권위 있는 Runtime usage는 기존 ledger에 남는다. Produced 저장소,
마이그레이션, T1, receipt, ownership 또는 recovery 구현은 변경하지 않았다.

기본 Worker 연결은 `HINT_EXTRACT`만 등록한다. Coarse/Fine에는 명시적인
실행 리소스 `service_factory`가 필요하며, 없으면
`RUNTIME_UNREGISTERED_KIND`로 남는다. 기본 진입점은 여전히 전체 Case T2/stored adapter 연결이 없다.
부분적인 root이며, 동작하는 프로덕션 Search pipeline은 아니다.

제외 범위: `INCIDENT_CLIP_BUILD`, `PLATE_READ`, `OVERLAY_TIME_READ`,
`REPORT_VIDEO_EXPORT`, `PLATE_IMAGE_EXPORT`.
미지원 기능을 성공 stub으로 나타내지 않는다. 테스트는
Search 부분집합을 현재 `JOB_KINDS`와 대조하고 미등록 기본 동작을 확인한다.

<a id="blocking-discovery--implementation-stopped"></a>

## 차단 요인 발견 — 구현 중단

JobExecution Contract §6은 모듈 prefix를 가진 `failure_kind`와
모듈 failure taxonomy에 등록된 이름을 요구한다. Tech Spec §6.2도 provider
계정/인증 실패를 일반 INFRA와 구분하도록 요구한다.

현재 초안 핸들러는 `IntentHintResult.failure_kind`(예:
`PROVIDER_ERROR` 또는 `CONFIG_ERROR`)와 첫 실패 AnalysisRun issue의 kind
(예: `INFRA`)를 전달한다. 이는 문서화된 JobExecution 매핑이 아니다.
Search taxonomy 문서는 여전히 초안으로 표시돼 있다. Coarse는 provider 오류를
`INFRA / PROVIDER_CALL_FAILED`로 합치며, Fine은 실패 Run을 반환하는 대신 예외를
발생시킬 수 있다. AnalysisRun 검증은 issue가 없는 FAILED도 허용하는데,
초안 핸들러는 첫 issue를 참조한다. 테스트 성공은 이
실패 경로의 공백을 해결하지 **않는다**. 이 상태로 핸들러를 병합하거나 프로덕션에서 활성화하면 안 된다.

이 발견을 해결하려고 새 taxonomy, 임의의 `SEARCH_` 결합, 예외 텍스트 파싱,
Search 내부 import 또는 대체 terminal 정책을
도입하지 않았다. 제품 구현은 이 경계에서 중단했으며 현재
초안과 한계를 검토용으로 유지한다.

필요한 Owner 판단:

1. Search Owner: intent status와 AnalysisRun issue에서 JobExecution failure 이름으로의
   매핑을 정의/문서화한다. issue 우선순위/빈 FAILED run,
   계정/인증 구분을 포함한다. Fine 모듈 실패 노출 방법을 확인한다.
2. Runtime/Contract Owner: 해당 매핑과 Fine 예외 대 반환된 실패 Run의
   terminal/produced 동작을 확인한다. 실제 실패 Run
   ref와 T1 후 usage reconciliation을 보존하며, 성공 결과를 만들어내지 않는다.
3. Recording/Case 구성 의존성은 남아 있다. 영속 RecordingFacts, 공개
   source 복원/설정, API/Worker stored adapter 주입, 이후 Case의
   자동 Coarse→Fine dispatch다. 비공개 schema 지름길은 추가하지 않았다.

<a id="tdd-and-direct-evidence"></a>

## TDD와 직접 증거

증거는 PR에서 제외된 `.codex-scratch/rt10b-20261025/`에 있다. 모든 시도에
별도 산출물이 있으며, 이후 통과가 앞선 실패를 재분류하지 않는다.

| 직접 실행 | 결과와 범위 |
| --- | --- |
| 최초 handler RED | `search_handlers`가 없을 때 실패 12건 (`red.xml`) |
| Input/handler GREEN | 23건 통과 (`green4.xml`); 앞선 fixture-ref, strict JSON, append-only test-fixture 실패 보존 |
| Composition RED→GREEN | 2건 실패(composition/intent config 누락) → 50건 통과 (`composition-green.xml`) |
| 공개 기능 + 오프라인 SDK transport | 9건 통과 (`capability.xml`): 세 kind 모두 × 정상/begin 실패/finish 실패; HTTP 수, sink 식별값, 재시도 없음, null KRW 비용 |
| Receipt 회귀 RED→GREEN | 2건 실패(별도 Run/object ref) → 33건 통과 (`receipt-green.xml`) |
| 고정 Case interval RED→GREEN | 1건 실패(전체 span 비교) → 33건 통과 (`span-green.xml`) |
| 최종 관련 오프라인 회귀 | **1,235건 통과, 6건 skip, 612건 선택 해제**, 기존 SDK serializer 경고 3건, 59.27s (`regression-final.xml`) |
| 새 실제 MySQL 8.4.7 Search chain | **3건 통과**, 성공 phase 9개, skip/xfail 0 (`mysql-search-green.json/.xml`); 정상/deadlock rollback/실제 COMMIT 응답 유실 |
| 기존 실제 MySQL 회귀 | **71건 통과**, 성공 phase 213개, skip/xfail 0 (`mysql-regression.json/.xml`): produced store, Worker usage/reconciliation, cancel checkpoint, Case 반영 |
| Gate 음성 대조 | 15건 통과, 8,103건 선택 해제 (`gate.xml`); bypass/JUnit 누락/metadata 변형 검사 |
| 경계 / Contract fixture | 위반 0건; 구조 62 / JSON 26 / 의미 fixture 검사 104건 통과 |
| Diff와 보호 경로 | `git diff --check` 통과; checker, workflow, Contract fixture, jobs core, Search/Case/Recording/Readout 파일은 HEAD 대비 변경 없음(checkout 줄바꿈 정규화만 있음) |

최종 오프라인 명령은 `tests/search tests/worker tests/case
tests/common/jobs tests/common/usage -m 'not mysql'`를 선택했다. Skip 네 건은 선택적 typer
AIhub 테스트이며 두 건은 사용할 수 없는 외부 Case video 사례다. Skip/xfail 정책은
변경하지 않았다. 새 MySQL 테스트는 실제 Case 명령, Runtime Worker,
실행 범위 영속 sink, 실제 Search/Gemini adapter, 오프라인 provider
transport를 사용한다. 서로 다른 실행 usage 기록 세 개, 유료 호출을
반복하지 않는 T1 재실행, produced payload, Case T2, 정제된 로그를 확인한다. Fine은
NOT_OBSERVED이므로 이 테스트는 Recording fact 읽기를 허용하지 않는다. 주입된
stored adapter는 테스트 구성이며 완성된 기본 구성이 아니다.

보존한 실패 실행에는 Windows sandbox subprocess 권한 실패
(`regression2.xml`: 32건 실패 / 1,203건 통과 / 6건 skip), Linux media/CLI
의존성 누락(`regression-linux.xml`: 12건 실패 / 1,199건 통과 / 30건 skip),
Windows MySQL 사전 점검 setup 오류, 연속된 새 MySQL 통합 실패
(media duration fixture, receipt ref, Case interval 형태, stored adapter 누락)가 있다.
최종 Windows 관련 회귀는 명시적인 process 권한으로 실행했다.
테스트가 실행되지 않은 명령 오타와 Python 의존성 누락 시도는 통과가 아니다.
실행별 수치는 scratch `audit.json`을 참고한다. 수치를 합쳐 전체 suite로 만들지 않는다.

새 MySQL 보고서는 selection 일치, 고유 node, 완전히 성공한
setup/call/teardown phase, JUnit을 갖는다. 각 보고서에서 실제 JUnit testcase 하나를 제거하면
거부됐다. 변경하지 않은 전체 inventory validator는 `required MySQL role/scenario missing`으로
**두 부분집합을 모두 거부한다**. 이는 예상된 거부이며,
strict full-gate PASS가 아니다. Inventory/checker나 nested gate 우회는 추가하지 않았다.

<a id="unexecuted-checks-and-resources"></a>

## 미실행 검사와 리소스

전체 pytest, 전체 MySQL/nested 900s wrapper, 전체 8,118개 테스트 gate 단위 inventory, 독립
Recording/Readout suite, 실제 유료 provider, 전체 API/Worker 프로세스 간 E2E,
이 diff의 원격 CI는 실행하지 않았다. 변경 표면은 Search
adapter/config/input 연결로 한정하며, 관련 오프라인 및 집중 실제 MySQL 테스트가
persistence 경계를 검증한다. Failure Contract와 프로덕션 구성 차단 요인을
해결하기 전에 전체 suite/필수 DB inventory를 반복해도
누락된 의미론을 입증하지 못하며 비용이 큰 선행 검증을 중복한다. 과거
CI는 증거일 뿐 새 인수를 대체하지 않는다. Workflow 30분과
nested 900초는 그대로다(scratch runner 자체는 880초 사용).

소유한 MySQL 감사(`server-final.json`)는 시스템 스키마와 테스트
base schema만 존재하고, 기본 계정만 있으며, 비감사 client 없음, transaction 0, data
lock 0임을 기록한다. Helper는 종료했고 정확한 `/dev/shm/rt10b-*` datadir를 제거했으며,
port 연결은 거부를 반환했다. 공유 도구/이전 증거는 보존했다.

사용자의 명시 요청 뒤 독립 검토가 이 초안을 살펴볼 수 있으며,
검토자는 호출하지 않았다. Failure taxonomy는 여전히 merge 차단 요인이며,
전체 구현 검토 전에 Owner 설명이 필요할 수 있다. Scratch RAW,
JSON/JUnit, runner, cache/temp tree, DB 자료, 로컬 실행 계획은
PR에서 제외한다. Staging/index 변경은 없었다.

<a id="2026-10-26--resumed-confirmed-boundaries-append-only-follow-up"></a>

## 2026-10-26 — 확인된 경계에서 재개 (추가 전용 후속 기록)

**IN_PROGRESS · Refs #297 (RT-10(b)); HINT 인증/budget 인수 미결.**

사용자는 남은 Search Owner 응답을 기다리지 않고 확인된 Coarse/Fine/HINT 작업을
계속하도록 승인했다. 원래 수정/untracked 파일 15개는
제외된 `.codex-scratch/rt10b-20261026/pre-update/`에 byte 단위로
hash 및 tracked patch와 함께 백업했다. 들어오는 develop
변경과 겹친 경로는 없었다. 현재 브랜치는 `ea580ac6...`에서 최신
`4a69a292f55ed48b9f679c1016087d3acd11a994`로 fast-forward했다(#327, #358, #401 포함).
Fast-forward 직후 원래 파일 hash 15개가 모두 일치했고 index는
비어 있었다. 최초 sandbox Git ref 쓰기는 거부됐지만, 이후 승인된 같은
fast-forward가 파일시스템 권한으로 성공했다. Commit/stash/branch/worktree는
생성하지 않았다.

<a id="confirmed-mapping-and-remaining-dependency"></a>

### 확인된 매핑과 남은 의존성

[#297 Runtime 인수](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6387601291)와
[Search Owner 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6392679689)은
앞선 일반 taxonomy 질문을 해결한다. 공개 helper 함수 세 개를 사용하고
규칙을 복제하지 않는다. FAILED run은 실제 Run
receipt/payload를 보존하며 PARTIAL은 실행 성공으로 유지한다. Case-command §11은 이미
실패 intent가 JobExecution FAILED가 되지만 Case는 빈 hint로 계속한다고 규정한다.
새 Runtime 정책이 아니다.

**PR #403은 계속 open/unmerged**이며 `00549ff23d27ac327a9305cb22b4661b68be403f`에 있다.
따라서 공개 helper는 최신 develop에 설치되지 않았다. `SearchFailures`는
확인된 공개 함수 이름에 대한 구조적 포트일 뿐이다. 기본 discovery는
`daesingo.search`를 사용하며, 필요한 helper 중 하나라도 없으면 Search kind는
미등록 상태로 남아 input 읽기/provider 호출을 하지 않는다. 테스트는 포트
double을 주입할 수 있고, 별도의 제외된 snapshot은 정확한 공개 구현을 검증한다.
이 브랜치에는 복사한 taxonomy, 비공개 import, 미병합 Search 코드가 없다.
실제 helper를 사용할 수 있게 된 뒤에도 기본 등록은 HINT뿐이며, Coarse/Fine에는
media factory 주입이 계속 필요하다. 이는 앞선
체크포인트의 안전하지 않은 원시 failure 전달을 대체하며, 과거 테스트 결과를 대체하지 않는다.

오류 매핑 try 블록은 공개 Search 호출만 감싼다. 입력 로드,
트랜잭션 작업, factory enter/exit, checkpoint, payload 직렬화, T1은
밖에 남는다. `UsageError`와 협력적 취소는 그대로 전파한다.
결과 helper는 Search 결과 또는 AnalysisRun만 받는다. 매핑은
usage finalize, 예외 시 Run 생성, 후속 job dispatch 또는 T1 변경을 하지 않는다.

<a id="explicit-pending-acceptance"></a>

### 명시적 인수 미결 사항

최종 조회에서도 [#403 HINT 후속 기록](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/403#issuecomment-6398537018)에는
후속 Owner 답변이 없다. #403 snapshot의 실제 SDK + MockTransport와
주입한 clock은 다음을 관측한다.

| HINT 응답 | Budget 남음 | Budget 소진 |
| --- | --- | --- |
| 401 / 403 / 404 | 공개 helper가 SEARCH_PROVIDER_CONFIG 반환 | SEARCH_DEADLINE_EXCEEDED 반환 |
| 500 | SEARCH_PROVIDER_ERROR | SEARCH_DEADLINE_EXCEEDED |

이는 **미결 관측**이며, 인수된 의미론 assertion이나 성공
기준이 아니다. Runtime은 공개 결과를 그대로 전달하며, 원인,
status code, 경과 budget을 검사해 덮어쓰지 않는다. `hint-pending.json`은 각각
HTTP 호출 한 번인 별도 관측 여덟 개를 보존한다. 어떤 테스트도 spent-auth 동작을
올바른 것으로 고정하지 않는다. Owner 수정과 이후 인수 실행이 여전히 필요하다.

<a id="new-direct-verification-separate-from-all-2026-10-25-evidence"></a>

### 새로운 직접 검증 (모든 2026-10-25 증거와 별도)

| 실행 | 결과 |
| --- | --- |
| 경계 TDD | **23 RED → 23 GREEN** (`red-boundary.xml`, `green-boundary.xml`); 최초 test-import 실수는 `red.xml`에 별도 보존 |
| 현재 workspace 집중 테스트 | **64 PASS** (`focused.xml`) |
| 현재 workspace 관련 회귀 | **2,000 PASS / 21 SKIP / 713건 선택 해제**, SDK 직렬화 경고 3건, 202.43s (`regression.xml`) |
| 새로운 실제 MySQL 8.4.7 | **74 PASS / 성공 phase 222개 / skip=xfail=0**, 98.17s (`mysql-final.json/.xml`); 새 실제 Search chain 세 개와 produced/usage/reconciliation/cancel/Case 회귀 |
| Gate 음성 대조 | **15 PASS / 8,103건 선택 해제** (`gate.xml`) |
| 의존 snapshot | **95 PASS**, 7.05s (`owner-final.xml`), 최신 develop + 정확한 #403 Search source 및 현재 Worker 파일 |
| Snapshot 옛 handler 음성 대조 | **16 FAIL / 4 PASS** (`owner-red.xml`); 재개 전 handler로 복원하면 원시 failure 매핑/issue 누락/Fine 예외 결함이 드러남. Snapshot handler를 되돌린 뒤 위의 95개 테스트 실행을 다시 수행 |
| 경계 / fixture / diff | 위반 0건; Contract 62/26/104; diff 검사 PASS |

95개 테스트 의존 실행에는 실제 공개 helper/기본 registry
투영과 실제 SDK 실패 기능 검사 20개가 포함된다. Coarse 실패 Run usage
ref, Run을 만들어내지 않는 Fine 예외도 포함한다. 이는 develop 통합도,
미결 HINT spent-auth 동작의 인수 결과도 아니다. Snapshot-source
hash/revision은 별도 기록한다. 현재 workspace 정상 경로 테스트는
#403이 없는 동안 성공 전용 policy double을 주입하며, 실제
helper 통합을 주장하지 않는다. 서로 다른 실행의 수치는 합치지 않는다.

관련 회귀는 `-m 'not mysql'`로 Search/Worker/Case/jobs/usage/Recording/Readout을
선택했다. 기존 skip은 선택적 typer import 네 개, 누락된
Case 동영상 두 개, Recording 실제 media opt-in 열다섯 개다. Skip/xfail 규칙은 바뀌지 않았다.
성공한 DB 보고서와 JUnit 모두 고유하고 완전한 selection,
성공한 setup/call/teardown, skipped/xfail phase 없음을 확인했다. 실제
JUnit 항목 제거는 거부한다. 변경하지 않은 full-inventory checker는 필수 role/scenario 누락으로
74개 테스트 부분집합을 거부하며, **전체 strict gate는 PASS가 아니다**.

전체 pytest, 전체 MySQL/nested 필수 wrapper, 전체 gate 변형 suite,
유료 provider, 전체 API/Worker 프로세스 간 E2E, 현재 diff의 원격 CI는
실행하지 않았다. 관련 회귀에 이미 약 202초, 집중 실제 DB에 약
98초가 걸리며, jobs core/checker/workflow/다른 Owner 코드는 그대로다. 더 넓은
필수 inventory를 반복해도 미병합 의존성, 미결
HINT 의미론, 미완성 프로덕션 media/T2 구성을 해결하지 못한다. Workflow 30분과
nested MySQL 900초는 그대로다. Command/setup 실수, 최초
sandbox 거부, 음성 대조 실패를 보존하며 통과로 부르지 않는다.

소유한 DB/helper 종료, 정확한 datadir 제거, port 거부는
`server-final.json`에 기록한다. 시스템 스키마와 전용 base schema/기본
계정만 있었으며 비감사 client, transaction, data lock은 없었다. 과거
증거와 공유 runtime은 보존했다. 모든 snapshot/RAW/JSON/JUnit/runner/cache,
DB 자료, 로컬 실행 계획은 계속 PR에서 제외한다. 독립된
새 context의 읽기 전용 검토가 사용자가 명시 승인한 다음 단계이며,
결과는 이 이력을 바꾸지 않고 추가한다.

<a id="2026-10-26--fresh-independent-read-only-review"></a>

## 2026-10-26 — 새로운 독립 읽기 전용 검토

사용자가 요청한 검토자를 같은 대화에서 `fork_turns=none`으로
배정하고, 구현 대화 대신 요구사항/base/파일 manifest를
전달했다. 검토자는 변경 파일 17개 전체, SoT,
현재 #403 상태를 살폈고 `git diff --check`만 실행했다. 검토자는
테스트나 DB를 실행하지 않았다. 결과 기록 전 작성자는 독립적으로
manifest hash 17개와 HEAD/branch가 그대로이며 index가 비어 있음을 검증했다.

- 전달한 Search adapter 범위에서 **새 P1/P2 결함 없음**. 이는
  정적 검토 결과이며 독립 실행 증거나 merge 인수가 아니다.
- **P3, 유보:** tracked 성공 구성 테스트는 policy 포트를 주입하지만,
  tracked discovery 테스트는 helper 부재만 검증한다. 호출 가능한 공개 속성을
  제공하고 `failures=`를 생략하는 유지관리 테스트를 추가해 discovery가
  실수로 항상 None을 반환하는 경우를 잡아야 한다. 제외된 #403 snapshot은 이번 실행의 실제
  기본 통합을 검증하지만 유지관리 회귀를 대체하지 않는다.
  프로덕션 결함은 입증되지 않았다. 요청하지 않은
  추가 구현/재검토 회차 없이 경미한 항목을 기록했다.
- **판단 유보:** 미완성 프로덕션 Recording/media/T2 수명주기와
  프로세스 간 구성, 명시적으로 제외된 clip/readout/export handler,
  전체 pytest/전체 필수 DB gate/현재 diff CI. 어느 것도 암묵적으로
  완료로 취급하지 않는다. 별도 의존성/인수 한계로 남는다.
- HINT spent-auth는 계속 **인수 미결**이며 #403은 open/unmerged다.
  의존성이 병합된 뒤 공개 helper의 실제 통합을 확인해야 한다.
  검토는 해당 HINT 의미론 동작이나 전체 RT-10 인수를 승인하지 않는다.

새 검토 텍스트와 무결성 증거는 제외된 scratch 산출물이다. 최종
상태는 계속 **IN_PROGRESS · Refs #297 (RT-10(b))**이며 미커밋, unstaged다.
Push, PR 생성, branch/worktree 생성 또는 추가 검토자는 없었다.

<a id="2026-10-26--independent-production-composition-follow-up"></a>

## 2026-10-26 — 독립 프로덕션 구성 후속 기록

앞선 검토 뒤 사용자는 #403/#405가 미결인 동안 영속 Recording facts/source
조회, API/Worker stored adapter, 프로덕션 Coarse/Fine media, 기존 T1/T2
통합, 별도 프로세스 E2E를 승인했다. 이는
후속 변경이며 앞선 17개 파일 검토의 재해석이 아니다.
앞선 P3 기본 discovery 테스트 공백은 이제 검증한다. 범위, RED→GREEN, 직접
2254개 오프라인 / 226개 MySQL 테스트 실행과 그 한계는
[프로덕션 구성 체크포인트](rt10b-production-composition.md)에 기록한다. 해당 기록에는
이후의 문서 전용 develop fast-forward와 리소스
정리도 있다. 확장된 초안에는 새 읽기 전용 검토가 필요하다.

IN_PROGRESS · Refs #297 (RT-10(b)); #403 HINT spent-auth와 #405 STALE 정책은
계속 인수 미결이다. Stage/commit/push/PR 없음.

<a id="2026-10-26--expanded-draft-review-follow-up"></a>

## 2026-10-26 — 확장 초안 검토 후속 기록

새 읽기 전용 검토는 P2 한 건을 발견했다. SQLAlchemy가 아닌 Runtime transaction
결과가 주입된 capability resolver에서 Search helper로 도달할 수 있었다.
이를 재현하고 명시적인 예외 네 개 guard로 수정한 뒤
RED2 21 FAIL/4 PASS → 25 PASS와 집중 회귀 167개로 검증했다. 같은 검토자는
두 파일 delta를 읽고 P2 해결, 새 P1/P2 없음으로 판단했다. 이 결과는
앞선 실행 식별값을 대체하거나 #403/#405를 해결하지 않는다. 시간순
[검토/수정 기록](rt10b-production-composition.md)을 참고한다. IN_PROGRESS · Refs
#297 (RT-10(b)); staging/commit/push/PR 없음.
