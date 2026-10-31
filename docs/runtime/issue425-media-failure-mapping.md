<a id="425-analysis-input-failure-mapping--implementation-notes"></a>

# #425 분석 입력 실패 매핑 — 구현 기록

상태: IN_PROGRESS · Refs #425 · Related #297. 이번 요청의 구현 사양, 2026-10-31 KST.

<a id="plan-and-constraints"></a>

## 계획과 제약

현재 대화에서 체계적 원인 조사와 TDD로 구현한 뒤, fresh 읽기 전용 GPT-6.1
Sol / High 리뷰를 받는다. 이번 요청에서 구현·실행 범위를 제공했으므로 추가 계획 승인,
worktree, 브랜치 전환, 커밋 또는 외부 쓰기는 수행하지 않는다.

- [x] 준비 단계의 UNSUPPORTED_MEDIA가 RUNTIME_HANDLER_ERROR가 되는 기존 동작 재현(RED).
- [x] taxonomy에 정확한 값을 등재하고 단일 준비 호출을 분리한 뒤,
  FAILED / RECORDING_UNSUPPORTED_MEDIA / produced=[] 검증(GREEN).
- [x] 합성 입력·provider 대역으로 production registry 조립, 제외 경계, 크기 한도,
  성공, 취소 및 정리 검증.
- [x] 전용 MySQL 부분집합으로 T1/T2, replay, receipt 및 Case projection 검증.
- [x] Runtime quality, boundary, Contract fixture 및 diff 검사.
- [x] 리뷰·증거 문서화·Runtime Log append와 소유 자원 정리.

시작 브랜치: `codex/issue425-media-failure-mapping`; HEAD:
`d1f57b343c509ef2d5ea42aa119487d79c9adc43`. 작업 트리와 index는 깨끗했다.

<a id="source-decisions-and-scope"></a>

## 근거 결정과 범위

[#425](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425)와
[Recording Owner 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627)을 읽었다.
해당 결정은 서로 다른 time base를 지원하고 정확히 표현할 수 없는 입력은 typed 오류로
거부한다는 의미다. 새 terminal 값까지 승인한 결정은 **아니다**.
`RECORDING_UNSUPPORTED_MEDIA`는 이번 구현 요청에서 지정한 값이다.
[PR #499](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/499)의 병합을 확인했고,
병합 커밋은 시작 HEAD와 같았다. 공통 시간축 구현과 strict 검증은 변경하지 않았다.

리뷰 중점은 실제 준비 오류만 변환하는 것이다. context 수명·transaction 오류는
Runtime 소유 경계를 유지하고, 취소·UsageError는 전파하며, terminal에 예외 상세를 넣지 않는다.
Case 실패를 성공이나 결과 없음으로 취급하지 않는다.

<a id="before-and-after-exact-boundary"></a>

## 변경 전후와 정확한 적용 경계

기존 `search_handlers`는 service factory 진입 시 크기 한도 code만 처리했다.
준비 단계의 `UNSUPPORTED_MEDIA`는 `KindRegistry.dispatch`까지 전파돼
`FAILED / RUNTIME_HANDLER_ERROR`가 됐다. 해당 execution의 produced receipt는 없었다.

변경 후 `ProductionMediaFactory`는 **오직**
`recording.prepare_analysis_source_from_resolution(resolution, profile_ref)` 호출을 감싼
범위에서 `RecordingCapabilityError`를 처리한다. 정확한 code가 `UNSUPPORTED_MEDIA`인
경우에만 내부 `_UnsupportedAnalysisInput` 신호를 만든다. 신호가 handler에 도달하기 전에
Recording context가 종료된다. 정리에 실패하면 그 오류가 신호를 대체하며 Runtime 오류로
남는다. handler는 진입 시점에만 신호를 처리하고 취소 checkpoint를 확인한 뒤,
`FAILED / RECORDING_UNSUPPORTED_MEDIA`, `objects=()`, `produced=()`를 반환한다
(저장 형태는 `[]`). 거부된 execution은 Search AnalysisRun이나 produced receipt를 만들지 않는다.

| 경계 | 동작 |
| --- | --- |
| COARSE_SEARCH / FINE_VERIFY의 production 준비 | 같은 factory와 Recording 공개 준비 호출을 사용하므로 새 mapping 적용 |
| HINT_EXTRACT | 별도 텍스트 추출기 사용. 변경 없고 media factory에 진입하지 않음 |
| 입력 조회 / factory 구성 / Recording context 진입 / metadata 소유권 / resolve_span / observe_time_sources / Search 설정 | 새 catch 범위 밖. 같은 원래 UNSUPPORTED_MEDIA라도 Runtime 소유 경계 유지 |
| prepare 내부 DB 조회 / publish / transaction / commit | repository는 media capability 오류가 아닌 SQLAlchemy·transaction 예외를 전파하므로 새 catch에 해당하지 않음 |
| 알 수 없는 Recording code | 기존 Runtime 경계로 재전파 |
| checkpoint / 취소 / UsageError | 새 변환 없음. 정리 후 취소 checkpoint가 대기 중인 준비 실패보다 우선 |
| Search/provider, resolver, 본문, context 종료/정리 | 새 변환 없음. 기존 Search 공개 helper 또는 Runtime 경계 유지 |
| 크기 한도 mapping | 원래 적용 범위를 포함해 기존의 정확한 진입 mapping 유지. 일반화하지 않음 |
| IncidentClip / export | 기존 공개 wrapper와 확정 mapping 유지 |

prepare 메서드는 repository 조회와 영속 publish도 수행한다. `get_timeline`, 로컬 원본/index
조회, `_publish_prepared` → `add_prepared_media`를 검토했으며, 해당 MySQL 연산은
DB/transaction 오류를 발생시킨다. 테스트는 **실제 prepare 호출 내부에서** 조회·미디어 생성·
publish 각각에 독립적으로 fault를 주입하고, 주입 지점에 도달했는지도 검증한다.
새 전역 변환기, Recording 공개 API, schema, migration, receipt, retry, 시간축 연산 또는
strict 검증은 추가하지 않았다.

<a id="direct-author-verification"></a>

## 작성자의 직접 검증

Python은 `.venv/Scripts/python.exe`, offline Windows FFmpeg/ffprobe는 PATH의
`ffmpeg-9.0.1-essentials_build`를 사용했다. 생성한 한 초 영상과 합성 Search 결과/오류만
사용했다. 전용 로컬 MySQL 8.4 컨테이너는 tmpfs·무작위 localhost 포트·작업 전용 무작위
credential을 사용했다. harness는 테스트별 schema를 생성·삭제했으며 공유 DB는 사용하지 않았다.

RED 이후 모든 명령은 `-o cache_dir=.codex-scratch/issue425-mapping/cache`와
해당 ignored 디렉터리 아래 작업 전용 `--basetemp`를 사용했다.
원본 로그와 MySQL 보고서는 ignored scratch에만 보관했다.

| 검사 / 명령 범위 | 관측 결과 |
| --- | --- |
| RED: 제품 변경 전 `pytest tests/worker/test_unsupported_media_mapping.py -q` | 2 failed. COARSE·FINE 모두 기대값은 `RECORDING_UNSUPPORTED_MEDIA`, 실제값은 `RUNTIME_HANDLER_ERROR`. 기존 cache 권한 경고 두 건 |
| 최초 GREEN + 기존 크기 한도 mapping 테스트 | 9 passed |
| 주입 지점 도달 assertion 보강 전 새 경계 matrix 단독 실행 | 48 passed. 최종 보강·서식 정리 후 반복: 48 passed / 30.58 s |
| 아래 focused 회귀 명령. prepare 내부 read/publish assertion 보강 포함 | 176 passed, skip 없음, 109.15 s |
| `DAESINGO_REQUIRE_MYSQL=1`·`--mysql-report`를 적용한 전용 `pytest tests/worker/test_unsupported_media_mysql.py -q` | 12 passed, skip/xfail 없음, 30.96 s. fixture alias/서식 정리 후: 12 passed / 44.19 s. 보고서: MySQL 8.4.13, selected/passed 12개, collection 오류 없음 |
| `python scripts/check_runtime_quality.py` | Ruff PASS; mypy linux·win32 각각 87파일 PASS |
| `python scripts/check_boundaries.py` | UTF-8 출력으로 PASS. 최초 CP949 콘솔 인코딩 오류 후 `PYTHONIOENCODING=utf-8`로 재실행 |
| `python scripts/check_contract_fixtures.py` | 구조 62 / JSON 26 / 의미 검사 104건 PASS |
| 새 테스트 두 파일 Ruff 검사 | fixture alias·서식 정리 후 PASS |
| `git diff --check` | 작성자 검증 시 PASS |

focused 회귀 명령(전체 pytest 아님):

```text
python -m pytest tests/worker/test_unsupported_media_mapping.py
  tests/worker/test_analysis_source_limit_mapping.py
  tests/worker/test_search_handlers.py tests/worker/test_search_failure_boundary.py
  tests/worker/test_production_media.py tests/worker/test_export_handlers.py
  tests/recording/test_mixed_timebase.py -q
```

새 matrix는 정확한 terminal, 거부 후 Search 생성/capability 미호출, 준비 밖의 같은 원래
code의 실패, unknown code, SQLAlchemy, BeforeCommitFailure, CommitOutcomeUnknown,
TransactionBoundaryError, TransactionRetryExhausted(결과 확인/미확인),
UsagePersistenceError, CancellationRequested와 거부·정리 중 취소 요청을 검증한다.
기존 성공·Search/provider·크기 한도 사례도 GREEN이다. mixed time base 테스트는 #499 코드를
수정하지 않고 IncidentClip wrapper와 정리도 검사한다. 최초 fixture는 잘못된 repository
클래스를 patch했으므로 이를 고치고 prepare 내부 주입 도달 assertion을 보강했다.

MySQL 12개 사례는 COARSE/FINE × 정상, T1 rollback, T1 COMMIT 응답 유실,
T2 rollback, T2 COMMIT 응답 유실, T1→T2 전달 공백이다. 자동 `ProductionMediaFactory`를
사용하는 실제 `compose_search_registry`, `SearchInputs`, Recording/MySQL repository,
MediaRoot, Worker terminal 영속화와 `StoredCaseReflector`를 사용한다.
Fine 선행 Coarse는 합성 Search 후보로 성공한다. 준비 실패 시 media는 정확히 한 번 호출되고
후속 Search capability는 호출되지 않는다. T1/T2 transaction replay, redelivery와 idle Worker
재시작은 media/provider 호출을 추가하지 않는다. 영속 status/kind/빈 produced, produced object
없음, 처리된 execution, replay 후 receipt 불변, 중복 job 없음, RUNNING job 없음,
pool checkout 없음, Recording temp 잔여 없음도 확인한다. 이 fixture는 HINT job을 발주하지
않으므로 영상 Search 미호출을 이전 텍스트/HINT provider 호출과 혼동하지 않는다.

<a id="case-consumption-and-unposted-owner-proposal"></a>

## Case 소비와 미게시 Owner 제안

`ExecutionOutcome.failure_kind`는 문자열을 받고 `CaseReflector`는 새 값을 그대로 전달한다.
COARSE의 FAILED 분기는 produced payload를 읽지 않고 실패를 기록한다.
FINE의 FAILED 분기는 observation을 정산하며 성공 Fine/clip 경로를 따르지 않는다.
T2·receipt·redelivery 코드는 변경하지 않았다.

| 저장된 CaseView로 확인한 기존 projection | 남은 정책 |
| --- | --- |
| COARSE: stage SEARCHING, `coarse_search=FAILED`, running job·만들어 낸 후보·결과 없음 성공 없음 | 일반 `search.candidate_search_failed` notice와 `RETRY_SEARCH` 유지 |
| FINE: 선택 후보 유지, observation outcome FAILED, downstream job·running job 없음 | 일반 blocking `search.visual_verify_failed`, actions=[] 유지. 기존 Case view는 시작하지 않은 downstream 단계를 생략하며 별도 Fine 실패 progress 행은 제공하지 않음 |

Fine projection assertion은 기존 DONE 단계 세 개(file_intake/coarse_search/candidate_review)에
맞췄으며 **새 progress schema를 만든 것이 아니다**. 실패는 기존 blocking notice로 노출하고
NOT_OBSERVED나 성공 evidence로 취급하지 않는다. 새 Case/Web 코드·문구·action·retry 정책은 없다.

**Case Owner에게 전달할 댓글 초안 — 미게시:**

> Refs #425 / Related #297. Runtime은 Coarse·Fine의 Recording 분석 입력 거부를
> FAILED / RECORDING_UNSUPPORTED_MEDIA / produced=[]로 구분합니다. 예외 원문·파일명·경로·
> locator·영상 내용은 포함하지 않으며 기존 T2/receipt 의미를 유지합니다. 현재 Coarse는 일반
> 후보 탐색 실패와 RETRY_SEARCH를, Fine은 notice action 없는 일반 blocking 영상 검증 실패를
> 표시합니다. 새 kind의 안전한 전용 notice와 실제 가능한 출구를 결정해 주세요.
> 검토용 제안 문구: “이 영상은 현재 분석용으로 준비할 수 없습니다. 다른 입력으로 다시 시도해 주세요.”
> 이는 원본 손상이나 mixed time base의 영구 미지원을 뜻하지 않습니다. 같은 입력 재시도는
> 결정적인 거부를 반복할 수 있으므로, 이 kind에서는 재시도를 유일한 복구 경로로 제시하지 않고
> 일시적 Search 실패의 retry 정책은 유지하는 방향을 제안합니다. 기존 입력 교체·재등록·
> 입력 단계 복귀 중 실제 제공 가능한 흐름과 이미 생성된 후보/결과의 보존 여부를 확인해 주세요.
> 교체에 새 Case나 별도 command가 필요하면 UI action을 추가하기 전에 동작을 명시적으로
> 결정해야 합니다. Fine은 선택 후보를 보존하고 Case/Web이 합의한 입력/후보 출구를 제공하는
> 방향이며, 여기서 새 action enum은 제안하지 않습니다. 수락 기준은 FAILED 표시 유지,
> 무한 RUNNING·후보 없음 성공 방지, media 상세 원문 비노출, receipt replay의 execution 중복
> 방지, Coarse·Fine 거부 후 사용자 출구 검증입니다. 이는 검토용 정책 제안이며 승인 또는
> 구현된 notice/retry 변경이 아닙니다.

<a id="complete-change-file-inventory"></a>

## 전체 변경 파일 목록

| 파일 | 목적 |
| --- | --- |
| `src/daesingo/worker/production_media.py` | 공개 준비 호출의 미지원 오류만 분리해 내부 신호로 전달 |
| `src/daesingo/worker/search_handlers.py` | 내부 진입 신호를 지정 terminal로 변환 |
| `docs/modules/recording/decisions/failure-taxonomy.md` | 사용 전에 요청 권한·제외 경계와 함께 정확한 값 등재 |
| `tests/worker/test_unsupported_media_mapping.py` | RED/GREEN, production 연결과 제외 경계 matrix |
| `tests/worker/test_unsupported_media_mysql.py` | 실제 production 조립, terminal, T1/T2/replay/receipt, CaseView·자원 검사 |
| `docs/runtime/issue425-media-failure-mapping.md` | 이번 mapping의 계획·증거·범위·미게시 제안 |
| `docs/runtime/runtime-implementation-log.md` | 이전 이력을 보존하는 mapping 기록 append |

<a id="review-cleanup-and-unverified-scope"></a>

## 리뷰·정리·미검증 범위

구현 대화 이력을 상속하지 않은 fresh **GPT-6.1 Sol / High**가 후보 일곱 파일과 관련
Recording/repository/lifecycle, registry, terminal, Case projection·export 경계를 검토했다.
**수정할 지적이 없었으며 제품 보완이나 동일 reviewer의 재확인은 필요하지 않았다.**

| reviewer 검증 | 증거 범위 |
| --- | --- |
| 직접 실행: 새 mapping, 기존 크기 한도, Search 실패 경계 | 104 passed / 33.14 s; 직접 `git diff --check` PASS |
| 최초 직접 실행 | reviewer 상위 temp 디렉터리 부재로 fixture setup 오류 44건·60 passes. 상위 디렉터리 생성 후 재실행 성공. 제품 실패 아님 |
| reviewer 실행이 아닌 작성자 증거 검토 | RED, 176건 회귀, 최종 48건 matrix, MySQL 12/report, quality/boundary/fixture 로그·assertion |
| reviewer 미실행 | MySQL, 원래 Issue 영상, 전체 원격 CI |

reviewer는 source/docs/index/DB/container를 변경하거나 credential을 읽지 않았다.
직접 실행에는 별도의 ignored scratch 디렉터리만 사용했다.

전용 DB는 제거 전 harness schema 잔여가 없었으며, 소유 label을 확인한 뒤 작업 소유
container와 tmpfs를 제거했다. 공유 image/cache·이전 작업 scratch는 보존했다.
이번 작업의 pytest media/temp/cache, credential 파일, 임시 helper script를 제거했고,
작은 원본 증거 로그/보고서는 ignored `.codex-scratch/issue425-mapping/`에만 남겼다.
reviewer가 생성한 media/temp/cache도 리뷰 후 정리했다. 리뷰 결과는 위에 기록했다.
Runtime Log의 기존 HEAD 전체 byte prefix 보존을 확인했다.
최종 branch·HEAD는 시작값과 같고 후보 일곱 파일만 수정/untracked 상태다.
모두 unstaged이고 index는 비어 있으며 `git diff --check`는 PASS다.
원래 #425 AVI 아홉 파일·MP4 두 파일 재현 세트는 재검증하지 **않았다**.
실제 provider·사용자 원본·AWS·EC2·배포는 사용하지 않았다.
전체 로컬 pytest·mandatory MySQL·전체 mutation inventory·Docker OCR acceptance는
의도적으로 실행하지 않았다. 후속 push에서 전체 원격 CI gate를 충족해야 하며,
#499의 과거 CI는 이번 미커밋 diff를 검증하지 않는다.

이번 작업은 독립적인 Runtime/Recording mapping만 구현한다. #425는 IN_PROGRESS이며,
원래 세트 검증과 사용자 안내/출구 정책은 별도 미결이다. #425 완료나 사용자 안내 문제가
해소됐다고 주장하지 않는다.
