# 단서 구조화 소진 — `EXHAUSTED`로 정산하고 빈 단서로 첫 탐색을 이어 간다

> 2026-10-27 · 결정 추적 [#405](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/405) · 관련 `start-analysis.md` §3-5 · `case-wait-timeout.md` §5 · `stop-analysis.md`

## 1. 목표 · 범위

Runtime이 `HINT_EXTRACT`를 재시도까지 `STALE`로 끝냈다고 확정하면 T2가 오지 않아 case가 `SEARCHING`에 머물렀다(`case-wait-timeout.md` §5 한계). Runtime이 별도 소진 알림을 보내고, case는 그 알림을 받아 분석을 이어 간다.

**범위:** case 쪽 정산 사유 · 반영 함수 · 진입점 · 테스트.
**범위 밖:** Runtime의 `job_exhaustion_notice` outbox · redelivery · receipt · DTO · port · Worker composition 연결(Runtime 소유, #405 제안). `HINT_EXTRACT` 외 kind의 소진(Fine · 판독 · export) — kind마다 후속 동작이 달라 따로 정한다.

## 2. 결정

1. **정산 사유 `EXHAUSTED`를 더한다**(`domain.JOB_SETTLE_REASONS`). 기존 사유는 맞지 않는다 — `REFLECTED`는 결과가 와서 반영됐다는 뜻이고, `STOPPED_WAITING`은 case가 자기 마감으로 기다리기를 그만뒀다는 뜻이다. 소진은 「Runtime이 결과가 더 오지 않는다고 확정했다」는 별개 사실이라, 기록만 보고도 결과 없이 넘어간 탐색인지 알 수 있게 나눈다.
2. **후속 동작은 구조화 실패와 같다**(#405 D-3, `start-analysis.md` §3-5). hints 4개를 `None`으로 두고 첫 `COARSE_SEARCH`를 발주한다. 사용자에게는 실패 출구를 주지 않고 「전체 찾기」로 이어 간다(#259와 같은 이유 — 단서는 탐색을 좁히는 보조 입력이다).
3. **`hint_unclear`는 세우지 않는다.** 구조화가 보류(`ABSTAINED`)한 것이 아니라 실행이 끝나지 못한 것이라 `search.hint_unclear` notice를 띄우지 않는다.
4. **받는 조건은 결과 반영과 같다(`awaits_result()`).** 이미 정산된 job(사용자 중단 `CANCELLED` · 먼저 온 결과 `REFLECTED` · 같은 알림 재전달 `EXHAUSTED`)이면 아무것도 바꾸지 않고 저장하지 않으며 `NO_CHANGE`(+ 그 정산 사유)를 돌려준다. Runtime은 `NO_CHANGE`도 receipt해 재전달을 끝낸다.
5. **맞지 않는 알림은 오류다.** 이 case가 발주하지 않은 `job_id`, JobRecord kind와 다른 알림 kind, `HINT_EXTRACT`가 아닌 kind는 `ValueError`로 올린다. `NO_CHANGE`로 받으면 receipt가 남아 잘못된 알림이 조용히 사라진다. T2 `reflect_execution`의 배선 오류 규칙과 같다.
6. **`case_rev`는 올리지 않는다.** 사용자 요청이 아니라 실행 사실이다(결과 반영과 같다).

## 3. 구현

- `analysis_start.reflect_hint_exhaustion(case, *, job_id, kind, timelines, budget) -> bool` — aggregate 수준. 검사(§2-5) → `awaits_result` → hints `None` · `EXHAUSTED` 정산 · `issue_initial_search`.
- `service.receive_hint_exhaustion(case_id, *, job_id, kind, store, timelines, budget=None) -> ExhaustionResult` — `receive_hint_extraction_result()`와 같은 모양. `load_for_update` → 반영 → 바뀐 경우만 `save`. 예외는 그대로 올라가고 rollback · retry는 호출자 몫이다.
- `ExhaustionResult(status: "APPLIED" | "NO_CHANGE", appended_job_records, reason)` — `APPLIED`면 첫 `COARSE_SEARCH` 1건을 composition root가 같은 transaction에서 enqueue한다.
- lock 순서는 T2와 같다: case `load_for_update` → (Runtime) notice `FOR UPDATE` → enqueue · receipt.
- Runtime port(`ExhaustionReceiver.receive(conn, notice)`)에 맞춘 adapter는 Runtime DTO가 정해진 뒤 더한다. 그때 notice의 `case_id` · `job_id` · `kind`를 이 진입점에 넘기기만 하면 된다.

## 4. 사용자 쪽 대기 — case 대기 timeout을 두지 않는다

`start-analysis.md` §3-5의 90초는 두지 않는다(#405 결정 댓글, 2026-10-26).

| 상황 | 출구 |
| --- | --- |
| 정상 운영 · 재시도까지 `STALE` | 소진 알림 → `EXHAUSTED` → 빈 단서로 첫 탐색 |
| Worker 부재 · 재시작 지연 등(Runtime hard bound 없음) | 사용자가 **[분석 중단]**(`STOP_ANALYSIS`) — 기다리던 `HINT_EXTRACT`를 `CANCELLED`로 정산 |

Runtime 조건부 계산(첫 attempt 마지막 heartbeat부터 최종 소진까지 약 157초)은 보장값이 아니라 마감 근거로 쓰지 않는다.

## 5. 알려진 한계

- **단서 구조화 단계에서 중단하면 출구가 「새 신고」뿐이다.** 다시 낼 이전 `COARSE_SEARCH`가 없어 `case.analysis_stopped`의 `actions`가 빈다. #410 `EDIT_HINT`가 정해지면 그 command가 출구가 된다.
- 소진 뒤 늦은 T2가 오면 `reflect_execution`은 `EXHAUSTED`를 「다른 경로로 이미 반영된 job」으로 보고 `ValueError`를 올린다. Runtime은 최종 `STALE` execution의 T1을 받지 않으므로 생기지 않는 경로로 본다. 생기면 Runtime `ReflectionOutcome.reason`에 `EXHAUSTED`를 더할지 함께 정한다.

## 6. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| 소진을 `REFLECTED`(구조화 `FAILED`와 같은 사유)로 정산 | 결과 없이 넘어간 것과 결과를 반영한 것이 기록에서 구분되지 않는다 |
| 소진을 `STOPPED_WAITING`으로 정산 | case 마감이 아니라 Runtime 확정이다. `case.analysis_timed_out` 판정과도 섞인다 |
| 맞지 않는 알림을 `NO_CHANGE`로 받기 | receipt가 남아 배선 오류가 조용히 사라진다 |
| 157초보다 넉넉한 사용자 쪽 마감 | 보장값이 아니고, 마감 뒤 보여 줄 출구(새 action · 화면)가 따로 필요하다 |

## 7. 테스트

`tests/case/test_hint_exhaustion.py` — `EXHAUSTED` 정산 · hints `None` · `hint_unclear` 없음 · 첫 탐색 발주 · `running_jobs`, `case_rev` 유지, 재전달 `NO_CHANGE(EXHAUSTED)` · 추가 발주 없음, 결과 먼저 `NO_CHANGE(REFLECTED)`, 중단 먼저 `NO_CHANGE(CANCELLED)` · `analysis_stopped` 유지, `NO_CHANGE`는 저장 안 함, 모르는 job · 다른 kind · 탐색 job 알림은 `ValueError`, 타임라인 실패는 저장 안 함.

## 8. 남은 것

- Runtime: `job_exhaustion_notice` outbox · redelivery · receipt · DTO · port, Worker composition에서 이 진입점 연결 · MySQL 통합 테스트.
- case: Runtime port가 정해지면 `ExhaustionReceiver` adapter.
