<a id="rt-10b-readout-handler-implementation-notes"></a>

# RT-10(b) Readout 핸들러 구현 기록

**IN_PROGRESS · Refs #297 (RT-10(b))**

기준: `debc783266d011ab46b102020c8d696a7dbd818e` (PR #440).
기존 `codex/rt10b-readout-handlers` checkout에서 작업한다. 새 브랜치,
worktree, staging, commit, push, PR 또는 Issue 변경은 이 작업에 포함되지 않는다.

<a id="authority-and-scope"></a>

## 권한과 범위

- [Readout 사용량 값](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469413593).
- [Runtime PARTIAL, 시간 및 begin 정책](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469456244).
- [Readout A 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469784532).
- [Runtime A 복구 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469908092).
- [PR #440 호출자가 발급하는 Run ID](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/440).
- 기존 Readout 공개 API/contracts/taxonomy, Case observation 입력/저장
  결정, Runtime UsageSink/ProducedObject/T1 계약이 계속 권위 있는 기준이다.

`PLATE_READ`와 `OVERLAY_TIME_READ`만 추가한다. Readout 알고리즘,
Case/Web 정책, export, 스키마, 마이그레이션, workflow, gate inventory는
그대로다. 테스트는 오프라인 OCR을 주입하며, 실제 OCR이나 Search HTTP를 사용하지 않는다.

<a id="input-invocation-and-resources"></a>

## 입력, 호출 및 리소스

`ReadoutInputs`는 호출자의 짧은 트랜잭션을 사용한다. Case의 공개
`get_case`, `observation_input(case_id, job_id)`, 실행 읽기 포트를 읽고,
`ProducedReader`로 불변 payload를 읽는다. 요청된
case/job/kind, 고정된 generation/scope/candidate, 그리고
동일 candidate/generation에서 성공하고 produced clip이 고정 ref와 일치하는 clip job을 검증한다.
대기 중인 job의 입력을 현재 선택값으로 대체하지 않는다.

반환되는 `ReadoutInput`에는 분리된 스칼라 사실이 들어간다. OCR context를 열기 전에
입력 트랜잭션과 connection은 이미 반환된 상태다.
`RecordingOcrFactory`는 Recording의 공개
`get_incident_clip`으로 clip 식별값/길이를 읽는다. `recording_ocr_factory`는 짧은 트랜잭션 저장소 콜백을 가진
실행별 RecordingService를 구성한다. Recording의
context는 성공, 기능 오류, usage 오류, 취소 시 모두 닫힌다.

핸들러는 입력 읽기 전후, context 진입 후,
usage begin 후, usage finish 후, 리소스 종료 후에 checkpoint를 둔다. OCR 뒤
취소를 확인하기 전에 반환된 Run observation을 `finish`에 전달한다.

호출마다 실행 식별값과 구별되는 새 `rr_` UUID를 발급한다.

```text
new rr_ ID
  -> UsageSink.begin(exact readout_run ref)
  -> matching public readout function once, with the same run_id
  -> UsageSink.finish(actual observations)
  -> ProducedObject preparation
  -> resource closure/checkpoint
  -> existing Worker T1 terminal + object transaction
  -> existing reconciliation
```

핸들러 재시도, T1 전 `finalize`, 예외 문자열 파싱,
Runtime 포트/스키마 확장은 없다. begin이 실패하면 OCR을 호출하지 않는다. Usage
복구, T1 receipt 재실행, T2 반영은 OCR을 호출하지 않는다. STALE의 새
attempt는 기존 재시도 정책에 따라 새 Run ID로 OCR을 호출할 수 있다.

<a id="outcome-and-usage-mapping"></a>

## 결과 및 사용량 매핑

| 공개 결과 | JobExecution | Usage observation |
| --- | --- | --- |
| `ReadoutRun.outcome=FAILED` | FAILED / `READOUT_INFRA`; Run 보존, result null | FAILED / `READOUT_INFRA` |
| `SUCCEEDED` 또는 `PARTIAL` | SUCCEEDED; 원래 Run 보존 | SUCCEEDED / null |
| Plate 판독 보류 / NEEDS_REVIEW | SUCCEEDED | SUCCEEDED / null |
| Overlay OK | SUCCEEDED | SUCCEEDED / null |
| Overlay NOT_APPLICABLE / `readout.overlay.not_present` | SUCCEEDED | SUCCEEDED / null |
| Overlay UNKNOWN / `readout.overlay.presence_undetermined` | SUCCEEDED | SUCCEEDED / null |
| Overlay UNKNOWN / `readout.overlay.ocr_failed` | SUCCEEDED | SUCCEEDED / null |

전체 `ReadoutRun.failure`는 code를 포함해 payload에 남는다. 유효하지 않은
입력의 `ValueError`와 input/DB/checkpoint/context/persistence 오류는
기존 Runtime 경계를 유지하며, `READOUT_INFRA`로 변환하지 않는다.
취소와 UsageError는 기존 Worker 수명주기로 전파된다.

Owner가 확인한 usage 필드는 `READOUT_PLATE` / `READOUT_OVERLAY_TIME`,
`ocr-local`, `{pricing_id: local-2026-09, unit: per_second}`,
`{amount: "0", currency: KRW}`, token usage null, incident clip 길이
(알 수 없으면 null)다. `occurred_at`은 계속 sink 시계이며, `latency_ms`는
Run started_at/ended_at에서 얻는다(ended_at을 알 수 없으면 null). Run usage_refs는
API가 반환하는 파생값으로 유지하며, ledger의 run_ref가 권위 있는 기준이다.

<a id="durable-objects-and-recovery"></a>

## 영속 객체와 복구

ProducedObject 하나에 `kind=readout_run`, 명시적 `ref=run.run_id`, 다음 payload가 들어간다.

- Plate: `{"readout_run": run.to_dict(), "plate_readout": result.to_dict() | null}`.
- Overlay: `{"readout_run": run.to_dict(), "overlay_time_readout": result.to_dict() | null}`.

이는 기존 ProducedReader / StoredObservationAdapter 형태다.
명시적인 Run ref 덕분에 현재 planned-run reconciliation이 영속 T1을 확인할 수 있다.
T1 전에 해당 produced Run이 없는 terminal 실행은
`RUN_NOT_PRODUCED`로 정리되며, 영속 usage observation은 남는다. T1 뒤에는
FAILED Run도 저장된 readout_run으로 정리된다. 유실된 COMMIT 확인 응답은
기존의 영속 receipt 검증으로 처리한다. Reconciliation은 기존
usage 식별값을 사용하며 두 번째 Final 행을 추가하지 않는다.

<a id="explicit-composition"></a>

## 명시적 구성

`compose_registry(..., readout_provider_factory=...)`는 두 Readout
핸들러를 기존 Search 및 clip 핸들러와 합친다. 기본값은 None이므로
설정하지 않은 프로덕션에서는 계속 미등록 상태다. fixture 기본값이나 새
환경 키가 OCR을 암묵적으로 활성화하지 않는다.

명시적으로 설정한 로컬 Paddle 배포에서는
`recording_ocr_factory(transaction=..., storage_root=...,
ocr_factory=lambda recording: PaddleOcrProvider(RecordingFrameSource(recording)))`
로 factory를 만들고 registry에 전달한다. 이 의존성을 조립하는 애플리케이션이
Readout 소유 의존성과 모델 설정을 설치하고 읽어야 한다. 모델
다운로드, Linux/프로덕션 하드웨어 지연시간, 실제 Paddle 실행은
이 변경의 오프라인 테스트로 검증하지 않았다.

<a id="verification-ledger"></a>

## 검증 기록

직접 증거는 PR에서 제외된 로컬 `.codex-scratch/rt10b-readout/`에 있다.
내부 `plan.md`, RAW 콘솔 출력, JSON/JUnit 보고서, 생성된
동영상/환경 파일과 일회용 DB 자료는 전달할 소스 파일이 아니다.

| 증거 | 결과 |
| --- | --- |
| 핸들러 최초 RED | 25건 실패: 핸들러 모듈 없음 |
| 핸들러 GREEN | 25건 통과 |
| 입력/구성 RED | 28건 실패 / 기존 기본 등록 1건 통과 |
| 결합 집중 검사 + 기존 clip 구성 GREEN | 57건 통과 |
| 재개 집중 검사, clip 구성 중복 제외 | 54건 통과 |
| 실제 MySQL 새 핸들러 receipt/복구 | 18건 통과, 31.31 s |
| 기존 실제 MySQL reconciliation | 30건 통과, 60.20 s |
| 경계 | 위반 0건 |
| Contract fixture | 구조 62 / JSON 26 / 의미 104, 모두 통과 |

첫 핸들러 테스트에는 잘못된 테스트 데이터가 있었다(contract의 `OK` 대신 `KNOWN`,
낮은 신뢰도의 판독 보류 대신 빈 OCR, 읽을 수 없는 sample 대신 sample 없음).
공개 계약에 맞게 수정했으며, 제품 수정은 아니다.
첫 MySQL 실행은 이미 STALE인 행을 테스트가 재시도하려 해서 16건 통과,
2건 실패했다. 실제 lease 만료/sweep을 사용해 18건 통과 실행을 얻었다.
초기 프로세스 probe에서 잘못된 어댑터 접근 메서드와 이후 peer
timeout이 드러났다. 어느 것도 통과한 E2E로 세지 않는다. 최초 경계 검사 호출은
cp949에서 Unicode dash를 출력할 때만 실패했으며, UTF-8 호출은 통과했다.

<a id="resume-verification-2026-10-29-kst"></a>

### 재개 검증 (2026-10-29 KST)

| 이 checkout에서의 직접 실행 | 결과 |
| --- | --- |
| DB/checkpoint/object 오류와 재선택/새 generation 입력 보존을 포함한 핸들러/입력/구성 집중 검사 | 69건 통과, 2.33 s |
| 관련 Worker/Readout/Case/Recording/Search/jobs/usage 비 MySQL 선택 | 2254건 통과 / 48건 실패 / 기존 skip 21건 / 831건 선택 해제, 231.81 s |
| 실패한 48건만, sandbox 제약 밖의 쓰기 가능한 작업 TEMP/TMP 사용 | 48건 통과, 57.83 s |
| 관련 실제 MySQL Search/clip/usage/produced/Case 부분집합 | 49건 통과, 123.37 s, 147개 phase |
| 별도 API/Worker 전체 체인 Readout 프로세스 E2E, 6개 모드 | 6건 통과, 248.37 s, 18개 phase |
| 기존 별도 프로세스 normal/hint/fractional-clip helper 회귀 | 3건 통과, 56.88 s, 9개 phase |

두 회귀 실행은 선택된 테스트를 미해결 실패 없이 검증한다.
단일 GREEN 전체 suite 실행은 아니다. 기존 skip에는 없는
`typer`, 비공개 실제 동영상 opt-in, 누락된 실제 동영상 파일이 포함된다. 기존
경고는 FastAPI/Starlette TestClient 폐기 예정 경고와 malformed-usage
Pydantic serializer probe다. 이를 억제하거나 변경하지 않았다.

위의 핸들러 MySQL 18건 / 기존 reconciliation 30건 실행은 이 작업에서
앞서 직접 수행했으며 사용량 한도 중단을 거쳐 보존했다.
그 실행 뒤 제품 코드는 바뀌지 않았다. 최종 집중 검사,
49건 MySQL, 6건 프로세스 실행은 재개 후 수행했으며, 어느 것도
원격 전체 회귀를 대체하지 않는다. MySQL 보고서에는 서버 `8.4.13`이 명시돼 있다.
한정 검증은 기존 validator로 수집/선택된 모든 node, 모든 setup/call/teardown
phase, phase 중복 없음, failed/skipped/xfail phase 없음, JUnit 식별값을
확인한다. 필수 전체 inventory gate를 호출하거나 완화하지 않는다.

E2E timeout의 원인은 Plate가 먼저 claim된다는 테스트 가정이었다.
두 job의 enqueue 타임스탬프는 같으며, Runtime의 실제 순서는
available_at/execution_id다. 이제 테스트는 그 순서를 따르며 실제 Case 쓰기 뒤
Readout T2 트랜잭션 **두 개 모두** 의도적으로 롤백한다. 두
provider 프로세스가 종료된 상태에서 재전달은 저장된 결과를 적용하며,
새 usage나 OCR 없이 반복된다. 여섯 status 모두 일치하는 공개 호출 수
1, 서로 다른 Run ID, 동일한 영속 clip, fake provider 내부에서 checkout된 main-engine connection
없음, connection 반환, 복원된 adapter observation,
남은 child process 없음을 포함한다. overlay 알림 세 개는 구별된 채 유지된다.
통과시키기 위해 timeout, skip 또는 프로덕션 orchestration 정책을 바꾸지 않았다.

최초의 새로운 읽기 전용 검토는 확인된 제품 P1/P2/P3를 발견하지 않았고,
앞선 54개 집중 테스트를 독립 실행했다. 정확한
Owner 결정을 다시 가져왔다. 최종 증거/문서 재검사는 아래에 기록한다.

<a id="resources-and-review-limits"></a>

### 리소스와 검토 한계

테스트 후 전용 DB에는 예상 밖 테스트 스키마, 비감사
트랜잭션, data lock 또는 다른 client가 없었다. 첫 감사에는 감사
자체 트랜잭션이 포함됐다. 자신을 제외한 autocommit 감사에서 남은 트랜잭션이 없음을 검증했다.
작업의 `codex-rt10b-readout-mysql` container와 확인한 익명
volume을 제거했다. 이 작업 scratch root 아래에서 경로를 확인한 child test 디렉터리
아홉 개를 생성 동영상/환경 파일과 함께 제거했다. RAW 콘솔
로그, 증거 JSON/JUnit, 내부 계획, 감사 스크립트는 ignored 상태로 남는다.
테스트는 child process 종료와 engine connection 반환을 assertion으로 확인했다.
공유 Docker engine은 실행 상태로 남겼다.

검토에서 finding으로 채택하지 않은 고려사항은 falsey 사용자 정의
provider가 기존 Readout fallback을 유발한다는 가정, 공개
observation 입력이 없는 예전 clip job, 손상된 실행 간 ProducedReader 참조였다.
이 우려에 대해 실패하는 유효한 프로덕션 경로는 입증되지 않았다. 새
fallback/마이그레이션/common-store 정책은 도입하지 않았다. 영속 T1 전 취소는
승인된 RUN_NOT_PRODUCED 의미론을 따른다. 실제 candidate
재선택과 새 generation은 이후 집중 검증에 추가했다.
운영 배포에는 여전히 명시적 provider 주입이 필요하다. 이 PR은
Paddle을 기본 활성화하거나 설치/모델/하드웨어 동작을 검증하지 않는다.

<a id="final-same-reviewer-recheck"></a>

### 동일 검토자의 최종 재검사

같은 새로운 읽기 전용 검토자가 최종 13개 파일 작업 delta를 다시 확인하고,
집중 검사 **69건 통과 (3.67 s)**를 독립 실행했다. 한정된
MySQL JSON/JUnit 세트 다섯 개를 모두 검증하고, 최초 회귀 실패 48건과
통과한 재실행 48건이 정확히 일치함을 확인했으며, 원래 718,403바이트 runtime-log prefix를
HEAD 및 SHA-256과 대조했다. 최종 판정: **P1/P2/P3 없음**. 검토 수정
회차는 필요하지 않았다. 검토자는 source/index/HEAD를 변경하지 않았다.
남은 한정사항은 명시적으로 미실행한 전체 suite/CI/실제
Paddle 경로와 분리된 회귀 증거이며, 전체 GREEN 주장으로 해석하지 않는다.

최종 상태: 변경 파일 13개, staged 파일 없음, HEAD와 origin/develop은
기준 SHA를 유지한다. commit/push/PR/Issue 변경 없음. 상태는 계속
**IN_PROGRESS · Refs #297 (RT-10(b))**다.

<a id="exact-intended-file-set"></a>

## 정확한 예정 파일 집합

- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/readout_handlers.py`
- `src/daesingo/worker/readout_inputs.py`
- `src/daesingo/worker/readout_composition.py`
- `tests/worker/readout_support.py`
- `tests/worker/test_readout_handlers.py`
- `tests/worker/test_readout_inputs.py`
- `tests/worker/test_readout_composition.py`
- `tests/worker/test_readout_mysql.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_readout_process_mysql.py`
- `docs/runtime/rt10b-readout-handlers.md`
- `docs/runtime/runtime-implementation-log.md` (추가만 허용)

전체 로컬 pytest, 전체 필수 MySQL gate, 원격 CI는 여기서 실행하지 않았다.
기존 gate/workflow/skip/xfail/30분/900초 정책은 그대로다.
