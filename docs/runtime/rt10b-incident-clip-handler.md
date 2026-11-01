<a id="rt-10b-incident_clip_build--implementation-notes"></a>

# RT-10(b) INCIDENT_CLIP_BUILD — 구현 기록

**IN_PROGRESS · Refs #297 (RT-10(b))** · 2026-10-28.

<a id="result-and-scope"></a>

## 결과와 범위

프로덕션 Worker registry는 Case가 발급한 `INCIDENT_CLIP_BUILD`를
`RecordingService.build_incident_clip()`으로 실행할 수 있다. Fine, clip, 각 readout은
별도 실행으로 유지한다. 성공한 clip T2는 기존
Case 반영과 enqueue를 사용해 동일한 불변 `incident_clip_ref`로 `PLATE_READ`와
`OVERLAY_TIME_READ`를 발급한다. 이 핸들러들, export 핸들러 두 개, Case/Web
상태 표시는 이 변경 밖이다. 완전한 RT-10 또는
ReportPackage 인수가 아니다.

시작 gate에서 origin/develop을 fetch하고 브랜치
`codex/rt10b-incident-clip-handler`, HEAD와 origin/develop이 모두
`6764c8f7f6dc5ef284db3c9bff3d4d19e02bfe73`임과 깨끗한 working tree, 빈 index를 확인했다.
기존 checkout을 사용했다. 새 worktree, staging, commit, push 또는 PR
작업은 이 작업에 포함되지 않는다.

<a id="sot-and-input-bindings"></a>

## SoT와 입력 바인딩

- [Case 결정](../modules/case/decisions/incident-clip-observation-input.md)은
  추가만 허용되는 observation 입력에 candidate, generation, span, Fine job을 고정한다.
- [Runtime 명세](runtime-tech-spec.md)는 checkpoint, T1/T2, retry,
  registry 의미론을 소유한다. [앞선 구성 체크포인트](rt10b-production-composition.md)는
  과거 증거로 유지하며, 이 변경의 테스트 실행이 아니다.
- [Owner terminal 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6464169000)은
  앞선 매핑 차단 요인을 해소한다. 정확한 literal 매핑은
  [Recording taxonomy](../modules/recording/decisions/failure-taxonomy.md)에 등록돼 있다.

`IncidentClipInputs`는 구성 측이 소유하는 트랜잭션 안에서만 실행한다. 공개
`CaseStore.get_case`, clip과 Fine job의 `observation_input`,
`read_executions`를 호출한다. 성공한 의존 payload는 `ProducedReader`로 읽는다.
clip/Fine/Coarse JobRecord의 kind, case, scope, scope 본문,
clip 입력에 대한 Fine의 candidate/generation/span, 최신 의존 attempt의
SUCCEEDED 상태, Coarse candidate/run/scope/span과 Fine run/evidence 연결을 확인한다.
상대 scope는 동일 timeline/revision에 묶여야 한다. 원래 요청한
범위를 candidate에 다시 적용하지 않는다. Recording의 실제 frame coverage는
scope 끝을 넘어갈 수 있으며 Search/Fine은 그 실제 source를 사용한다.
예전의 성공한 Fine이 더 최근의 실패한 attempt를 덮어쓸 수 없다.

현재 선택한 candidate에서는 입력을 가져오지 않는다. Case 입력에 stream ref를
추가하지 않는다. Fine의 공개 `analysis_run.input_ref`가 AnalysisSource를 식별하며,
공개 Recording 메타데이터가 timeline/range와 stream 사실을 제공한다. VIDEO
stream이 정확히 하나여야 하며, Case에 대해 공개 `owns_asset` 검증을 수행한다.
모호한 경우 first/default/front/rear stream을 선택하지 않고 거부한다.

Search는 `round(seconds * 1000)`으로 CandidateSpan을 만든다. 따라서 source 포함 관계도
동일한 ms 좌표계에서 비교하며, source 끝점은
Search와 똑같이 `timeline_range.start_sec + duration_sec`로 계산한다.
Recording은 MP4 길이와 실제 frame coverage를 독립적으로 probe한다.
Search의 duration 좌표를 실제 range 끝으로 대체하지 않는다. 고정된 Case 요청을
Recording `resolve_span`에 그대로 전달하며, clamp, 새 허용오차 정책,
provenance 재작성은 없다. PARTIAL과 사용 가능한 span, 실제 media/frame coverage의
권위 있는 기준은 계속 Recording이다.

<a id="transaction-connection-lifecycle-and-terminal-boundaries"></a>

## 트랜잭션, connection, 수명주기 및 terminal 경계

1. Checkpoint 후 호출자의 짧은 트랜잭션에서 영속 입력을 조회한다.
2. 해당 connection을 반환한 뒤 실행별 Recording context를 연다.
   Recording 저장소 작업은 `TransactionalRecordingRepository`를 통해
   각자의 짧은 caller 트랜잭션을 사용한다. Connection이나 stream은 입력 로드를 벗어나지 않는다.
3. 공개 metadata/ownership/resolve/build 기능 사이에 checkpoint를 둔다.
   핸들러 내부 재시도 없이 `build_incident_clip(resolution)`을 한 번 호출한다.
4. 성공/오류/취소 시 context를 닫는다. 알려진 기능 실패 경로를 포함해
   닫은 뒤 terminal 사실을 반환하기 전에 다시 checkpoint를 둔다.
5. 성공은 정확히 `{"incident_clip_ref": "<Recording ref>"}`인
   단일 `ProducedObject` payload를 반환한다. `incident_clip_result` receipt는
   기존 실행별 ref 할당을 사용하며 불변
   Recording clip ref와 구별된다. 따라서 후속 clip job이 같은 clip을 재사용해도
   object-store 고유성 충돌이 없다.
6. 기존 Worker T1은 terminal, produced ref, payload를 원자적으로 저장한다.
   rollback/COMMIT 결과 불명 복구는 핸들러를 호출하지 않고 이 사실들을 재사용한다.
   기존 T2는 Case 반영, 후속 job/enqueue, receipt를 함께 영속화한다.
   재전달은 media를 호출하지 않는다. T1/T2 구현은 변경하지 않았다.

build 호출에서 발생한, code가 `INCIDENT_CLIP_BUILD_FAILED`인
`RecordingCapabilityError`만 `FAILED`,
`failure_kind=RECORDING_INCIDENT_CLIP_BUILD_FAILED`, 빈 produced/objects로 매핑한다. 알 수 없는
code는 기존 registry 예외 경계로 전파한다. 문자열로 생성한
Recording failure는 도입하지 않는다. Input/metadata/context/checkpoint/ValueError/DB/
transaction/persistence 오류는 이 매핑 밖이다. 취소는
기존 제어 흐름을 유지한다. 이 핸들러는 원시 오류 텍스트나 path/locator를
로그에 남기지 않는다. clip 실패 뒤에도 Fine 성공과 그 produced는 그대로이며,
Case는 새 clip job을 발급할 수 있다. 일반 FAILED 자동 재시도는 추가하지 않는다.

<a id="explicit-production-configuration"></a>

## 명시적 프로덕션 설정

Recording은 AnalysisSource profile 설정과 독립적인 선택적 설정 키 세 개를
소유한다. `DAESINGO_RECORDING_INCIDENT_HEIGHT`,
`DAESINGO_RECORDING_INCIDENT_PRESET`, `DAESINGO_RECORDING_INCIDENT_CRF`다. 세 개를 모두
함께 제공하고 기존 encoder 검증을 통과해야 한다. 새로운
encoding 기본값은 없다. 새 clip 전용 factory는 `LocalIncidentMaterializer`와
영속 prepared 저장소를 제공한다. 기존 Analysis service factory는 그대로다.
Worker는 기존의 설정된 temp-root lease로 materializer를 감싼다.
명시적 encoding/context가 없으면 kind는 미등록 상태다. Registry 병합은
중복 kind를 거부하고 기존 Search 등록 규칙을 유지한다.

<a id="direct-execution-evidence-and-preserved-records"></a>

## 직접 실행 증거와 보존 기록

이 작업의 증거는 `.codex-scratch/rt10b-incident-20261028/` 아래에 제외돼 있다.
각 행은 별도 실행이며 합산 총계나
원격 CI의 대체물이 아니다. 앞선 RT-10 작업의 과거 증거는 여기서 세지 않는다.

| 검사 / 스냅샷 | 관측 결과 |
| --- | --- |
| 최초 handler/input RED | 36건 실패: 구현 모듈 없음 |
| Composition/config RED, 쓰기 가능한 temp root 수정 | 8건 실패, 7건 통과 |
| 불변 clip receipt 재사용 RED | 1건 실패: 두 실행이 같은 result-store ref를 재사용 |
| 최초 상대 scope 검증 RED | 3건 실패. 이후 검토에서 requested-range 포함 검사가 잘못 추가된 정책임을 발견하고 별도 긍정 회귀와 함께 제거 |
| 알려진 build 실패 뒤 close 중 취소 RED | 1건 실패 |
| 소수 source 경계 RED | ms 좌표 비교 전 1건 실패 |
| 새로운 검토의 scope-tail / duration-coordinate RED | 각 1건 실패, 이후 집중 테스트 72건이 2.09 s에 통과 |
| 정밀도 수정 후 집중 handler/input/composition/Recording config | 71건 통과, 1.79 s |
| 앞선 관련 오프라인 스냅샷 | 1614건 통과, 기존 opt-in skip 17건, 614건 선택 해제, 116.82 s |
| 최종 정밀도/close 후속 수정 전 실제 MySQL 부분집합 | 57건 통과, 193.60 s; MySQL 8.4.13 |
| 영속 clip 하나를 공유하는 독립 성공 실행 | 1건 통과, 8.21 s; 57개 테스트 수에 합산하지 않음 |
| 검토 전 최종 통과 스냅샷, 30fps 프로세스 E2E 포함 | 59건 통과, 268.49 s; 명시적 검토 후 검사만이 이를 대체하며, 최종 source 실행으로 다시 표시하지 않음 |
| 검토 전 오프라인 후속 실행 | 1633건 통과, 기존 opt-in skip 17건, 619건 선택 해제, 198.47 s |
| 경계 / Contract fixture | PASS; fixture 검사 구조 62 / JSON 26 / 의미 104 |

중간 import/fixture 오류는 별도 기록으로 유지한다. 잘못된 AnalysisRun
package import, 실제 202 대신 API 200을 기대한 오류, 의도적인 영속
cleanup-lock을 media 누수로 오인한 오류, 잘못된 `issue_same_input` 인자다.
수정한 MySQL 실행은 제품 정책을 바꾸지 않고 이 경로들을 검증했다.
Sandbox socket/temp 권한 실패와 Python 시작 메모리 오류 한 건은
환경 실패이며, 기능 RED나 PASS가 아니다. 이후 짧은 20-frame source E2E
probe는 Coarse provider 전에 중단됐다. 그 fixture는 clip 처리에 도달하지 않았다.
30fps clip 테스트는 일 초 source와 같은 소수 candidate
경계를 사용한다. source-tail 준비 한계를 여기서 수정했다고 주장하지 않는다.

최종 현재 source 회귀, MySQL, 검토, 리소스 정리 결과는
아래에 기록한다. 전체 pytest와 전체 필수 MySQL suite는
의도적으로 로컬에서 중복 실행하지 않는다. PR 원격 CI의 `regression` / `mysql` /
`test` job이 기존 workflow, inventory, timeout,
skip/xfail 정책으로 이를 검증해야 한다. 이 작업에서 원격 CI job을 시작하지 않았다.

<a id="test-boundaries-and-remaining-limitations"></a>

## 테스트 경계와 남은 한계

MySQL 테스트는 영속 Case/Fine 복원, connection 반환 후 실제 AVI-to-H.264 clip
생성, T1 rollback과 COMMIT ACK 유실, T2 rollback과
재전달, 실제 build 뒤 취소, Recording 오류와 DB 오류 구분, Fine/provider를
재실행하지 않는 새 Case clip job, 실행 간 불변 clip 재사용을
검증한다. Spy는 실제 build/encoder를 감싸며, 진입한 실행별로 정확히 한 번
호출됨과 느린 경계에서 main-pool checkout 없음을 assertion으로 확인한다.

API/Worker 인수는 서로 다른 spawned OS process와 단계별 새 Worker를
사용한다. API HTTP는 API child 내부의 ASGI TestClient를 통하며,
TCP API listener가 아니다. 실제 MySQL, ffmpeg, 공개 서비스, registry, T1/T2를 유지하고,
외부 Search provider HTTP만 MockTransport를 사용한다. Clip worker HTTP 호출은
없으며, build와 encode 호출은 각 한 번이다. Readout job이 같은 clip ref로 QUEUED임을
assertion으로 확인하며, readout 실행/package 준비 완료는 주장하지 않는다.

이 범위는 명시적 VIDEO stream 하나를 지원하며, 다중 video 선택은
정의하지 않는다. 더 강한 process-kill 복구/encode 비용 회피, orphan retention,
Case/Web 실패 표시, readout/export 실행, 실제 provider, 배포,
플랫폼 간 FFmpeg 인수는 이 검증 밖이다. 영속 Recording 게시 후
T1 전에 프로세스가 죽으면 prepared media가 남을 수 있으며,
기존 retention 정책과 STALE 처리는 그대로다. 새 실행은
다시 encode할 수 있다. exactly-once는 진입한 실행별 의미이며, 전역적인 crash-proof media
실행이 아니다.

<a id="final-verification-and-fresh-review"></a>

## 최종 검증과 새로운 검토

다음 실행은 검토 수정 후 최종 제품/테스트 스냅샷을
사용했다. 서로 중복되므로 상호 간 또는 앞선 행과 합산하지 않는다.

| 직접 검사 | 결과 |
| --- | --- |
| 집중 input/handler/composition/Recording config | 72건 통과, 2.09 s |
| Worker / Recording / Case / common jobs, `-m 'not mysql'` | 1634건 통과, 기존 opt-in skip 17건, 619건 선택 해제, 169.36 s |
| 아래에서 선택한 실제 MySQL 파일 | 59건 통과, 268.12 s; failure/error/skip/xfail 없음 |
| MySQL 보고서 / JUnit 교차 확인 | 고유 테스트 59개, setup/call/teardown phase 177개, selected/collected/JUnit 식별값 정확히 일치; MySQL 8.4.13 |
| 경계 / Contract fixture / diff 공백 | PASS; 정책과 Contract source 변경 없음 |

MySQL 선택: `tests/worker/test_incident_clip_mysql.py`,
`tests/e2e_runtime/test_production_search_process_mysql.py`,
`tests/worker/test_search_handlers_mysql.py`,
`tests/worker/test_case_composition_mysql.py`,
`tests/recording/test_durable_facts_mysql.py`,
`tests/case/test_result_reflection_mysql.py`,
`tests/worker/test_produced_store_mysql.py`. 프로세스 시나리오 일곱 개에는
기존 normal/PARTIAL/Coarse-failed/Fine-failed/HINT 사례와 실제
clip 경로 두 개(10fps, 30fps)가 포함된다. 각 clip 실행은 실제 build/encode를 감싸고
각 한 번 호출, Search HTTP 호출 없음, 느린 진입점의 main-pool checkout 없음을
관측했다. 실패/새 job probe는
독립 clip job 두 개에서 build 두 번을 관측했으며, persistence/T2 재실행은 build 호출을 추가하지 않았다.

오프라인 skip 식별값은 앞선 opt-in 사례 17개와 정확히 일치한다. Recording
외부 media 입력 열다섯 개와 Case 외부 동영상 두 개다. 새 skip이나
xfail은 도입하지 않았다. 관측된 경고는 기존 Starlette/httpx
TestClient 폐기 예정 경고다. Workflow, 필수 inventory, timeout, skip/xfail
정책은 수정하지 않았다. 전체 pytest, 모든 필수 MySQL, 원격 CI, 실제
provider, 배포는 위에서 명시한 범위대로 미실행 상태다.

새 검토자는 구현 이력 없이 시작해 전체
tracked/untracked 제품/테스트/문서 delta와 기존 transaction/Recording
계약을 살폈으며, 변경이나 test/DB 실행은 하지 않았다. P2 한 건을 발견했다. 유효하게
frame 정렬된 candidate를 원래 요청 scope로 잘못 제한한 문제다.
작성자는 이를 RED로 재현하고 scope/run/timeline/revision 바인딩은 유지한 채
추가된 range 정책만 제거했다. 검토자가 별도로 추론한 duration
좌표 위험도 RED로 재현하고 Search의 start+duration
좌표로 수정했다. 읽기 전용 후속 검토는 실제 수정 두 건, 긍정
회귀, 보존된 72개 GREEN text/XML을 확인했다. **남은 제품
P1/P2/P3 finding 없음**. 오래된 scope 설명에 대한 문서 수정도 반영했다.
앞선 검토자 시도는 사용량 한도로 끝났으며, 완료된
검토나 독립 실행 증거로 세지 않는다. 이는 merge 승인이 아니다.

재개 중 Docker가 멈췄다. daemon을 시작한 뒤 소유한 테스트 container만
재시작하고, 새 endpoint를 최종 검증에 사용했다. 정리 전
서버에는 시스템 스키마와 작업의 일회용 base만 있었다.
비감사 client, InnoDB transaction, data lock은 모두 없었다. 소유한
container와 확인한 익명 volume을 제거했다. 작업의 `*-temp` 디렉터리
21개(생성 AVI/MP4, 테스트 환경 파일 포함)는 경로 해석 결과가 작업 scratch root 아래이며
reparse point가 아님을 확인한 뒤 제거했다.
해당 디렉터리는 남아 있지 않다. 제거한 endpoint의 시간 제한 TCP probe는
Windows 10035(연결 없음)를 반환했다. 즉각적인 connection refusal은
주장하지 않는다. 공유 Docker/WSL process는 중지하지 않았다. Raw/JSON/JUnit 증거는
ignored 상태이며 PR 후보에서 제외한다. 임시 DB 데이터는 남기지 않았다.

<a id="changed-file-inventory"></a>

## 변경 파일 목록

- `docs/modules/recording/decisions/README.md`
- `docs/modules/recording/decisions/failure-taxonomy.md`
- `docs/runtime/rt10b-incident-clip-handler.md`
- `docs/runtime/rt10b-production-composition.md`
- `docs/runtime/runtime-implementation-log.md` (추가만 허용)
- `docs/superpowers/plans/2026-10-28-incident-clip-handler.md`
- `src/daesingo/recording/factory.py`
- `src/daesingo/worker/__main__.py`
- `src/daesingo/worker/registry.py`
- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/incident_clip_composition.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/recording/test_factory_config.py`
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_clip_mysql.py`

RAW, JSON/JUnit, 생성 media, 임시 DB, 환경 파일, runner는
제외된 scratch 증거로 유지하며 PR 후보가 아니다. 사용자 원본 media는 사용하지 않았다.

<a id="2026-10-31-follow-up--486-8"></a>

## 2026-10-31 후속 기록 — #486 §8

위의 단일 VIDEO 제한은 과거 RT-10(b) 기준선이다.
현재 unstaged 순차 source 어댑터와 검증은
[다중 source IncidentClip 구현 기록](multisource-incident-clip.md)에 기록돼 있다.
앞선 실행 증거와 원래 구현 이력은 보존한다.
