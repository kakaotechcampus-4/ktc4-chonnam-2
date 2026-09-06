# Data Contract — JobExecution v1

**Status:** `Final — Accepted`
**Accepted:** `2026-09-05`
**수락 근거:** PM의 common/runtime Owner 결정과 `adr-job-record-case-view.md` 부록-A를 따른다. **소비자 수락·무이견을 확인한 상태라는 뜻은 아니다.** 신규 결정과 접합부 확인 범위는 §10·§11 및 `adr/adr-consistency-followup-2026-09-06.md`를 따른다.

**Architecture Contract:** v4 §5-1 ⑫ · §4-모듈5 ④⑤
**Contract Version:** `job-execution/v1`
**Producer / Owner:** `common/runtime` — 김준영 (계약) · **구현 담당 정철원** (2026-09-04 백엔드 회의)
**Consumers:** `case` — 유소연 (Runtime) · `web` — 신유민 (`CaseView` projection 경유) · `eval` — 김대원 (실행 성공률 집계)
**Related ADR:** `adr/adr-job-execution.md` · 상위 결정 `adr/adr-job-record-case-view.md` 부록-A

> **이 문서가 왜 지금 생겼나.** `JobRecord` ADR이 실행 상태(status/attempt/cost/produced/failure_kind)를 `JobRecord`에서 떼어내 별도 `JobExecution` 계약으로 이관하기로 확정했는데(부록-A §6·§10·§12), 그 계약 문서가 없었다. 목데이터 통합에서 queue 목 응답을 만들 근거가 없으므로 PM이 ADR의 기존 결정과 PM 소유 영역의 추가 결정을 모아 작성했다. 새로 정한 것은 §10에 따로 표시했고, 정하지 않은 것은 §11에 미결로 남겼다.

---

## 1. 계약 목적

`case`가 발주한 Job 1건(`JobRecord`)의 **실행 상태 1회분**을 기록한다. 발주 의도는 `JobRecord`가 소유하고 본 계약은 그 의도가 실제로 어떻게 돌았는지만 소유한다.

`case`는 이 계약을 통해 「지금 돌고 있는가 / 끝났는가 / 결과를 반영해도 되는가」만 알면 되고, lease·heartbeat·retry 타이밍은 알 필요가 없다(v4 §4-모듈5 ④ · 원칙 6).

## 2. Producer / Consumer

**Producer**: `common/runtime`. 계약 Owner는 김준영, 구현 담당은 정철원이다.

**Consumer**

| 소비자 | 무엇을 읽는가 |
| --- | --- |
| `case` (Runtime) | `status` · `produced` — 현재 `case_rev`와 맞는 결과만 domain state에 반영한다 |
| `web` | 직접 읽지 않는다. `CaseView.progress[].state`와 `running_jobs[].status`로 projection된 값만 본다 (v4 원칙 7) |
| `eval` | 실행 성공률·재시도 횟수 집계. **`case`/`evidence`를 import하지 않는다** |

## 3. 책임 경계

### `common/runtime`이 소유하는 것

- Job 1건의 실행 상태 전이와 그 시각
- 시도 횟수(`attempt`)
- 실행이 만들어낸 산출물 참조(`produced`)
- 실행 실패의 종류(`failure_kind`)
- 사용량·비용 원장으로의 연결(`usage_refs`)

### `common/runtime`이 소유하지 않는 것

- **왜 이 작업이 필요한지** — `JobRecord`(case)
- 캐시를 쓸지 말지의 정책 판단 — `JobRecord.force_rerun`(case)
- 결과를 domain state에 반영할지 — `case`
- 산출물의 의미·유효성 — 각 생산자 계약
- 비용 금액의 authoritative 값 — `UsageRecord`
- 화면 표현 — `CaseView`

## 4. 확정 Contract 스키마 (JSON)

```json
{
  "execution_id": "string",
  "job_id": "string",
  "status": "QUEUED | RUNNING | SUCCEEDED | FAILED | STALE",
  "attempt": "int",
  "queued_at": "ISO8601",
  "started_at": "ISO8601 | null",
  "ended_at": "ISO8601 | null",
  "produced": "ContractRef[]",
  "failure_kind": "string | null",
  "usage_refs": "ID[]"
}
```

## 5. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 근거 |
| --- | --- | --- | --- | --- |
| `execution_id` | string | Y | 실행 1회분의 고유 식별자. 재사용하지 않는다 | 신규 (§10-1) |
| `job_id` | string | Y | 소속 `JobRecord.job_id` | ADR 부록-A §6 |
| `status` | enum(5) | Y | 실행 상태 | **ADR 부록-A §13-2 확정** |
| `attempt` | int | Y | 이 `job_id`에 대한 몇 번째 시도인가. 1부터 시작 | ADR 부록-A §6 이관 목록 |
| `queued_at` | ISO8601 | Y | queue에 들어간 시각 | 신규 (§10-2) |
| `started_at` | ISO8601 \| null | Y(키) | `RUNNING` 진입 시각. `QUEUED`면 null | 신규 (§10-2) |
| `ended_at` | ISO8601 \| null | Y(키) | 종료 시각. 종료 상태가 아니면 null | 신규 (§10-2) |
| `produced` | ContractRef[] | Y(빈 배열 허용) | 이 실행이 만든 산출물 참조. 공통 모양은 `contract-observation.md` §3의 `ContractRef` | ADR 부록-A §6 이관 목록 |
| `failure_kind` | string \| null | Y(키) | 실패 종류. **모듈 접두어 규칙을 따른다** | ADR 부록-A §2 (v1 p.20) |
| `usage_refs` | ID[] | Y(빈 배열 허용) | 이 실행에 속한 `UsageRecord` 참조 | §10-3 |

## 6. Enum / State

### `status` — 닫힌 enum 5값

| 값 | 의미 |
| --- | --- |
| `QUEUED` | 발주됐고 아직 실행되지 않음 |
| `RUNNING` | 실행 중 |
| `SUCCEEDED` | 정상 종료. `produced`가 유효하다 |
| `FAILED` | 실행이 실패로 종료됨 |
| `STALE` | 실행 중이던 worker가 살아 있지 않다고 판정됨 |

**`CANCELLED`는 두지 않는다** — 현재 제품 요구가 없다(ADR 부록-A §13-2).

허용 전이는 다음뿐이다.

```
QUEUED → RUNNING → SUCCEEDED
                 → FAILED
                 → STALE → (새 execution_id로 재시도)
QUEUED → FAILED          (실행 전 발주 자체가 무효화된 경우)
```

### `CaseView`로의 projection

상태 매핑은 `contract-job-record-case-view.md` B절 §13의 닫힌 항목을 따른다. 이 계약에 매핑표를 복제하지 않는다. Domain PARTIAL 처리의 접합은 §11의 확인 대기 항목이다.

### `failure_kind`

모듈 접두어로 구분한다. 값 목록은 닫히지 않으며, 신규 값은 해당 모듈의 `decisions/failure-taxonomy.md`에 등재한 뒤 사용한다(`modules/search/`·`modules/readout/`).

`RUNTIME_` 접두어는 실행 기반 자체의 실패에 쓴다. `status=STALE`일 때 `failure_kind`는 null일 수 있다 — worker가 실패를 보고할 기회 없이 사라진 경우다.

## 7. 정상 예시

```json
{
  "execution_id": "exec_9001",
  "job_id": "job_51",
  "status": "SUCCEEDED",
  "attempt": 1,
  "queued_at": "2026-09-01T18:00:01Z",
  "started_at": "2026-09-01T18:00:04Z",
  "ended_at": "2026-09-01T18:02:37Z",
  "produced": [{"kind": "analysis_run", "ref": "run_2026_0901_0007"}],
  "failure_kind": null,
  "usage_refs": ["usage_101", "usage_102"]
}
```

## 8. 실패 / STALE 예시

```json
{
  "execution_id": "exec_9002",
  "job_id": "job_61",
  "status": "STALE",
  "attempt": 2,
  "queued_at": "2026-09-02T09:10:00Z",
  "started_at": "2026-09-02T09:10:03Z",
  "ended_at": null,
  "produced": [],
  "failure_kind": null,
  "usage_refs": []
}
```

`ended_at`이 null인 채로 `STALE`이 될 수 있다. 종료 시각을 관측하지 못한 것이 STALE의 정의이므로 값을 만들어내지 않는다(`product-spec.md` §7).

## 9. 불변조건

1. `execution_id`는 재사용되지 않는다.
2. 하나의 `job_id`에 여러 `JobExecution`이 붙을 수 있다. `attempt`는 그 안에서 1부터 증가한다.
3. `status=SUCCEEDED`가 아니면 `produced`를 유효한 결과로 취급하지 않는다.
4. `status ∈ {QUEUED, RUNNING}`이면 `ended_at`은 null이다.
5. `status=QUEUED`이면 `started_at`은 null이다.
6. 캐시 재사용 조건은 `contract-job-record-case-view.md` A절 §7을 따른다. 실행 결과만의 fingerprint 비교로 범위를 넓히지 않는다(근거: `adr-job-record-case-view.md` A절 §7).
7. 비용 금액의 authoritative 원천은 `UsageRecord`다. 본 계약은 `usage_refs`로 연결만 하고 금액을 자체 필드로 중복 보관하지 않는다.
8. `case`는 현재 `case_rev`와 맞지 않는 실행의 `produced`를 domain state에 반영하지 않는다(v4 §4-모듈5 ④).

## 10. PM이 새로 정한 것 (소비자 통보 대상)

아래 세 행은 처음 기록한 추가 필드 목록이며 전체 신규 결정 목록이 아니다. 상위 ADR은 §6의 세부 허용 전이, attempt 기산·증가/실행 row 단위, RUNTIME_ 접두어와 STALE의 failure_kind nullable까지 모두 고정하지 않았다. 이들은 본 문서의 PM 추가 결정이다. **소비자 확인은 §4~§9와 §11을 포함하며, 필드 추가만으로 호환성을 보증하지 않는다.** 실제 소비자 통보·수락 원문은 확인 대기다.

| # | 항목 | PM 결정 | 왜 |
| --- | --- | --- | --- |
| 10-1 | 실행 1회분의 식별자 | `execution_id` 신설. `job_id`를 PK로 쓰지 않는다 | `attempt`가 2 이상이면 같은 `job_id`에 실행 row가 여러 개 생긴다. ADR §7 「동일 job_id 재사용 없음」은 발주 식별자에 대한 규칙이고 실행 row에는 별도 키가 필요하다 |
| 10-2 | 시각 필드 3개 | `queued_at` / `started_at` / `ended_at` | v4 §4-모듈5 ④가 `available_at`을 언급하지만 그건 retry 타이밍(구현 세부)이다. 계약에 필요한 것은 「queue 대기 시간」과 「실행 시간」을 분리해 볼 수 있는 최소 3점이다. `eval`의 latency 집계도 이 3개로 닫힌다 |
| 10-3 | `usage_refs`를 `JobExecution`에 둔다 | ADR §6 이관 목록의 `cost`를 금액이 아니라 `UsageRecord` 참조로 표현 | v4 §4-모듈2 ⑥과 `AnalysisRun` 계약 L36·L327이 「상세 ledger의 authoritative source는 `UsageRecord`」로 확정했다. 금액을 여기 복제하면 원천이 둘이 된다 |

## 11. 미결 — 이 계약에서 확정하지 않는다

- **소비자 확인:** §10의 추가 결정 전체와 domain PARTIAL → runtime status/produced 연결은 case·eval 확인 대기다. 이번 보정에서 새 매핑을 정하지 않는다.

- **retry 상한 · backoff 곡선 · lease 길이 · heartbeat 주기 · DB 구조** — Runtime 구현 세부다(ADR 부록-A §13-4). 구현 담당(정철원)이 정하고 계약을 바꾸지 않는다.
- **`STALE` 판정 임계값** — 몇 초 heartbeat 미수신을 STALE로 볼지는 위와 같은 구현 세부다. 계약은 「살아 있지 않다고 판정됨」이라는 의미만 고정한다.
- **`produced[]`의 구체 ref 타입 목록** — 각 생산자 계약이 소유한다. 본 계약은 opaque `ContractRef`로만 다룬다.
- **`failure_kind` 전체 값 목록** — 닫지 않는다. 모듈 접두어 규칙과 등재 위치만 고정한다.
