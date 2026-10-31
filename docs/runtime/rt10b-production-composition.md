<a id="rt-10b--durable-recording--production-search-composition-checkpoint"></a>

# RT-10(b) — 영속 Recording / 프로덕션 Search 구성 체크포인트

> 2026-10-28 후속 기록: 다음 최소 clip-handler 작업 범위는
> [INCIDENT_CLIP_BUILD 구현 기록](rt10b-incident-clip-handler.md)에 있다.
> 아래 체크포인트의 범위와 실행 증거는 원래의
> 역사적 의미를 유지한다. 제외된 핸들러 목록은 후속 작업의 상태가 아니다.

**IN_PROGRESS · Refs #297 (RT-10(b))**. 2026-10-26의
[Search adapter 체크포인트](rt10b-search-handlers.md) 후속 기록이다.
#403과 #405가 미결인 동안 사용자가 승인한 독립 구성 작업을 기록하며,
전체 RT-10 인수나 merge 승인이 아니다.

<a id="scope-and-dependency-boundary"></a>

## 범위와 의존성 경계

작업 전에 기존 17개 파일 unstaged 초안을 백업했다. 동일한 브랜치
`codex/rt10b-handler-registry`를 계속 사용했다. 구현/테스트는
`4a69a292f55ed48b9f679c1016087d3acd11a994`를 기준으로 실행했다. 사용량 한도 뒤 재개할 때
origin/develop에는 Case 문서 변경 네 개가 추가돼 있었다(#354/#406/#397).
현재 변경 파일 37개를 모두 백업했고, 들어오는 경로는 겹치지 않았으며,
`42ddea72bb927e7adedf352ba53d160bda1aa049`로 fast-forward한 뒤에도 모든 hash와
빈 index가 보존됐다. 들어온 Fine 70초/반복 정책/상태 기록은
새 Runtime orchestration이나 재시도 정책을 요구하지 않는다. 이 갱신에서 source는
바뀌지 않았으며 앞선 테스트 실행은 원래 실행 식별값을 유지한다.

이 범위는 HINT_EXTRACT / COARSE_SEARCH / FINE_VERIFY adapter를 영속
Recording 읽기, 저장된 Case observation, 프로덕션 Coarse/Fine media,
기존 T1/T2 경로에 연결한다. 기본 Search 등록에는 여전히 실제
공개 failure helper 세 개가 필요하지만 이 develop에는 없다. 테스트는 명시적으로
확인된 정책 포트를 제공한다. 프로덕션 fallback이나 taxonomy 복사가 아니다.
Helper가 없으면 기존의 미등록 kind 실패를 유지한다. Helper와
명시적 media profile이 있으면 프로덕션 Coarse/Fine 구성을 사용할 수 있다.

- **#403 인수 미결:** intent/HINT 401/403/404와 소진된 budget.
  마지막으로 살핀 논의는 여전히 `6398537018`에서 끝난다. Runtime 재매핑이나
  의미론 인수는 추가하지 않았다. PR은 `00549ff23d27ac327a9305cb22b4661b68be403f`에서 open/unmerged다.
- **#405 미결:** 모든 attempt가 STALE이 된 뒤의 terminal 알림, 자체 receipt,
  Case 정책. 기존 T2와 `case_applied_at`은
  기존 SUCCEEDED/FAILED 전달에만 유지하며, STALE 투영은 도입하지 않았다.
- INCIDENT_CLIP_BUILD, PLATE_READ, OVERLAY_TIME_READ, REPORT_VIDEO_EXPORT,
  PLATE_IMAGE_EXPORT handler는 계속 제외/미등록 상태다. 이 범위는
  Runtime 권한으로 candidate를 고르거나 후속 job을 발급하지 않는다.

<a id="public-composition-and-storage"></a>

## 공개 구성과 저장

Recording은 새 분리된 facts/source 읽기와 그 persistence를 소유한다. Runtime은
Recording 스키마를 조회하지 않는다. `RecordingFacts`는 Case의 기존
facts 포트를 구현한다. API와 Worker CaseStore는 caller Connection, `read_executions`,
`ProducedReader`, `stored_adapter_factory`를 공유한다. API 명령 timeline 조회와
Worker T2는 해당 caller Connection에서 수명이 짧은 RecordingService를 사용한다. Lazy
repository facade 덕분에 media 파일/root를 확인하지 않고도
Case 전용 읽기와 실패한 Coarse T2를 처리할 수 있다.

실행 media는 실행마다 별도 RecordingService를 사용하며, 실패/취소 시에도
context manager가 닫는다. Repository 작업은 짧은
Runtime 소유 트랜잭션을 사용하고 분리된 데이터를 반환한다. 파일 확인, encoding,
provider I/O 동안 DB checkout을 유지하지 않는다. ProductionMediaFactory는 공개
get_media_stream / owns_asset / resolve_span / observe_time_sources /
prepare_analysis_source_from_resolution을 따르고, 기능 사이에 협력적
checkpoint를 둔 뒤 Search의 RecordingAnalysisSourceResolver와 공개 factory를 사용한다.
Case가 선택한 VIDEO ref가 필요하며 media 확인 전에 ownership을 검사한다.
현재 지원 입력은 명시적 TIMELINE_RELATIVE range 하나다.
Runtime은 임의의 stream을 고르거나 다른 scope를 추론하지 않는다.

Recording 모듈 factory는 다음을 담은 mapping을 사용한다.
`DAESINGO_RECORDING_ANALYSIS_PROFILE_REF`, `DAESINGO_RECORDING_ANALYSIS_HEIGHT`,
`DAESINGO_RECORDING_ANALYSIS_PRESET`, `DAESINGO_RECORDING_ANALYSIS_CRF`, 선택적
`DAESINGO_RECORDING_FILENAME_OFFSET`. Profile key가 없으면 media 구성을
비활성화하며, 일부만 있거나 유효하지 않은 profile 설정은 시작을 실패시킨다. Encoding 기본값이나
filename timezone을 만들어내지 않는다. Runtime은 모듈 mapping을 전달하며
provider secret이나 profile 의미를 해석하지 않는다.

영속 prepared media는 opt-in이다(Recording factory의 `durable_prepared=True`).
기존 기본 ephemeral 수명주기는 유지한다. Recording의 기존
InnoDB generic entry table은 불변 prepared metadata, 검증된 MP4 body
descriptor, 선택적 case 연계를 원자적으로 저장한다. 마이그레이션/스키마 변경은
필요하지 않았다. Content/metadata fingerprint가 안정적인 불투명 ref를 제공하며,
observation은 service/process 재시작 뒤에도 최초 저장한 candidate 식별값을
보존한다. 원본 source 경로는 Recording의 기존 storage root 아래에 남는다.

AnalysisSource byte는 기존 공개
`open_analysis_source`로 복원할 수 있다. IncidentClip model/body 영속성은
Recording 내부에서 테스트하지만 **공개 open_incident_clip API는 추가하지 않는다**. 기존 호환성은
해당 표면이 없어야 함을 명시적으로 요구한다. Clip/readout orchestration은 계속
이 범위 밖이다. 영속 preparation은 실패한 T1보다 오래 남을 수 있으며, retention/orphan
삭제 정책은 변경하지 않는다. 같은 출력은 같은 불변 ref를 갖지만
materialization 반복 시 encoding도 반복될 수 있다. Encode 비용 제거나
대형 object 처리량은 주장하지 않는다.

새 facts 목록은 외부 source lineage와 clip provenance를 보존한다.
검증된 content가 없는 알려진 metadata는 잘못된 AVAILABLE 대신 UNKNOWN이다.
기존 `lookup_asset_facts`의 unknown/error 동작을 유지하며, 분리된
목록은 자체 metadata fallback을 수행한다. RemoteCopy는 AssetFacts kind가 아니다.

Search handler는 실제 모듈 payload/ref를 기존 RT-10(a)
object store에 반환한다. Worker는 같은 T1에 object + terminal + produced를 영속화하며,
rollback과 COMMIT 결과 불명 식별값 검사는 그대로다. FAILED Run은
실제 receipt를 유지하고, 예외는 Run을 만들어내지 않으며 PARTIAL은 실행 성공이다.
Execution UsageSink는 그대로 전달하며 handler는 finalize하지 않는다.
공개 Search helper 적용은 Search 기능 결과/오류로 제한한다.
Runtime load/checkpoint/factory/transaction/persistence/serialization 실패는
Search failure로 매핑하지 않는다. 기능을 통해 올라오는 SQLAlchemy 오류,
UsageError, 취소는 helper 전에 전파한다. Ownership fence,
timestamp 순서, 늦은 결과 guard, 기존 T2 재전달은 그대로다.

<a id="direct-execution-evidence"></a>

## 직접 실행 증거

이하 실행은 모두 이 구성 작업에 속하며, 제외된
`.codex-scratch/rt10b-composition-20261026/` 아래에 별도 보존한다. 앞선 Search adapter
실행/snapshot과 원격 PR CI는 과거 증거이며 이 로컬 실행이 아니다.

| 검사 | RED / 중간 실패 | 후속 결과(각각 한 번의 실행) |
| --- | --- | --- |
| 영속 facts, 복원, persistence-error 경계 | 수정한 RED: 6 FAIL / 24 PASS; 최초 import 실수 보존 | 70 PASS / 기존 실제 동영상 2 SKIP |
| 실제 MySQL 영속 prepared object / transaction facade | 4 FAIL | 4 PASS; 최종 확장한 현재 파일 6 PASS |
| 프로덕션 media / 명시적 모듈 config | 10 FAIL; 이후 test-double과 명시적 VIDEO-ref 실패 보존 | 33 PASS |
| 저장된 API/Worker Case adapter / normal, FAILED, PARTIAL T2 | 최초 collection 오류, 이후 4 FAIL | 4 PASS |
| Bootstrap / 기본 reflector | 2 FAIL / 8 PASS | 53 PASS |
| 기존 facts/case 연결 | 3 FAIL | 11 PASS |
| Source lineage / media 없는 실패 T2 | 각 1 FAIL | 11 PASS |
| 별도 API/Worker process | 4 FAIL: 테스트 요청에 case_id 누락 | 4 PASS, 39.63 s |
| 관련 오프라인 회귀 | 1 FAIL / 2253 PASS / 21 SKIP: 금지된 추가 clip API | **2254 PASS / 기존 21 SKIP**, 970건 선택 해제, 213.45 s |
| 관련 실제 MySQL 회귀 | 1 FAIL / 221 PASS: 잘못 배치한 테스트 끝부분 NameError | **226 PASS**, 159.38 s |
| 추가 clip API 제거 뒤 현재 영속 MySQL | 별도 후속 실행 | **6 PASS**, 3.41 s |
| 기존 gate 음성 대조 | bypass / JUnit / metadata 변형 검사 | **15 PASS**, 8103건 선택 해제 |

제거한 clip API를 정당화하려고 기존 assertion을 바꾸지 않았다. 엄격한
datetime 복원, 미지원 remote-copy facts, fixture를 수정했다.
모든 중간 실패, sandbox child-process 실패, request/fixture 실수,
사용량 한도로 실행하지 못한 승인 시도는 별도 기록으로 유지한다. 실패 실행을
이후 PASS와 합치지 않았다. 현재 present-helper 기본 discovery
테스트는 override를 생략하고 호출 가능한 공개 속성을 제공해
앞선 검토의 P3 공백을 검증한다. 이미 올바른 경로를 기능 RED로 주장하지 않는다.

오프라인 선택은 Search/Worker/Case/jobs/usage/Recording/Readout/API에
`-m 'not mysql'`를 적용한다. Skip은 선택적 typer import 네 개, Case 외부
동영상 두 개, Recording 실제 동영상 opt-in 열다섯 개다. 경고: 기존
FastAPI/httpx 폐기 예정 경고 한 건과 malformed-usage serializer 경고 세 건.
Skip/xfail 정책은 완화하지 않았다.

실제 MySQL은 기존 Recording persistence/compatibility, 새 facts,
Search T1 object 원자성/rollback/COMMIT 결과 불명, execution usage/cancellation,
API START_ANALYSIS/views, Case 결과 반영, 프로덕션 process E2E를 검증한다.
226개 테스트 실행에는 process 사례 네 개가 포함되므로 수치를 더하지 않는다.
최종 테스트 여섯 개 후속 실행도 해당 실행과 겹치며 합산하지 않는다.

Process E2E는 별도 spawned API/Worker OS process, 실제 MySQL과
ffmpeg, 프로덕션 media/registry/T1/T2, 외부 provider에 MockTransport를 쓰는
실제 SDK를 사용한다. API HTTP는 child process의 ASGI TestClient를 통하며,
TCP listener가 아니다. 사례: normal, Coarse PARTIAL, Coarse FAILED, Fine FAILED.
테스트는 선택 후 공개 Case Fine 발급을 명시적으로 호출하며,
자동 제품 orchestration이나 제외된 clip/readout job을 입증하지 않는다.
확인된 정책 테스트 포트는 병합된 #403 통합을 입증하지 않는다.

JSON/JUnit 감사는 각각 테스트 226개/phase 678개, 여섯 개/18개, 네 개/12개의
고유하고 완전한 selection, 성공한 setup/call/teardown, skip/xfail 없음을 검증한다.
실제 JUnit 항목 제거는 변경하지 않은 validator가 거부한다. 전체
inventory 검사는 필수 role 누락으로 각 부분집합을 의도적으로 거부하며,
**전체 strict MySQL gate는 PASS가 아니다**. 경계 위반 0건; Contract fixture
구조/JSON/의미 62/26/104 PASS; diff 공백 검사 PASS. Contract,
Case/Search/Readout/jobs source, gate/inventory/workflow는 checkout한
base 대비 그대로다. Workflow 30분과 nested MySQL 900초를 유지한다.

전체 pytest, 전체 필수 MySQL/nested wrapper, 전체 gate 변형 suite,
실제 유료 provider, 이 미커밋 diff의 원격 CI는 실행하지 않았다. 관련
오프라인(~213 s)과 DB(~159 s) 검증에는 변경한 경계가 포함된다. 관련 없는
inventory를 반복해도 미결 #403/#405를 해결하지 못한다. 대형 MP4/BLOB 제한,
provider 프로덕션 동작, 다중 range media는 인수 한계로 남는다.

<a id="resources-and-review-handoff"></a>

## 리소스와 검토 인계

소유한 MySQL 8.4.7을 중지했고, 정확한 소유 datadir를 제거했으며 port는
연결을 거부했다. 종료 전에는 시스템 스키마/기본 계정과 소유한
base schema만 남았다. 비감사 client, transaction, data lock은 없었다.
Child process는 join했다. 새 빈 root cleanup lock 파일 두 개를 배타적으로
열고 백업한 뒤 제거했으며, 기존 파일은 삭제하지 않았다. 공유 runtime,
과거 증거, 백업 자료는 보존했다.

계획, 모든 scratch/RAW/JSON/JUnit/cache/runner/temp/DB, review-package 산출물은
PR에서 제외한다. Stage/commit/push/PR/새 branch/worktree 없음. 이 대화의
구현 이력이 없는 새 검토자가 다음 승인된 단계이며,
실제 결과를 추가할 예정이다. 미결 Owner 결정은 미결로 남는다.

<a id="2026-10-26--fresh-read-only-review-and-p2-correction"></a>

## 2026-10-26 — 새로운 읽기 전용 검토와 P2 수정

새 독립 검토자 한 명을 `fork_turns=none`으로 시작해, 구현 이력 대신
요구사항, base, 40개 파일 manifest를 전달했다.
모든 hash, HEAD/branch, 빈 index를 확인했다. 전체 한정
초안, SoT/현재 원격 합의, 보존 보고서를 읽었으며 테스트,
DB, validator 실행, 추가 agent 생성 또는 파일 변경은 하지 않았다. 최초 결과:
**P2 한 건, P1 없음, 추가 P3 없음**. 정적 검토이며 merge 승인이 아니다.

P2는 실제 경계 공백이었다. Runtime `TransactionRetryExhausted`는
SQLAlchemyError가 아닌 RuntimeError이므로, 주입된 Search resolver/gateway를 통해
전파되는 transaction 예외가 Search helper에 들어갈 수 있었다. Scratch에서
`outcome_unknown=True`로 재현하자 기존 RUNTIME_HANDLER_ERROR 대신 SEARCH_UNCLASSIFIED를
반환했다. 모든 현재 로컬 media 실행이 이 경로를 탄다는 뜻은 아니다.
정상 prepared source는 로컬 실행 상태를 사용한다.

검토 뒤 search_handlers.py와 failure-boundary 테스트만 변경했다.
수정은 기존의 명시적인 Runtime transaction 예외 네 개를 helper 전에 다시 던진다.
BeforeCommitFailure, CommitOutcomeUnknown, TransactionBoundaryError,
TransactionRetryExhausted다. RuntimeError 전체를 제외하거나
common DB runner/registry/T1 의미를 바꾸지 않는다. 회귀는
HINT/Coarse/Fine/resolver 전반의 DB 실패 여섯 건과 실제 transaction runner가
연결되지 않은 acquisition attempt 세 번을 소진하는 경로를 검증하며, helper 호출 없음과 리소스
종료를 확인한다. 첫 RED는 테스트 sleep 주입 실수 한 건을 포함해 21 FAIL/4 PASS였다.
수정한 RED2는 **21 FAIL/4 PASS**이며 모두 예상한 분류 실패였다.
최소 수정: **25 PASS**. 관련 handler/input/media/bootstrap/Recording factory와
DB transaction 오프라인 회귀: **167 PASS**, 12.59 s. 이는 별도
직접 실행이며 앞선 suite와 겹치므로 수치를 더하지 않는다.

같은 독립 검토자는 그 뒤 두 파일 delta만 읽기 전용으로 확인하고,
후속 hash 40개/나머지 파일 38개 그대로, 빈 index,
HEAD/branch 그대로임을 확인해 **P2 해결, 새 P1/P2 없음**으로 판단했다. 테스트는
실행하지 않았다. 두 번째 검토자나 추가 agent는 없었다. 이 결과를
추가하기 전 작성자는 delta가 해당 source/test 파일 두 개로 한정됨을 확인했다.

앞선 2254개 오프라인과 226개 MySQL 테스트 실행은 최종 예외
guard 변경 전이다. 해당 source revision에서의 직접 증거로 보존하며,
수정 후 실행으로 다시 표시하지 않는다. Guard만 바꾼 변경에는 전체 반복이나 새 MySQL 서버가
필요하지 않았다. SQL/수명주기/transaction 알고리즘은 바뀌지 않았으며,
167개 집중 테스트에는 실제 runner 소진 경로가 포함된다.
경계/Contract fixture/diff와 JSON/JUnit 누락 감사를 재검사했다.
실패한 RED/setup 실행은 구분해 유지한다. 앞서 명시한 전체 suite,
실제 provider, 원격 CI 미실행은 그대로 유효하다.

계속 판단을 유보하는 항목: 병합된 #403 통합과 미결 HINT taxonomy,
#405 terminal 정책, 제외된 clip/readout/export/자동 제품 orchestration,
대형 media/BLOB과 프로덕션 부하에서의 Search 내부 temp/SDK 수명주기,
전체 pytest/전체 필수 MySQL/현재 diff CI. 어느 것도 인수로 세지 않는다.
새 guard는 이 Owner/의존성 질문을 해결하지 않는다. 현재 원격
조회에서도 #297/#303은 동일 sink/helper 합의로 open이며 새
#403/#405 답변은 없다. 최종 상태: **IN_PROGRESS · Refs #297 (RT-10(b))**. 모든 수정은
unstaged/미커밋이며 push/PR/새 branch/worktree 없음. 전체 40개 파일 목록과
불변 review/evidence manifest는 제외된 scratch에 유지한다. 로컬 계획 두 개와
모든 RAW/JSON/JUnit/runner/temp/DB 산출물도 계속 PR에서 제외한다.

<a id="2026-10-26--merged-403-integration--pr-407-ci-reproduction"></a>

## 2026-10-26 — 병합된 #403 통합 / PR #407 CI 재현

**IN_PROGRESS · Refs #297 (RT-10(b))**. 새 사용자 요청은
병합된 Search helper/기본 registry 통합과 PR #407에서 실패한 process 사례
네 개로 한정된다. #405 STALE 소진 알림/receipt/Case 정책은 계속 제외한다.
이 후속 기록은 이력을 수정하지 않고 앞선 의존성 상태를 대체한다.

최초 checkout은 codex/rt12b-observability의
`42a4712d7f63eda64f3fd9766ac6765caae9869a`에서 깨끗했다. Tree와 index가 모두
깨끗함을 확인한 뒤 요청한 codex/rt10b-handler-registry 브랜치를 선택했으며,
`52629d4b562ee4ef03070e39fb23e83f44dcaf62`에서 역시 깨끗했다. 원격 PR #403은
fetch한 origin/develop인 `405512cd0c8b74fd602b9557668f8603fd9d286e`에 병합돼 있다.
브랜치와 들어오는 변경은 공통 base
42ddea72 이후 경로가 겹치지 않는다. No-commit merge는 충돌 없이 완료됐으며 의미 선택이나
충돌 해결은 수행하지 않았다. 자동 index 변경은 unstaged로 되돌렸다.
HEAD는 52629d4b, MERGE_HEAD는 405512cd이며, merge는 의도적으로
빈 index의 미커밋 상태다. 들어온 web/Search 파일은 upstream
통합에 속하며 이 작업에서 작성한 test/document 변경과 구분한다.

원격 증거는 직접 실행과 별도다.

- PR #403 head `8a5413109575631f8b0e0e8664274c96f443d325`: python-tests 실행
  40253669661과 boundary-check 40253669630 성공. 선행
  head CI 결과이며 이 미커밋 통합의 CI나 merge-SHA CI 주장이 아니다.
  Owner 후속 답변 6406363557은 intent auth/spent-budget 수정을 다룬다.
- PR #407 head 52629d4b: python-tests 실행 40230798384 / test job 121281892941
  실패. normal/partial/failed/fine_failed 각각 HTTP 호출을 1 대신
  0으로 보고했다. Nested actual-report 테스트도 같은 child 사례 네 개로 실패했으며,
  전체 원격 결과는 실패 5 / 통과 12182 / skip 33이었다. 이후
  MySQL execution-gate 단계는 skip됐다. 이 실행은 영구적으로 실패 기록으로 남으며,
  이후 로컬 통과로 다시 표시하지 않는다.

실제 helper 세 개는 이제 daesingo.search에서 import되며 기본 registry
검색도 이미 동작한다. 추가 프로덕션 dispatcher/taxonomy 코드는
필요하지 않다. Process helper의 임시 ConfirmedPolicyPort를 제거했다. 이제
failures override 없이 compose_search_registry를 호출한다. 새 오프라인 검사는
설치된 helper로 HINT/Coarse/Fine을 검증하며, Runtime input,
transaction, persistence, checkpoint 오류가 Search error
helper에 도달하지 않음을 관측한다. 최초 실패 세 건은 프로덕션 결함이 아니라
테스트 context/sink 불일치에서 나왔다. 해당 setup 실행은 별도 보존하며 수정된
특성 확인은 15건 통과다. Search 결과/예외는 Owner 매핑을 유지하며,
로컬 재분류는 없다.

실제 CI 실패를 로컬에서 재현했다. 원래 Windows 사례는 통과했지만
Ubuntu ffmpeg/ffprobe 6.1.1에서 동일한 HTTP-0 실패 네 건이 발생했다
(linux-process-baseline: 4건 실패, 203.25 s). Scratch 예외 추적으로
Recording 출력 검증에서 마지막 frame duration/pkt_duration 누락을 확인했다. Probe
snapshot에서는 생성된 H.264 MP4 두 변형(B frame 있음/없음) 모두 기존
엄격 검사를 실패하고, 생성 MPEG-4 AVI는 관측 coverage로 통과한다.
Recording 정책을 완화하지 않으며 fps나
container duration으로 frame tail을 만들어내지 않는다. 통합 fixture는 이제 지원되는 AVI 입력을
일치하는 filename suffix/MIME과 함께 사용한다. 생성 media, 공개 preparation, 실제
Search media 변환은 테스트에 남긴다. 이는 예전 ffprobe에서 일반적인 H.264
MP4 호환성을 보증하지 않으며, 기존 한계를 명시적으로 유지한다.

Process 테스트는 HTTP 정확히 1회와 pool checkout 0개 assertion을 유지하고, 비공개 테스트 pipe에
예상 terminal status/failure-kind 진단을 추가하며 HINT
시나리오를 추가한다. 별도 HINT Worker를 실행해 Case의 기존 T2가 Coarse를 발급하는지
관측한 뒤 별도 Coarse/Fine Worker를 사용한다. Fine 선택/발급은 여전히 테스트에서
Case를 통해 명시적으로 수행하며, Runtime은 orchestration 정책을 갖지 않는다.
기존 HTTP 공개 필드 privacy assertion은 계속 유효하다.

이 체크포인트의 직접 증거(겹치는 실행은 합산하지 않음):

| 실행 | 결과 |
| --- | --- |
| 최초 병합 import/경계 기준선 | 73건 통과 |
| 실제 helper/기본 통합 + Owner SDK auth/timeout/usage 검사 | 151건 통과, 6.19 s |
| 관련 Search/Worker/Case/jobs/usage/Recording/Readout/API 오프라인 | 2328건 통과 / 기존 skip 21건 / 970건 선택 해제, 327.87 s |
| 실제 MySQL T1 payload/rollback/COMMIT 결과 불명, usage/cancel, 저장된 T2 | 72건 통과, 58.99 s |
| Windows process 사례, 실제 기본 helper + HINT 사용 | 5건 통과, 91.22 s |
| 변경하지 않은 gate bypass/JUnit/parameter 변형 제어 | 14건 통과(앞선 중복 부분집합 4건 통과) |
| 경계 / Contract fixture / diff | 위반 0건; 검사 62/26/104; diff PASS |

오프라인 skip은 계속 선택적 typer import 네 개, Case 외부 동영상 두 개,
Recording 실제 동영상 opt-in 열다섯 개다. 경고는 기존
FastAPI/httpx 폐기 예정 경고 한 건과 malformed-usage 직렬화 경고 세 건이다.
Skip/xfail 정책은 바꾸지 않았다.

linux-process-green이라는 중간 파일은 **5건 실패**이며 통과가 아니다. Media fixture를
수정한 뒤 WSL 공유 filesystem I/O가 peer 응답 timeout을 일으켰다
(472.50 s). 이후 추적한 AVI normal 실행도 timeout됐다. 해당 실행은
실패로 보존한다. Timeout은 늘리지 않았다. Ubuntu package는 소유한
테스트 scratch에만 풀고, 도구와 임시 media를
소유한 Linux-native /tmp 디렉터리에 배치했다. 같은 코드의 normal은 이후
원래 peer별 timeout으로 92.25 s에 통과했다. 전체 Linux-native matrix는
이 시간순 체크포인트에서 아직 실행 중이며, 결과를 아래에 추가할 예정이다.

<a id="final-direct-validation-and-resource-audit"></a>

### 최종 직접 검증과 리소스 감사

전체 Linux-native 실행은 **5건 통과, 474.95 s**로 끝났다. normal, partial,
failed, fine_failed, hint다. PR #407 CI에 보고된 것과 같은 Ubuntu ffmpeg/ffprobe
6.1.1-3ubuntu5를 사용한다. Windows와 Linux 최종 실행 사이에
코드 변경은 없었고, 후자는 테스트 도구/media의 filesystem 배치만 변경했다.
최초의 같은 코드 native normal 검사는 이 실행과 겹치며 합산하지 않는다.
앞선 테스트 다섯 개의 WSL timeout 실행은 filename에
green이 있어도 실패로 남는다. 이는 최초 fixture 실패와 로컬 테스트
환경 지연을 구분하며, 늘린 timeout이나 fake 기능으로 숨기지 않았다.

최종 직접 DB 보고서는 테스트 72개/setup-call-teardown phase 216개, Windows
process 5/15, Linux process 5/15다. 각각 고유하고 완전한 collection/selection,
모든 phase 통과, collection 오류 없음, skip/xfail 없음을 갖는다. 변경하지 않은 JUnit
validator는 각 보고서를 허용하며, 실제 JUnit testcase 제거는 거부한다.
전체 inventory validator는 필수 role 누락으로 각 부분집합을 거부하므로,
**전체 strict MySQL gate는 PASS가 아니다**. 모든 프로덕션 source와 보호된
Contract/gate/harness/workflow 경로는 충돌 없이 통합된 snapshot과 일치한다.
작성한 변경은 테스트와 시간순 문서뿐이다.

전체 pytest, 전체 필수 MySQL/nested wrapper, 전체 gate 변형
matrix, 실제 유료 provider, 광범위한 media/BLOB 인수, 현재 diff 원격
CI는 실행하지 않았다. 관련 오프라인 2328개, helper 집중 151개, 실제 DB72,
양 OS process matrix가 이 통합을 검증한다. 전체 원격
inventory 반복은 중복 검증이며 미커밋/미푸시 revision의 CI 증거를
만들 수 없다. 이전 원격 #407 실패는 이 로컬 결과로 해소되지
않는다. Workflow 30분, nested MySQL900초, peer별60초,
runner880초를 유지했다.

소유한 MySQL8.4.7을 중지하고 정확한 datadir를 제거했으며 port는 새
연결을 거부했다. 종료 전에는 시스템 스키마/기본 계정과
전용 base schema만 남았다. 비감사 client, transaction, lock은
없었다. Process test peer는 join했다. Package hash와
증거를 보존한 뒤 소유한 Linux-native 도구/media, 새로
다운로드한 host package cache를 제거했다. 새 빈 root lock 파일 두 개
(unignored, 최초의 깨끗한 checkout에는 없음)를 배타적으로 열고 백업한 뒤 제거했다. 공유 runtime과
앞선 증거는 보존했다. 모든 새 scratch/RAW/JSON/JUnit/runner/probe/stack,
임시 DB 자료는 PR에서 제외한다.

사용자의 명시적 범위 지침에 따라 #405는 미결로 둔다. Clip/readout/export
handler, 일반적인 예전 ffprobe H.264 MP4 coverage, 프로덕션 provider/temp/SDK
수명주기 인수는 이 한정 통합 밖이다. 추가 Runtime
매핑이나 T2/case_applied_at 확장은 도입하지 않았다. 다음 단계는 이 통합 delta에 대한
새 context의 읽기 전용 검토 한 번이며, 실행 이력을 바꾸지 않고
결과를 추가한다. HEAD52629d4b / MERGE_HEAD405512cd와
빈 index를 유지하며 staging/commit/push/PR 갱신은 없다.

<a id="usage-limit-resume-additional-develop-update-and-review-follow-up"></a>

### 사용량 한도 후 재개, 추가 develop 갱신 및 검토 후속 기록

첫 새 검토 turn은 계정 사용량 한도에서 멈췄으며
검토 판정을 내지 못했다. 사용자의 명시적 재개 요청에 따라 작성자는
검토 hash 57개, HEAD52629d4b/MERGE_HEAD405512cd, 빈 index, 충돌 없음을 검증한 뒤
같은 독립 검토자를 재개했다. 읽기 전용 검토는 P1/P2 없음과
P3 한 건을 발견했다. 새 HINT 시나리오는 Coarse 발급은 확인했지만 추출된
값은 확인하지 않았다. Coverage 공백이며 관측된 프로덕션 결함은 아니다. 이제 테스트는
공개 CaseView가 provider fixture에서 온 vehicle="white car"와
situation="red signal"을 보존하는지도 확인한다. 검토자는 테스트를 실행하지 않았다.

재개 중 새 원격 조회에서 develop이
`a08d671547a9e1a79deac2464d0d0ae43f34f17f`로 진행한 것을 확인했다(#395 병합). 추가 경로
열 개에는 Search provider cut-off-response 처리와 테스트/실험
기록/script가 포함된다. 작성한 파일 여섯 개와는 겹치지 않는다. 옛/새 자동
merge tree를 모두 내용 충돌 없이 계산하고 현재 파일 57개를
백업했으며, 갱신 전 옛 tree에 대해 추가 경로를 확인했다.
최초 갱신 시도는 index stat 데이터가 갱신되지 않아 거부됐다.
MERGE_HEAD의 직접 update-ref도 Git이 거부했다. 어느 쪽도
내용 충돌이나 성공한 갱신이 아니다. Index를 복원했고 작성한
hash는 온전했다. Stat 데이터 갱신 뒤 two-tree update가 성공했다.
파일 열 개는 upstream과 정확히 일치했고 작성한 hash 여섯 개는 모두
그대로였다. Guard를 둔 pending-merge metadata는 원자적으로 a08d6715에 설정했다
(Git update-ref는 이 pseudoref를 허용하지 않음). 자동 index 변경은
다시 unstaged로 되돌렸다. Commit/rebase/새 branch/worktree는 생성하지 않았다. HEAD는
52629d4b를 유지한다. MERGE_HEAD와 fetch한 origin/develop은 이제 a08d6715이며 index는 비어 있다.

이 최신 source의 직접 재검증은 405512cd 실행과 별도로 유지한다.

| 실행 | 결과 |
| --- | --- |
| 실제 helper/SDK/usage/runtime failure 경계 집중 검사 | 153건 통과, 15.14 s |
| 실제 MySQL T1/receipt/COMMIT 결과 불명/usage/cancel/T2 | 72건 통과, 52.42 s |
| Windows 별도 API/Worker normal/partial/failed/fine_failed/hint | 5건 통과, 95.62 s |
| 경계 / Contract fixture / diff | 위반 0건; 검사 62/26/104; PASS |

최신 process 사례 다섯 개에는 새 공개 HINT 값 assertion 두 개와
HTTP1/pool0/terminal/privacy 검사가 포함된다. 최신 DB 증거는 테스트 72개/phase 216개와
5/15이며 완전/고유/모두 통과/skip-xfail 없음이다. 실제 JUnit 누락은 거부하며,
전체 inventory는 여전히 필수 role 누락으로 이 부분집합을 거부한다. 프로덕션
source는 최신 자동 통합 snapshot과 일치한다. 작성한 프로덕션
코드, taxonomy 또는 정책 변경은 추가하지 않았다.

앞선 offline2328과 Linux5 실행은 계속 405512cd source의 증거이며,
a08d6715 실행으로 다시 표시하지 않는다. 추가 변경 뒤 전체를 반복하지
않았다. Provider 오류 처리/import와 Owner 테스트만 바뀌었고,
media/Runtime DB/worker 코드는 그대로였다. 최신 focused153은
새 SDK length/content-filter 예외 사례를 검증하며, 최신 Windows process5와
DB72는 통합 경로를 검증한다. 여덟 분 Linux matrix와 portable
tool 재설치/전체 오프라인 반복은 바뀌지 않은 platform 검증을
중복한다. 전체 pytest/필수 nested gate/전체 변형/실제 provider/현재
diff 원격 CI는 미실행이며, 전체 gate나 원격 CI PASS를 주장하지 않는다.

두 번째 검증은 별도 소유 MySQL 서버와 구별되는 report/
readiness/CA/shutdown 기록을 사용하며, 첫 서버 증거/로그 사본은 유지한다.
최종 정리와 추가 delta에 대한 같은 검토자의 읽기 전용
평가는 아래에 기록한다. #405와 앞서 제외한 인수 사항은 계속
미결이다. **IN_PROGRESS · Refs #297 (RT-10(b))**.


<a id="final-independent-read-only-re-review-and-handoff"></a>

### 최종 독립 읽기 전용 재검토와 인계

같은 독립 검토자는 작성자의 대화를 상속하지 않고 추가 develop delta와 HINT
assertion 두 개를 확인했다. P3 해결을 확인했으며
**새 P1/P2/P3 없음**으로 판단했다. 최신 manifest hash62개 전체와
통합 snapshot의2136개 파일을 읽고, 추가 upstream 파일 열 개를
각 a08d6715 Git blob과 대조했으며 HEAD52629d4b/MERGE_HEADa08d6715, 빈 index,
충돌 항목이 없음을 확인했다. 작성자의 JUnit153/72/5를 읽었지만 테스트,
DB, validator를 실행하거나 file/ref/index를 변경하거나 추가 agent를 만들지 않았다. 판단은
한정된 정적 검토이며 전체 RT-10 인수나 merge/원격 CI 승인이 아니다.

결과 기록 전 작성자는 hash62개가 모두 그대로임을 재확인했다.
두 번째 소유 MySQL8.4.7도 종료했다. 정확한 datadir는 없고 port는
연결을 거부하며, 기본 시스템 계정/스키마와 전용 base만 남고,
비감사 client/transaction/lock은 없다. 원래 서버 로그 사본,
두 실행 이력, 검토 source snapshot은 별도로 유지한다. Root
lock 잔여물이나 소유한 native media/tool은 없다. Scratch 증거는 보존하며
PR 범위에서 제외한다.

최신 source Linux 전체 process 실행, 전체 pytest/필수 nested gate/
변형 suite/현재 미커밋 CI, 일반적인 예전 ffprobe MP4/대형 media/실제
provider/운영 수명주기, 제외된 clip/readout/export, 전체 RT-10
인수는 위 기록대로 미실행 또는 판단 유보다. #405는 명시적으로
미결이다. 최종 작성 delta는 test/document 파일 여섯 개이며 자동
upstream 경로56개와 별도다(working-tree 전체 경로 62개). 최종 상태는 **IN_PROGRESS · Refs
#297 (RT-10(b))**이며 빈 index의 미커밋 merge 대기 상태다. Commit/push/PR
변경은 없다. 통합을 게시하기 전에 사용자에게 결과를 전달한다.

<a id="2026-10-26--pr-407-timeout-systematic-investigation-and-bounded-optimization"></a>

### 2026-10-26 — PR #407 timeout: 체계적 조사와 한정 최적화

**IN_PROGRESS · Refs #297 (RT-10(b)).** 최초 브랜치는
`codex/rt10b-handler-registry`, HEAD는
`dac940dc2bb638a56df8fa03953c77c6f171ac96`이며 working tree와 index는 비어 있었다.
Branch/ref/index 작업은 필요하지 않았다. 읽기 전용 원격 검사는
같은 PR head, base/develop `1943cb51e2bd579a02f09d67f104f16c52666c88`, Draft,
MERGEABLE/UNSTABLE, boundary 성공, python-tests 취소를 확인했다. 원격
workflow 재실행이나 PR 변경은 하지 않았다.

보존한 PR 로그는 run40321183978/job121566213929이며, 최신 성공
develop push는 정확히 해당 base의 run40320484510/job121563856235다. 다음은
명시적으로 이름 붙인 pytest summary를 제외하면 GitHub step 타임스탬프다.

| 단계 | 성공한 develop | PR #407 | 해석 |
| --- | --- | --- | --- |
| Setup/container/checkout/tools, smoke 제외 | 53s | 59s | 기록된 setup step 시간 합계; +6s |
| 합성 media smoke step | 3s | 4s | pytest 자체 1.25s 대1.33s; 둘 다1건 통과 |
| 전체 pytest step | 1729s, SUCCESS | 1754s, CANCELLED | 미완료 PR 시간은 완료 suite의 회귀 차이가 아님 |
| 전체 pytest summary | 12446건 통과/33건 skip,1721.76s | 없음 | 취소 로그에 명시적 실패나 최종 summary 없음 |
| 후속 strict MySQL gate | 1s,1027개 테스트,skip0/xfail0 | SKIPPED | PR에는 이 단계의 성공 증거 없음 |
| 전체 job | 1789s | 취소/정리 포함 1821s | 성공 기준선도 이미30분에 가까움 |

PR의 마지막 전체 progress 행은12:45:37.2756209Z(97%,12312개 outcome
문자)이며 취소는12:46:09.123704Z다. 완료된 progress 행에는 `F`/`E`가
없다. 미완료 테스트 통과를 입증하는 것은 아니다.
원격 quiet 출력은 활성 node를 식별하지 못한다. 새 **Linux
collection-only** 실행에는12610개 항목이 있다. 추가 테스트135개를 빼면 base
항목12475개가 도출돼 성공한 원격 outcome 수와 일치한다(module collection skip은
별도). 이는 도출한 기준선 순서이며 실행한 base checkout이 아니다.
Windows에는 OS별 매개변수16개가 추가되므로 보정 없이 사용하면 안 된다.

Linux collection/순서가 일치하고 pytest가 보통처럼72문자 단위로
progress를 flush한다는 조건에서, 가능한 활성 범위는 item12312의 teardown부터
다음 미출력 블록 끝12384까지다. redelivery12312-12343,
reflection12344-12383, 첫 search-capability item12384다. 이는
후보 범위이며 기록된 활성 node 진단이나 hang 증거가 아니다.

동일 common-node block1081-1152는 develop에서741.282535s, PR에서783.925966s였다
(+42.643431s). 여기에는1142의 nested real-MySQL 테스트 **외에도71개
항목**이 있다. 캡처된 child stdout 때문에 원격에서는 child/mutation 경계가 보이지 않는다.
이를 둘러싼 gate-unit block1153-9648은173.452s 대172.184s로 증가가 없었다.
새 E2E 인접 구간10441-10512는25.744s 대81.334s였다. 마지막 common
항목 다섯 개는 삽입한 시나리오 다섯 개로 인해 달라지므로55.590s는 인접 구간
비교이며 새 테스트 시간의 정확한 합이 아니다. 다른 새 테스트와
개별 nested/mutation 비용은 원격 quiet 로그로 분리할 수 없다.
새 E2E 다섯 개는 필수 nested inventory 내부에서도 실행된다. 증거는
추가 작업에 따른 총 budget 압박을 지지하며, 테스트 하나를 원인으로 지목하지 않는다.

새 합성 진단은 DB를 띄우거나 실제 MySQL 인수를 주장하지 않고
기존 전체 mutation 본문을 실행했다. Linux cProfile은
수정 전232.17s/후73.72s를 측정했고, deepcopy 누적 비용은 전171.27s/후0.67s였다.
Windows cProfile은274.72s/144.69s를 측정했다. 계측한 로컬 값이며
원격 CI 절감량이 아니다. **프로파일링하지 않은 직렬 Linux 한 쌍**은 수정 전68.014s,
후40.442s(27.573s 감소)였다. 두 실행 모두 새995-node 합성 보고서를
사용하고 HEAD의 mutation 본문과 현재 본문을 비교했으며 두 입력 보고서는
그대로 유지했다. 생성 산출물 SHA256 값2842개가 모두 일치했고, 여기에는
parameter mutation 기록8415개도 포함된다. 이 host에서 다른 로컬 검증도 실행 중이었다.
이 시간은 진단 관측이며 통제된 CI budget 예측이 아니다.

최소 변경은 증거 복사만 줄인다. Family 누락은 필터링한
목록을 소유하고 읽기 전용 node를 유지하며, metadata 누락은 기존
단일 node 격리 helper를 재사용한다. 모든 새 nested 호출, inventory, JSON/
JUnit 검증, 생성 mutation XML을 유지한다. 제품 코드,
validator, workflow, 필수 검사, skip/xfail 규칙,900s/30분 제한, 재시도,
receipt, #405 정책 변경은 없다. AST 검사는 동일한 integration
inventory와 fresh-child/validation prefix를 확인한다. Workflow/validator/harness/gate
unit source byte는 HEAD와 같다.

TDD는 처음 omission helper가 없어 실패했고(1건 실패/2건 통과,
0.62s), 이후 기존 full-copy 알고리즘을 재현해 유지한 증거 복사에서
실패했다(1건 실패/2건 통과,0.66s). 최적화한 helper는 테스트3개를
0.40s에 통과했다. RED 출력은 별도로 보존하며 성공으로 다시 표시하지 않는다.
전체 gate-unit/helper 실행은 테스트8412개를383.37s에 통과했다(Windows, 명령 경과
386.66s). 직접 경계 검사는 위반0건, Contract fixture는
구조62/JSON 26/의미104개 검사 통과였다. 이어 별도 소유8.4.7 loopback 서버에서
전체 새 실제 MySQL nested 인수를 시작했으며, 최종 결과와
정리는 아래에 이어진다. 이전 JSON/JUnit/report를 이 변경의 인수로
사용하지 않는다. Scratch RAW, JSON/JUnit, timing probe, profile, runner, DB
자료는 PR 범위에서 제외한다.

이 dirty 후보에 대한 전체 outer pytest/현재 원격 CI는 실행하지
않았다. 집중 gate unit과 전체 새 nested inventory는 유일한
변경 동작을 겨냥하며 또 다른 전체30분 작업 중복을 피한다.
원격 활성 node 식별값, 새 테스트별 정확한 원격 시간, 이
최적화만으로30분 budget이 복원되는지는 미확인이다. Merge 준비를 주장하려면
새 원격 CI가 기존 제한 안에서 전체 pytest summary와 후속 strict gate를
**모두** 완료해야 한다.

진단 setup 실패는 인수 결과와 별도다. 최초
합성 driver는 unit 수준 `write_junit` helper가 있다고 가정해 AttributeError로
중단했고 mutation 본문에 진입하지 않았다. 수정한
scratch driver는 자체 합성 XML을 만든다. 최초 비특권 WSL
collection 시도는 collection 전에 E_ACCESSDENIED로 거부됐으며
승인된 읽기 전용 host 접근으로 다시 실행했다. 이 시도는 PASS로 바꾸거나
이후 측정 실행과 합치지 않는다.


<a id="fresh-mysqlmutation-completion-and-review-handoff--2026-10-26"></a>

### 새 MySQL/mutation 완료와 검토 인계 — 2026-10-26

별도 Windows pytest 호출은 실제 nested-gate parent를 통과했다.
**966.96s에1건 통과**(명령 경과969.59s, parent call966.77s). 새로
실행한 child는 선택 항목1027개, 통과 phase3081개, skip/xfail 없음,
JUnit suite 시간838.736s다. Subprocess900s 제한은 그대로다. Parent는 해당
subprocess가 끝난 뒤 검증/변형도 수행한다. 관측된 child
phase-report 구간은835.0s다. Parent call과의 차이에는 child
시작/종료, report 처리, 검증, mutation이 포함된다. 정확하게
분리한 mutation timer나 원격 시간 비교가 아니다.

Child는 normal/partial/failed/fine_failed/hint를 포함한 실제
프로덕션 process 시나리오 다섯 개를 검증한다. 새 setup+call+teardown 시간 합은
95.756s(각각22.018/19.054/12.066/17.435/25.183s)다. Worker HTTP-call1,
pool-checkout0, 실제 T1/T2/produced assertion은 그대로 실행했다.
모든8415개 parameter mutation과1501개 metadata/family 누락을 거부했다.
직접 strict CLI는 새 child의 JSON/JUnit을 허용한다(exit0). 별도
사본에서 setup phase 또는 JUnit testcase 하나를 누락하면 거부한다(각 exit1).
의도적인 음성 결과는 별도 기록으로 남긴다.

Collection-only 검사로 현재 MySQL 표시 테스트1045개를 확인했다.
Nested1027개와 별도 실행한 parent는 현재 MySQL 전체 호출을
구성하지 **않는다**. 변경하지 않은 다른 테스트 열일곱 개는 재실행하지 않았다.
Durable facts6, Case composition4, Search handlers3, Case execution-read/result-
reflection4다. 전체 outer pytest와 모든 MySQL의 한 프로세스 실행은 미실행이며,
변경한 mutation 경로는 전체 새 필수
nested 명령과8412개 gate-unit/helper 테스트로 검증했다. 로컬 검증 명령 시간은
22분을 넘는다(실행은 겹쳤으므로 wall time이 아님).
추가 전체 제품 회귀는 바뀌지 않은 코드 검증을
중복한다. 원격 develop의1027개 gate와 이 child의1027개는 서로 다른
집합이며 상호 대체 가능한 증거로 취급하면 안 된다. 이전 CI 산출물을
새 nested 테스트에 대신 넣지 않았다.

소유한 MySQL8.4.7은 schema/account/client/transaction/lock 감사를 마친 뒤
종료했고 정확한 UUID datadir를 제거했다. Linux listener 종료도 확인했다.
원래 증거 report, RAW, JSON/JUnit, mutation XML, probe, runner는 ignored 작업 scratch 아래에만
보존하며 PR 범위에서 제외한다. 다른 서비스/예전 scratch는
수정하지 않았다. 최종 Windows port 검사와 새 독립 읽기 전용
검토는 아래에 별도 기록한다.

제품/Contract/Accepted Decision/Baseline 또는 CI 정책 delta는 없다.
#405 STALE 알림/receipt/Case 정책은 계속 미결이다. 남은 merge
차단 요인은 기존30분/900s 제한 안에서 새 원격 전체 pytest와 후속 strict gate를
완료하는 일이다. 로컬 속도 향상이 budget 충족을 입증하지는 않는다.
Staging, commit, push, PR 변경 또는 CI 재실행은 없었다.


정리 한정사항: Linux 종료 receipt는 auditor와 MySQL 시스템 event scheduler 외
client 없음, transaction0/lock0, 시스템 계정/스키마와 전용 base만
존재, 소유 process 종료, UUID datadir 없음, Linux connect_ex111을
확인한다. 최초 Windows probe는10013으로 거부됐다.
이후 승인된 host 접근은2s 뒤10035를 반환했으므로 즉각적인 Windows 연결
거부는 **확인되지 않았다**. 공유 WSL/forwarding 서비스는 바꾸지 않았다.
이는 정리 관측 가능성의 한계이며 MySQL
프로세스가 남았다는 증거가 아니다. 새 검토자는 미커밋 파일 다섯 개 delta와
별도 표시 증거만 평가한다. 인계 시 source/ref/index는 그대로다.


<a id="fresh-independent-read-only-review-result--2026-10-26"></a>

### 새로운 독립 읽기 전용 검토 결과 — 2026-10-26

새 검토자는 `fork_turns=none`으로 미커밋 파일 다섯 개 delta,
해당 SoT, 보존 증거만 확인했다. 이 범위에서 **P1/P2/P3 없음**으로 판단했다. 현재
family consumer/validator는 유지한 node를 수정하지 않으며, 단일 node metadata
복사는 원래 격리를 보존하고, 누락 assertion/XML/새 child/
제한도 온전하다. 원시 hash와 JSON/JUnit 수치를 독립적으로 읽었으며,
보존된 작성자 실행과 자신의 읽기 전용
검사를 명확히 구분했다. Test/DB/원격 CI를 실행하거나 수정 또는 subagent 생성을 하지 않았다.
검토 전후 branch/HEAD/index와 manifest hash 다섯 개가 모두 그대로였다.
작성자는 이 결과와 log 항목만 추가하기 전에 다섯 개 모두 재검증했으며,
검토한 source snapshot은 ignored scratch에 남긴다.

이는 전체 RT-10 인수나 merge 준비 판정이 아니다. 현재 전체
원격 pytest와 후속 strict gate, 실제 CI 절감량, 원격 활성 node
식별값은 계속 미확인이며 #405도 미결이다. 최종 전달 상태는
**IN_PROGRESS · Refs #297 (RT-10(b))**, 미커밋/unstaged이며 branch,
commit/push/PR 또는 CI 변경은 없다.


<a id="2026-10-27--pr-407-second-timeout-tail-and-unit-fixture-investigation"></a>

### 2026-10-27 — PR #407 두 번째 timeout: tail과 unit fixture 조사

**IN_PROGRESS · Refs #297 (RT-10(b)).** 최초 브랜치는
`codex/rt10b-handler-registry`, HEAD는
`bc45925595dd540012432cd6dabd90ddcf06c9b6`이며 working tree/index는 깨끗했다. Branch,
ref, staging, commit/push, PR 또는 CI 작업은 수행하지 않았다. 읽기 전용 PR metadata는
해당 head, Draft/MERGEABLE/UNSTABLE, boundary 성공, 새로운
python-tests 취소를 확인했다. 해당 commit에는 앞선 evidence-copy
최적화가 포함돼 있으며, 위의 과거 조사/검토 이력은 그대로다.

현재 run40334969445/job121613963782와 앞선
40321183978/job121566213929는 별도 보존한다. 새 원격 조회에서
더 최근의 성공 develop run40331287437/job121601052393을
`4295abfff7e89297a75762ba653678240c8280d9`에서 확인했다. 이전 develop
기준선1943cb51과 비교해 Case 결정 문서 세 개만 바뀌었고 code/test는 바뀌지 않았다.
이 최신 성공을 아래의 주 비교 대상으로 삼으며, 이전 성공 실행과
RAW는 별도 이름을 붙인 네 번째 series로 남긴다. Checkout은 갱신하지 않았다.

| 기록된 단계/구간 | 이전 PR | 최신 PR | 최신 성공 develop |
| --- | --- | --- | --- |
| Smoke 제외 setup step 합계 | 59s | 51s | 57s |
| Media smoke step | 4s | 4s | 4s |
| 전체 pytest step | 1754s CANCELLED | 1761s CANCELLED | 1693s SUCCESS |
| 동일 outcome1081-1152 block | 783.926s | 742.443s | 720.580s |
| 동일 gate-unit 내부1225-9576 | 143.509s | 163.816s | 138.776s |
| 최종 전체 pytest summary | 없음 | 없음 | 12446건 통과/33건 skip,1686.74s |
| 후속 strict gate | SKIPPED | SKIPPED | SUCCESS,1027개 테스트/skip0/xfail0 |

내부 구간 두 행은 전체 pytest의 일부이며 더할 추가 단계가 아니다.
추론한 common-node 끝점은 모든 revision에서 일치한다. Nested를 포함한
block에는1142의 실제 parent와 다른 테스트71개가 포함된다. 전체 block에서 이전 PR 대비
41.483s 감소가 관측되지만, 원격 로그로 child와 mutation 비용을
나누거나 감소 전체를 함수 하나에 귀속할 수는 없다.
Unit 내부는20.307s 늘어 여유 일부를 소모했다. 같은 숫자 offset의 E2E/tail
block은 unit/새 RT-10 테스트 추가 뒤 끝점이 달라졌다.
따라서 정확한 node별 비교가 아닌 인접 구간으로만
유지한다. 기계 비교는 끝점 일치 여부를 명시적으로 기록한다.

최신 마지막 progress:12456개 outcome 문자(12427개 점/29개 skip),98%,
2026-10-26T14:25:54.3041261Z. 취소는28.709s 뒤인14:26:23.0134016Z다.
F/E/xfail 또는 최종 pytest summary는 관측하지 못했다. 손대지 않은 head에서 새로 한 Linux
collection에는12611개 항목이 있다. Collection/순서 일치와 보통의72-outcome
flush를 가정하면, 가능한 활성 작업은12456의 teardown 또는 다음 progress 행 전
12528까지의 후속 작업이다. 마지막 추론 node는
`test_search_failure_boundary.py::test_persistence_error_propagating_through_search_is_still_runtime_owned[resolver-error5]`다.
73개 항목의 후보 구간은 남은 Search boundary 테스트, handler,
handler MySQL/input, 전체 sweep-worker 테스트, reconciliation/usage, 첫
usage-worker MySQL 사례를 포함한다. 특정 원격 활성 node나 hang은 확인되지 않았다.
아래에서 새로 작성한 unit guard 두 개는 이 과거 collection 밖이다.

**직접 tail 실행:** 마지막 보고 node와 미출력 node155개 전체를
collection plugin으로 확인한 원래 Linux 순서 그대로 실행했다.
총156개가176.86s에 통과했고(명령185.66s), setup/call/teardown report468개가
통과했으며 skip/xfail은 없었다. Node별 값과 순서는 작업의 ignored
`tail-node-phase-summary.json`에 있다. Phase 시간 합계에는 다음이 포함된다.

| Tail 파일 그룹 | Setup | Call | Teardown |
| --- | --- | --- | --- |
| sweep-worker MySQL31 | 19.380s | 101.433s | 1.282s |
| worker MySQL20 | 11.368s | 8.984s | 0.743s |
| Search handler MySQL3 | 3.297s | 8.200s | 0.132s |
| usage reconciliation MySQL6 | 3.049s | 4.693s | 0.195s |

관측한 전체 phase 시간은168.367s이며 다른 시간에는 collection/reporting이 포함된다.
Sweep subprocess 테스트는 정당한 인수 작업이므로 그대로 유지했다.
로컬 Linux/WSL filesystem, 부하, MySQL8.4.7은 GitHub와 다르므로 이 시간은
원격 잔여 시간 예측이 아니다. 제품 wait/lease/cleanup이나
process 검증 범위는 줄이지 않았다.

**확인한 회피 가능 비용:** 변경 전 전체 unit/helper profile은
테스트8412개를167.78s에 통과했다. 번호를 붙이는 임시 디렉터리 할당6077회가
누적28.983s를 소모했으며, suffix를 찾는 동안 find_prefixed generator 호출/재개
18425500회가 있었다(정확한 scandir-entry 수는 아님).
이는 앞선 증거 디렉터리에 따라 증가한다. Role 누락은 새로 만든 독립 소유 합성 보고서를
불필요하게 다시 deep-copy했다. Deepcopy 최상위304회/
재귀14889721회가23.677s를 소모했다. 직접 측정한 fixture
비용이며 원격 timeout의 유일한 원인을 입증하지 않는다. 원격 전체
증상은 여전히 누적 작업이 기존 budget을 초과하는 것이다.

**최소 TDD 변경:** 이 unit 파일만 pytest의 공개 factory를 통해 각 parameter 사례의 새
UUID 디렉터리를 `numbered=False`로 할당한다. 동일한
관리 base 안에서 같은 `junit.xml` writer/validator를 사용한다. Outer
report 목적지, artifact 전달/구조, CI orchestration,
retention 설정, inventory, 테스트 identity/selection, 인수 검사는 바꾸지 않는다.
Role 누락은 두 번째 전체 복사 없이 이미 새로 만든 report를 사용한다.
Baseline/synthetic/actual 검증 결과를 실행 간 cache하거나 재사용하지 않는다.

Guard는 sibling directory scan과 새 report deepcopy를 거부한다. 최초
Windows 집중 시도는 소유한 basetemp를 생략해 기본 임시
root 할당에서 실패했다. 이 실패는 보존하며 유효한 RED/GREEN으로 부르지 않는다.
명시적 새 workspace basetemp에서는 두 기존 알고리즘이 의도한
guard에 실패했고(2건 실패,0.96s), 최소 구현과 기존 XML-call guard는
테스트3개를 통과했다(0.93s). 이후 전체 Linux unit/helper profile은 테스트8414개를
160.73s에 통과했으며, 원래 모든 사례와 guard 두 개를 유지했다.

번호 부여 할당은6077→8, find_prefixed 재개는18425500→17로 줄었다. Deepcopy 최상위는
304→5, 누적 시간은23.677→0.091s다. 전체 profile wall 개선은7.05s뿐이다.
동시 로컬 DB 검증과 관측한 filesystem stat 시간6.894→33.910s,
subprocess 대기가 다르다. 이를 CI
속도 향상 주장으로 바꾸지 않는다. 별도 비프로파일링 직렬 한 쌍은 실제 pytest 임시 경로 할당기와 새
합성 report로 role299개와 parameter6069개 검사를 모두 실행했다.
53.123→33.879s였으며, 생성 mutation XML hash1734개가 모두 일치했다.
이 비교는 전체 pytest overhead와 실제 MySQL 인수를 제외한다.

진단 후처리는 baseline pytest가 이미 exit0으로 끝난 뒤 pstats가 str 대신
Path를 받아 최초 실패했다. Driver 실패와
pytest 결과는 별도다. 기존 profile은 재실행하거나 다시 표시하지 않고
읽었다. 최초 byte 수준 불변 검사도 변경되지 않은
CRLF checkout helper 때문에 실패했다. Raw/HEAD hash, 줄바꿈 정규화 동일성, 빈 Git
diff를 명시적으로 기록한다. 해당 helper source는 변경하지 않았다.

AST/정규화 내용 검사는 unit inventory, 모든 기존
parametrization, strict validator, mysql harness, actual mutation helper,
nested 명령/900s 제한, workflow30분을 보존한다. 제품/Contract/Decision/
Baseline delta, 테스트 제외, job 분리, timeout 증가, required-check
변경은 없다. #405는 계속 미결이다. 새 actual nested/evidence 검증과
리소스 정리 결과는 아래에 이어진다. 예전 actual report를 대신 쓰지 않는다.


<a id="fresh-actual-evidence-scope-and-cleanup--2026-10-27"></a>

### 새로운 실제 증거, 범위 및 정리 — 2026-10-27

변경 후 새 real-MySQL nested parent는697.52s에 테스트1개를 통과했다(명령
699.42s). 새로 실행한 child는 선택 테스트1027개/통과 phase3081개,
skip/xfail 없음, JUnit suite613.169s다. 모든8415개 parameter mutation과1501개 metadata/
family 누락을 거부했다. 별도 strict CLI는 새 원본
report/XML을 허용한다(exit0). Setup phase 또는 JUnit case를 누락한 사본은 각각
실패하며(exit1), 음성 대조로 보존한다. 원본 report는 손대지 않고 유지한다.
독립 API/Worker 프로덕션 Search E2E 다섯 개도 이 child에서 통과했다.
이전 actual JSON/JUnit으로 인수 조건을 충족하지 않았다.

이 nested 시간은 새 검증 관측이며 unit 전용 변경의 측정 효과가
아니다. 변경한 unit 파일은 nested 명령에 포함되지 않는다.
전체 기본 outer pytest와 MySQL 테스트1045개 전체의 단일 호출은
실행하지 않았다. 새 nested, 별도 parent, tail의 node 집합을 직접 비교하면
미실행 MySQL node14개가 있다. Durable facts6, Case composition4, Case execution-
read/result-reflection4다. 이 검증 범위 공개는 합산 전체 suite
PASS가 아니다. 영향받은 전체 unit/helper, 필수 실제 inventory/mutation,
요청한 전체 tail을 실행했다. 추가 전체 outer 제품 회귀는
변경 없는 제품 코드를 중복 검증하며, 어차피 새 원격 budget 검사가 필요하다.

소유한 MySQL8.4.7 감사는 시스템 스키마/계정과 ci_tail_test만,
auditor/system scheduler만, transaction0, lock0을 보였다. 소유 process 종료,
정확한 UUID datadir 제거, Linux connect_ex111은 확인했다. Windows는 처음
connect_ex0, 이후 시간 제한 probe10035를 반환했다. 즉각적인 Windows 거부나
protocol 결과는 확인하지 못했다. Listener 조회는 listener
행 없음과 exit1을 반환했으며 확정적인 port 종료 증거는 아니다. 공유 WSL/forwarder/service는
바꾸지 않았고 살아 있는 소유 MySQL process는 관측하지 못했다. 이 Windows
정리 관측 가능성의 한계는 명시한다. Native tail/profile/pair 디렉터리는
범위를 정한 TemporaryDirectory 할당으로 종료 시 제거됐다. 작업 RAW, JSON/
JUnit, XML, 진단, profile, runner는 ignored 및 PR 제외 상태로 남긴다.

변경 source 전체의 경계/Contract/diff 검사와 새 독립 읽기
전용 검토의 세 파일 delta 확인은 아래에 이어진다. 현재 상태는 계속
**IN_PROGRESS · Refs #297 (RT-10(b))**다. Merge 준비 전에 기존30분/900s 제한 안에서
새 원격 전체 pytest와 후속 strict gate가 **모두** 성공해야 한다.
계속 취소되더라도 이 성능 관측이 timeout/job/inventory/required-check/artifact-policy
변경을 승인하지는 않는다.


<a id="fresh-review-p3-and-retention-compatibility-follow-up--2026-10-27"></a>

### 새 검토 P3와 retention 호환성 후속 기록 — 2026-10-27

독립 `fork_turns=none` 검토자는 새 세 파일 delta와
보존 증거만 읽고 P1/P2 없음, P3 한 건을 발견했다. 최초 manifest
hash 세 개와 빈 index를 모두 확인했다. P3는
앞선 이름 변경만의 설명에서 빠진 조건부 동작 차이다. `tmp_path_retention_policy=failed`에서
표준 tmp_path는 각 통과 사례 디렉터리를 제거하지만 일반 mktemp
fixture는 그러지 않는다. 현재 CI의 기본 `all`과 외부 report 전달에는
영향이 없었다. 최초 후보/검토 snapshot과 finding은 보존한다.

작성자는 설치된 pytest 구현을 확인하고, 통과 parameter 사례 하나와 의도적으로 통제한 실패 하나를
가진 실제 subprocess 회귀를 추가했다
(session 성공이 사례별 cleanup을 숨기지 못하도록 함). 그 결과 통과한 XML이 남는
RED를 관측했다.2.55s에1건 실패였다. 이제 fixture는
`all`이 아닌 정책에서는 표준 tmp_path에 위임하며 기본 all 빠른 할당기는 그대로다. 집중 검사는
기존 XML-call guard를 포함해2.43s에4건 통과했다. 의도적으로 실패하는
child는 예상한 음성 대조이며 제품/outer-suite 실패가 아니고
PASS로 다시 표시하지 않는다.

최종 비프로파일링 Linux unit/helper 실행은 테스트8415개를113.68s에 통과했다.
원래8412개 사례와 guard 세 개가 모두 남고, skipped/failed/error JUnit case는 없다.
이는167.78/160.73s와 계측이 다른 새 실행이며 비교 가능한
전체 suite 속도 향상 주장이 아니다. 앞서 측정한 기본 all 핵심
함수는 호환성 후속 수정 뒤에도 AST가 동일하다.53.123/33.879s
비교는 계속 앞선 source snapshot에 연결된다. 새 retention guard 자체는
이 로컬 최종 실행에서8.24s가 걸렸으며 추론한 원격 비용이 아니다.

위의 새 actual nested/mutation 실행은 이 unit fixture
호환성 후속 수정 전에 수행했다. 선택 코드, validator, harness, actual
mutation helper, nested 명령은 바뀌지 않았으며 unit 파일도 선택되지 않는다.
그 결과를 새 실행으로 다시 표시하지 않는다. 격리된 unit 전용 분기 때문에
추가697s actual 반복은 필요하지 않았다. 전체 outer/현재 원격 CI는
계속 미실행이며 merge 차단 요인이다. 최종 세 파일 delta와
결과만 담은 문서의 후속 읽기 전용 검토는 아래에 이어진다.


<a id="final-independent-review-and-uncommitted-handoff--2026-10-27"></a>

### 최종 독립 검토와 미커밋 인계 — 2026-10-27

원래 `fork_turns=none`으로 시작한 같은 독립 검토자는
retention 후속 수정/최종 세 파일 delta와 보존 기록만 읽었다.
원래 P3 해결을 확인하고 이 범위에서 **새 P1/P2/P3 없음**으로 판단했다.
Non-all 정책 위임은 표준 사례별 정리를 보존하며, 기본 all
할당기/report 전달과 원래8412개 사례를 모두 유지한다. RED/GREEN child XML
(통과 parameter 하나/의도적 probe 실패 하나, error/skip 없음), 최종8415개 JUnit case,
actual-child selection을 독립적으로 비교했다.
Test/DB/원격 CI 실행이나 file/ref/index 변경은 하지 않았다. 최초/최종
review manifest hash, branch/HEAD, 빈 index를 보존했다. 작성자는
이 결과와 log만 추가하기 전에 최종 hash 세 개를 모두 재확인했다.

이는 전체 PR/RT-10 승인이나 원격 timeout 해결 증거가 아니다.
최신 원격 상태는 계속 CANCELLED이고 후속 strict는 SKIPPED다. 기존30분/900s 제한 안에서
새 전체 pytest 최종 summary와 후속 strict 성공이
여전히 필요하다. #405 미결, 전체 outer/현재 원격 검증과 미실행 MySQL node14개는
계속 공개한다. Source는 bc459255에서 미커밋/unstaged 상태이며,
commit/push/PR/CI 작업은 수행하지 않았다. 상태는 계속
**IN_PROGRESS · Refs #297 (RT-10(b))**다.
