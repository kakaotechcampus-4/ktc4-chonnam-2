# ADR — `JobExecution` Data Contract

**Status:** Accepted — 일부 판단은 후속 ADR로 정정

> **현재 적용 범위:** `adr-consistency-followup-2026-09-06.md`가 무근거 종결·수락일·회신 의도·소비자 확인 및 통합 가능 결론을 정정한다. 아래 본문은 당시 결정 기록이며 현재 Pending을 닫는 근거가 아니다. 캐시 복원과 현재 규칙은 해당 계약 및 후속 ADR을 따른다.

**Decider:** 김준영 (`common/runtime` 계약 Owner) — 구현 담당 정철원
**Date:** 2026-09-05
**Contract:** `../contract-job-execution.md`
**상위 결정:** `adr-job-record-case-view.md` 부록-A §6·§7·§13 · `adr-consistency-2026-09.md` C1-8

---

## 1. Context

`adr-job-record-case-view.md` 부록-A가 `JobRecord`를 **Job Intent로 범위를 좁히고 실행 상태를 별도 `JobExecution`으로 분리**하기로 확정했다. v4 §5-1 ⑫에도 `JobExecution`이 등재됐다. **그런데 계약 문서가 없었다.**

정합성 검수 착수 전 판정에서 커버리지 공백은 축 B·D·E의 판정을 오염시킨다는 이유로(D-2) PM이 먼저 쓰기로 했다. `common/runtime`은 PM(김준영) 소유이므로 트랙 1에 해당한다.

## 2. Decision

**ADR이 이미 고정한 것은 그대로 옮기고, 목 응답에 필요한 최소한만 새로 정했다.**

ADR에서 그대로 온 것 — status 5값(`QUEUED/RUNNING/SUCCEEDED/FAILED/STALE`), **`CANCELLED` 미포함**(제품 요구가 없다), 캐시 semantics(`force_rerun=false` + 동일 fingerprint의 **`SUCCEEDED`** 결과만 재사용, `FAILED`/`STALE`은 재실행), `JobRecord`에서 이관된 필드 목록.

PM이 새로 정한 것은 셋뿐이고 계약 §10에 모아 두었다 — `execution_id` 신설 · 시각 3필드(`queued_at`/`started_at`/`ended_at`) · `cost`를 금액이 아니라 `usage_refs[]`로 표현.

**`execution_id`를 신설한 이유:** `attempt`가 2 이상이면 같은 `job_id`에 실행 row가 여러 개 생긴다. ADR §7의 「동일 `job_id` 재사용 없음」은 **발주** 식별자 규칙이므로 실행 row에는 별도 키가 필요하다.

**`cost`를 금액으로 두지 않은 이유:** v4 §4-모듈2 ⑥과 `contract-analysis-run-candidate-event.md`가 「상세 ledger의 authoritative source는 `UsageRecord`」로 확정했다. 금액을 여기 복제하면 원천이 둘이 된다(`ownership.md` §6).

## 3. 기각한 안

**`CANCELLED`를 status에 넣는다** — 기각. ADR 부록-A가 「제품 요구가 없다」로 이미 닫았다. 값 공간을 미리 늘리면 `CaseView.progress.state` 매핑도 같이 늘어난다.

**`JobRecord`에 실행 상태를 남겨 둔다** — 기각. 상위 ADR의 결정 1이 Job Intent/Execution 분리이고, 되돌리면 v4 §12 RT8이 다시 열린다.

## 4. `CaseView` 매핑

당시 계약 §6에 매핑표를 적었다. 현재 매핑 원천은 `../contract-job-record-case-view.md` B절 §13이다.

```
QUEUED        → PENDING
RUNNING       → RUNNING
SUCCEEDED     → DONE
FAILED, STALE → FAILED
```

`CaseView.running_jobs[].status`는 `PENDING | RUNNING`만 갖는다. 종료된 실행은 `running_jobs`에 넣지 않는다.

## 5. Consumer Review

계약을 **소비자 리뷰 없이 닫았다**(`adr-consistency-2026-09.md` §3 Consequences에 비용으로 기록). 소비자가 볼 범위를 §10 세 항목으로 좁혀 두었고, 이견이 나오면 그 자리에서 되돌릴 수 있다.

2026-09-06 공지 시점까지 이견 없음 — 유소연·신유민 확인.

## 6. 미결

retry/backoff/lease/heartbeat 임계값, `STALE` 판정 초 단위. **Runtime 구현 세부이며 채우지 않았다.**
