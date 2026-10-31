<a id="rt-10b-hint_extract-exhaustion-notice--implementation-notes"></a>

# RT-10(b) HINT_EXTRACT 소진 알림 — 구현 기록

`RT-10 IN_PROGRESS · Refs #297 (RT-10(b)) · Related #405`

2026-10-28 · 미커밋 / 미스테이징 · PR/merge SHA 미정.
합의: [#405](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/405). Runtime/Case 포트 합의와 Case PR #415를 포함한다.
Case 의미론의 권위 있는 기준은 계속 [hint-exhaustion](../modules/case/decisions/hint-exhaustion.md)이다.

## 구현 결과

Runtime은 `common/jobs/exhaustion.py`, 해당 DTO/포트, outbox 전달, 새
`job_exhaustion_notice` 테이블을 소유한다. `case/exhaustion_adapter.py`는 호출자의 Connection에서 병합된
`service.receive_hint_exhaustion()`에 위임하고 Case
진단값 `reason`은 제외한다. `worker/case_composition.py`는 기존의 영속
Recording 타임라인 기능을 제공하고, 프로덕션 진입점은 두 어댑터를 모두 제공한다.

`sweep_expired()`는 취소되지 않은 HINT_EXTRACT가
재시도 없이 STALE이 될 때만 알림을 삽입한다. STALE과 INSERT는 같은 트랜잭션에 속한다. `sweep_once()`는
기존 재시도 ID와 함께 B-D8 재시도에 들어가기 전에 알림 ID를 고정한다.
COMMIT 결과 불명 복구는 원래 실행을 잠그고, 영속 저장된
STALE/ended_at과 원래 알림의 식별값/사실을 확인하며, 이미 STALE인 행에 대해
대체 알림을 합성하지 않는다. `SweepOutcome`과 메트릭의 의미는
유지된다. 다른 kind에는 소진 알림을 보내지 않는다.

<a id="schema--migration"></a>

## 스키마 · 마이그레이션

정방향 마이그레이션 `runtime_0006`은 `runtime_0005` 다음이다. 고정된 DDL은
실시간 메타데이터와 독립적이다. 열: notice_id (PK), job_id (UNIQUE), case_id, kind,
final_execution_id, attempt, terminal_status, reason, exhausted_at, trace_id,
case_acknowledged_at. case_acknowledged_at만 nullable이다. 두 타임스탬프 모두
DATETIME(6)이며 UTC로 저장한다. exhausted_at은 terminal UPDATE가 실제로
영속 저장한 ended_at에서 읽으며, 기존의 인과적 하한도 포함한다.

FK는 Runtime 소유의 job_execution.execution_id를 가리킨다.
모듈 간 Case/JobRecord FK는 없다. CHECK는 HINT_EXTRACT, STALE, EXHAUSTED와
양수 attempt를 제약한다. 대기 스캔 인덱스는 (case_acknowledged_at, notice_id)이다.
Runtime은 알림을 실행/job/case/attempt/status/time/
trace 사실과 대조해 검증하고, receipt 전에 후속 attempt가 있으면 거부한다. 취소 여부는
generation 잠금 아래 확인한다. STALE에 나중에 추가되는 STOP_ANALYSIS 표시는 변경 가능한 상태이며,
이미 생성된 알림이 NO_CHANGE(CANCELLED)로 확인되도록 허용한다.

기존 실행기는 그대로다. API/Worker 시작 전에 한 번 마이그레이션하며,
정방향만 지원하고 운영 downgrade, 시작 시 마이그레이션, 자동
DDL/COMMIT 결과 불명 재실행은 없다. 이미 적용된 head는 아무 작업도 하지 않는다. 동일 프로세스 가드는
유지하며, 배포 시 별도 마이그레이션 프로세스는 직렬화해야 한다. MySQL DDL은
실패 시 부분 스키마를 남길 수 있으며 기존 수동 복구 정책을 따라야 한다.
저장소 마이그레이션 checksum 레지스트리는 발견되지 않았다. 과거 마이그레이션 파일을 바꾸지 않고
head/테이블 fixture를 갱신했다.

<a id="생성--전달--receipt-transaction"></a>

## 생성 · 전달 · receipt 트랜잭션

1. 잠금 없이 대기 알림 ID를 스캔하고, ID별로 B-D8 트랜잭션 하나를 시작한다.
2. 트랜잭션을 재실행할 때마다 잠금 없이 알림 receipt를 읽는다. 영속
   receipt가 있으면 COMMIT 응답이 유실된 뒤에도 Case 수신기 호출을 건너뛴다.
3. Case 어댑터는 공개 서비스를 호출한다. 이 서비스는 Case를 먼저 잠그고,
   Case가 발급한 job/kind를 검증한 뒤 EXHAUSTED를 적용하거나 NO_CHANGE를 반환한다.
4. Runtime은 알림을 FOR UPDATE로 잠그고 불변 스냅샷과
   해당 terminal 실행을 확인한다. Case 잠금보다 먼저 잡는 Runtime 잠금은 없다.
5. APPLIED는 정확히 하나의 COARSE_SEARCH 레코드를 반환한다. Runtime은 기존 enqueue를 통해
   job_id/case_id/kind만 투영한다. NO_CHANGE에는 후속 작업이 없다.
6. Runtime은 UTC_TIMESTAMP(6)으로 case_acknowledged_at을 기록한다. Case 저장,
   후속 enqueue, receipt는 함께 commit/rollback된다.

동시 전달은 Case에서 직렬화된다. 해당 잠금 뒤 receipt가 발견되면
중복 enqueue를 억제한다. 기존 receipt가 있는데 APPLIED를 반환하는 불일치는
오류다. 잘못된 Case/job/kind, 유효하지 않은 포트 결과, 불변값 불일치,
enqueue 실패 또는 receipt 실패는 해당 후보 전체를 롤백한다. 한 후보의
실패는 다른 후보를 중단하지 않는다. 스캔 실패는
기존 시작 시 admission 재시도 또는 주기적 DB 오류 정책으로 전파된다.

`SweepService.redeliver_exhaustion`은 기존 T2 콜백과 별도다.
시작 시 첫 claim 전에 둘 다 완료한다. 주기적 sweep도 둘 다 실행하며,
기존 stop/join 수명주기는 유지한다. 선택적 수신기가 없으면
기존의 선택적 T2 reflector 패턴처럼 알림을 대기 상태로 남긴다.

<a id="port--operational-event"></a>

## 포트 · 운영 이벤트

`JobExhaustionNotice`에는 합의된 notice/job/case/kind/final execution/
attempt/status/reason/exhausted_at 필드만 있다. trace_id는 공개 DTO 밖의
Runtime 상관관계 저장값으로 남는다. `ExhaustionResult`에는 APPLIED 또는
NO_CHANGE와 appended_job_records만 들어간다. Case의 정산 사유는 외부로 내보내지 않는다.
수신기는 commit, rollback, 트랜잭션 재시도를 수행하지 않는다.

`runtime.exhaustion.failed`는 status=FAILED인 사전 정의 ERROR다.
이 이벤트의 주변 상관관계를 지우며 notice/job/case ID, payload,
provider 응답, 원래 예외, locator, 파일명 또는 경로를 기록하지 않는다. 후보
실패 시 receipt를 NULL로 남겨 이후 sweep에서 처리하게 한다. 이벤트 카탈로그를 확장하며,
로그에 알림 내용이나 원시 예외를 추가하지 않는다.

<a id="plan-대비-변경--새-implementation-detail"></a>

## 계획 대비 변경 · 새로운 구현 세부사항

합의된 #405 경계는 별도의 RT-10(b) 작업 범위다. 선택적 구성
인자는 기존 T2 패턴을 따른다. 같은 모듈 내 FK와 엄격한 최소
enqueue 투영은 물리적 구현 세부사항으로 선택했다. 기존
T2, ExecutionOutcome, produced, job_execution.case_applied_at은 그대로다.
새 재시도 정책, scheduler, timeout, provider 호출 또는 설정값은 없다.

## Contract / Decision / Baseline 영향

- Contract 변경: 없음. 구현은 합의된 #405 포트를 사용한다.
- Decision 변경: 없음. Case PR #415의 공개 동작을 그대로 사용한다.
- Baseline 변경: 없음. 기존 재시도 제한/시간, B-D8, admission을 유지한다.
- Owner 확인 포인트: 별도의 terminal outbox, 이벤트, 마이그레이션 감사.
  Fine/readout/export 소진 정책은 이 구현 범위 밖이다.

<a id="verification"></a>

## 검증

제품 수정 전에 RED 증거가 있다. 실제 MySQL 생성/원자성/
마이그레이션 실패 세 건, 전달/시작 실패 두 건이며, checker inventory를 추가하기 전에
family 누락 테스트 아홉 건이 실패했다. 최초 통합 실행은 44건 통과와
테스트 fixture/driver 예외 기대값 실패 두 건이 있었고 이후 수정했다.

소유한 MySQL 8.4.7에서 얻은 새로운 로컬 증거:

- 새 소진 + Case 소진 + 진입점: 75건 통과.
- 추가 stored adapter/포트/스캔 정책 + DTO + 정상 Search 프로세스 E2E:
  31건 통과(실제 독립 API/Worker OS 프로세스 포함).
- 실제 소진 전용 strict-checker 범위: 61개 테스트 / 61개 매개변수 경계 /
  12개 family. 누락/메타데이터/phase/skip/xfail/JUnit 변형 927건 거부.
  전체 필수 MySQL 또는 전체 strict-gate 결과는 아니다.
- 경계 검사: 위반 없음. Contract fixture: 구조 62건, JSON 26건,
  의미 검사 104건 통과. workflow 정책은 그대로이며 diff 검사 통과.
- 관련 sweep/T2/reflection/composition/produced/timestamp/migration MySQL
  회귀: 224건 통과. 기존 Starlette TestClient 폐기 예정 경고 한 건.
- 기존 취소 상태/트랜잭션/sweep 제어: 9건 통과, 10건 선택 해제.
- Gate 단위 누락 제어: 7160건 통과, 2031건 선택 해제(최종 취소 의무 두 개
  추가 전). 최종 집중 실행에서 현재 소진 gate 제어 372건을 모두 재실행했다.
- 늦은 취소 수정 후 통과 실행: 461건 통과(실제 MySQL
  경계 60건, Runtime DTO 테스트 18건, Case 소진 테스트 11건, gate 제어 372건).
- 카탈로그 회귀: 의도하지 않은 메트릭 자동 포함으로 RED 1건, 이후 GREEN 25건과
  실제 emitter 스키마 위반 없음. 기존 메트릭 inventory는 유지한다.
- 늦은 실제 STOP_ANALYSIS 전달/COMMIT 결과 불명 복구: RED 2건, 이후
  최종 461개 테스트 실행에서 GREEN. 알림 생성 뒤 취소가 STALE에 표시될 수 있다.
  이는 변경 가능한 상태이며, 앞선 소진 사실과 모순되지 않는다.
- 구현 이력이 없는 새로운 읽기 전용 검토자: 최초 P2 두 건,
  P1 없음. 두 건 모두 유효한 RED로 재현하고 수정했다. 같은 검토자가
  둘 다 해결되었으며 이 범위에서 새로 발견되거나 남은 P1/P2가 없음을 확인했다.
- 검토 수정 1: nested 메타데이터/family 수와 출력
  inventory에 소진을 포함한다. 집중 제어는 통제된 입력으로 원래 nested 누락 단계를
  최종 assertion까지 실행한다. 메타데이터 누락 244건과
  family 누락 12건이다. 전체 nested database-child 실행은 아니다.
- 검토 수정 2: 반환된 execution_id를 Python에서 정확히 비교한다. MySQL의
  ascii_bin PAD SPACE 비교는 뒤에 공백이 붙은 FK/WHERE 별칭을 허용한다.
  실제 MySQL RED는 수정 전 잘못된 APPLIED/enqueue를 입증했다.
  최초 literal 비교 fixture 시도는 수정했으며 유효한 제품 RED로 취급하지 않는다.
  이후의 실제 열 RED와 GREEN은 보존한다.
- 두 검토 수정 후 최종 집중 실행: 469건 통과(실제 MySQL 61건,
  DTO 18건, Case 소진 11건, gate 제어 378건, nested 누락 제어 1건).
- 검토자는 469개 테스트 증거를 확인했다. 구현자는 이후
  실제 한정 checker를 매개변수 61개 / 거부된 변형 927건으로 갱신했다.
  검토자는 갱신된 변형 산출물을 살펴보지 않았다.
- 이는 범위 검토이며, 전체 CI/merge 승인은 아니다.

요청에 따라 전체 pytest, 전체 필수 MySQL과 nested strict gate는 의도적으로
원격 CI에 남겨 두었다. Checker 계산 논리는 그대로이며,
inventory와 독립 테스트 inventory만 확장했다. 기존 skip/xfail,
nested 900초, workflow 30분 정책을 유지한다.

## 남은 위험

Worker 부재 시 여전히 유한한 전달 SLA가 없으며, 대기 알림에는 실행 중인
sweeper가 필요하다. 반복적으로 잘못 연결된 알림은 안전한 실패 이벤트와 함께 대기 상태로 남으며,
복구는 운영 작업이다. 과거 STALE을 backfill하지 않는다. 이 마이그레이션은
새로 최종화되는 sweep부터 원자적 outbox를 시작한다. 다른 kind의 소진과
retention/purge 정책은 별도 결정 사항이다. 전체 원격 CI는 여전히 필요하다.
