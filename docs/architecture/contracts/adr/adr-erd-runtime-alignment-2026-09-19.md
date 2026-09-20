# ADR: Logical ERD ↔ Runtime 문서 정합화 기준 — 2026-09-19

**Status:** Accepted  
**Decider:** 김준영 (PM · 문서 일관성 B-4 · common/runtime Owner)  
**Date:** 2026-09-19  
**Scope:** `docs/architecture/erd-draft.md` · `docs/runtime/*` · Runtime 관련 Final Data Contract 접합

---

## 1. Context

`docs/architecture/erd-draft.md`는 PR #42를 거쳐 evidence·case·recording·readout·search의 검토 결과를 모은 **cross-domain 논리 ERD**다.

별도로 Runtime/Ops 설계는 백엔드 3인이 함께 검토한 Working 문서를 바탕으로 2026-09-19 Git 문서로 분리했다.

```text
docs/runtime/README.md
docs/runtime/runtime-tech-spec.md
docs/runtime/ops-spec.md
```

분리 과정에서 Final Data Contract와 실제 repository 상태는 확인했지만, Logical ERD를 명시적인 입력으로 대조하지 않았다. 그 결과 두 검토 문서 사이에 다음 종류의 drift가 발견됐다.

1. ERD가 당시 미결로 남긴 항목이 이후 Final Contract에서 이미 확정됨
2. Runtime Tech Spec이 논리 결정은 맞지만 물리 persistence 시점까지 과하게 확정해 표현함
3. Final Contract의 논리 필드는 확정됐지만 ERD/Runtime 모두 물리 저장 방식을 열어둔 항목이 존재함
4. 이미 merge된 후속 수정이 ERD의 "확인 필요" 상태로 남아 있음

이 ADR은 새 domain 의미를 설계하지 않는다. **이미 수락된 결정의 우선순위를 적용해 stale 문구를 정리하고, 양쪽 모두 미결인 물리 구현은 미결로 유지하는 기준**을 기록한다.

---

## 2. Decision 1 — 충돌 해결 우선순위

ERD와 Runtime 문서가 다른 말을 할 때 다음 순서로 판정한다.

```text
Product Policy
→ Module Architecture
→ Final Data Contract / Accepted Owner Decision · ADR
→ Logical ERD
→ Runtime Tech / Ops implementation spec
→ Code / migration
```

해석 원칙:

1. Final Data Contract나 해당 domain Owner의 Accepted Decision에서 이미 닫힌 항목은 그 결정을 따른다.
2. Logical ERD는 cross-domain 관계, cardinality, 독립 identity, 저장 후보를 통합해 보여준다.
3. Runtime Tech Spec은 상위 문서가 열어둔 **실행·persistence의 물리 구현**을 닫는다.
4. Ops Spec은 배포·관찰·복구·capacity를 소유하며 logical data model을 재정의하지 않는다.
5. 양쪽 모두 미결이면 문서 완성도를 위해 임의 확정하지 않고 Pending으로 유지한다.
6. Research/experiment는 결정의 근거이지 그 자체가 SoT는 아니다.

Logical ERD가 Final Contract와 충돌하면 ERD를 수정한다. Runtime 구현이 ERD보다 구체적일 수는 있지만, 상위 논리 의미를 바꾸려면 해당 Owner 결정이 먼저 필요하다.

---

## 3. Decision 2 — Logical ERD의 유지 책임

Logical ERD는 특정 한 domain의 문서가 아니라 전체 데이터 모델을 가로지르는 통합 문서다.

따라서 유지 구조를 다음처럼 해석한다.

```text
ERD 문서 유지·정합화
→ 김준영 (PM · 문서 일관성 / architecture integration)

각 domain의 데이터 의미·cardinality 변경
→ 해당 Domain Owner

common/runtime 계약·논리 실행 의미
→ 김준영

Runtime 물리 구현
→ 정철원 구현 + common/runtime 결정
```

초안 작성자가 문서 전체의 영구 Owner가 되는 것으로 해석하지 않는다.

김준영은 다음 조건을 만족하면 추가 Owner 승인 없이 ERD의 stale 표현을 수정할 수 있다.

- 이미 Final Contract / Accepted ADR / Owner 결정에서 정답이 유일하게 정해짐
- domain 의미·enum·cardinality를 새로 바꾸지 않음
- 미결을 임의로 확정하지 않음

반대로 기존 상위 결정이 없는 새 의미 변경은 해당 Domain Owner 확인을 받아야 한다.

Logical ERD는 전체 domain 관계를 포함하므로 `docs/architecture/`에 유지한다. `docs/runtime/`으로 이동하지 않는다.

---

## 4. Decision 3 — 같은 kind의 여러 Job 대표 규칙

ERD에는 다음 항목이 후속 합의로 남아 있었다.

> 같은 kind에 여러 job_id가 있을 때 progress 한 줄이 무엇을 대표하는가

하지만 현재 Final JobRecord/CaseView Contract A절 §10-7에서 이미 결정됐다.

```text
같은 job_id 내부
→ attempt 최댓값의 JobExecution이 대표 execution

같은 kind에 여러 job_id
→ requested_at이 가장 늦은 JobRecord가 대표 job
```

`case_rev`는 발주 순서 정렬 키가 아니다.

따라서 이 항목은 더 이상 Pending이 아니며 ERD를 Final Contract에 맞춰 갱신한다.

이 결정은 Runtime이 새로 만든 정책이 아니라 **case/web Final Contract의 projection 규칙을 Runtime 문서가 참조하는 것**이다.

---

## 5. Decision 4 — UsageRecord의 "기록 대상"과 persistence 시점을 분리

Final UsageRecord Contract가 확정한 것은 다음이다.

```text
실제 capability/provider invocation이 시작됨
→ 해당 호출은 UsageRecord 기록 대상

dispatch 전에 종료
→ UsageRecord 없음
```

ERD는 여기에 중요한 구현 구분을 추가로 기록하고 있다.

호출이 시작되는 순간에는 token/cost/latency/실패 정보가 아직 완성되지 않을 수 있으므로,

```text
invocation 시작
→ 기록 의무/대상 확정

관측 가능한 사용량·결과·실패 정보 확보
→ append-only UsageRecord 기록
```

으로 해석한다.

다음은 아직 Runtime 물리 구현 결정이다.

- 호출 시작 순간 incomplete row를 INSERT할지 여부
- 최종 append 시점
- worker 소멸 시 in-flight invocation 복구
- 중복 append 방지/idempotency

따라서 Runtime Tech Spec의 기존 `invocation 시작 → UsageRecord append` 표현을 완화한다.

---

## 6. Decision 5 — JobExecution.produced의 논리 필드와 물리 저장을 구분

Final JobExecution Contract의 다음 필드는 이미 확정이다.

```text
produced: ContractRef[]
```

미결인 것은 **MySQL에서 그 논리 필드를 어떻게 저장하느냐**다.

현재 후보:

```text
A. job_executions.produced JSON
B. job_execution_products(execution_id, kind, ref) 관계 테이블
```

따라서 ERD에서는 "필드 자체가 미정"처럼 읽히지 않도록 다음처럼 표현한다.

> 논리 Contract 확정 / 물리 저장 미정

Runtime Tech Spec의 Open Decision에도 동일 선택지를 남긴다.

---

## 7. Decision 6 — JobExecution.usage_refs의 논리 필드와 물리 materialization을 구분

Final JobExecution Contract에는 다음 필드가 존재한다.

```text
usage_refs: ID[]
```

동시에 UsageRecord는 `execution_ref`를 갖는다.

따라서 논리 serialization에서 `usage_refs`가 존재하는 것은 확정이지만, DB에서 이를 별도 저장할지

```text
UsageRecord.execution_ref
→ JobExecution.usage_refs projection
```

으로 재구성할지는 미결이다.

이 선택 역시 Runtime 구현 시 닫는다. 두 방향을 서로 독립 authoritative 원장으로 이중 관리하지 않는다.

---

## 8. Decision 7 — 이미 닫힌 ERD 후속 확인을 종료

### PR #46

ERD가 "병합 여부 미확인"으로 남긴 case 재개 결정 PR #46은 이미 develop에 merge됐다.

따라서:

- 재개 = 새 `job_id`
- 자동 infra retry = same `job_id` + new `execution_id` + attempt 증가

는 확정 상태로 표시한다.

### VisualEvidence Fine input

ERD가 확인 대기로 남긴 VisualEvidence 예시도 현재 Final Contract에서 다음으로 수정 완료됐다.

```text
VISUAL_VERIFY AnalysisRun.input_ref
=
VisualEvidence.input_ref
=
AnalysisSource
```

옛 `incident_clip` 예시는 제거됐다. 해당 후속 확인을 ERD에서 닫는다.

---

## 9. Consequences

### ERD

- 수정일과 정합화 기준 갱신
- ERD maintainer / Domain Owner 경계 명시
- same-kind 대표 Job Pending 제거
- PR #46 확인 대기 제거
- VisualEvidence 예시 병합 확인 대기 제거
- `JobExecution.produced`를 "논리 확정 / 물리 미정"으로 표현
- `JobExecution.usage_refs`를 "논리 확정 / materialization 미정"으로 표현
- 진짜 미결 항목만 유지

### Runtime Tech Spec

- Logical ERD를 명시적 설계 입력으로 추가
- same-kind 대표 Job 규칙을 Final Contract 출처와 함께 정확히 표기
- UsageRecord 기록 대상과 persistence 시점을 분리
- `produced` 저장 방식과 `usage_refs` materialization을 Open Decision에 추가

### Runtime Ops Spec

- Logical ERD가 logical data model의 입력임을 링크
- Ops가 schema/cardinality를 재정의하지 않는다는 경계만 명시

---

## 10. Non-decisions

이 ADR은 다음을 정하지 않는다.

- 별도 `runtime/runtime-db-schema.md` 생성 — 후속 고려
- Runtime Queue의 실제 table 수·이름
- MySQL column type / length / precision
- 실제 FK 생성 여부와 ON DELETE
- index 설계
- `produced` JSON vs 관계 테이블 선택
- `usage_refs` materialized column vs projection 선택
- UsageRecord final append timing
- retry max / backoff / jitter
- lease / heartbeat / STALE threshold

이 항목은 구현 시점의 실제 요구와 integration test를 근거로 닫는다.

---

## References

- `docs/architecture/erd-draft.md`
- `docs/architecture/contracts/contract-job-record-case-view.md`
- `docs/architecture/contracts/contract-job-execution.md`
- `docs/architecture/contracts/contract-usage-record.md`
- `docs/architecture/contracts/contract-visual-evidence.md`
- `docs/runtime/runtime-tech-spec.md`
- `docs/runtime/ops-spec.md`
- `docs/management/ownership.md`
