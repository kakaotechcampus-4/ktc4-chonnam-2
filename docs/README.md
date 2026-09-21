# 대신고 docs 운영 규칙

> 이 README는 프로젝트 요약이나 Source of Truth가 아니다. 문서 폴더의 사용 규칙만 설명한다.

## 기본 원칙

- 작업에 필요한 문서만 읽는다. `docs/README.md` 하나로 프로젝트 전체를 대신 설명하지 않는다.
- 제품의 사용자 약속과 범위는 `product/`에서 관리한다.
- 전체 모듈 경계와 계약 원칙은 `architecture/`에서 관리한다.
- 전체 logical data model은 `architecture/erd-draft.md`에서 통합한다. Final Contract나 Accepted Owner Decision과 충돌하면 상위 결정을 따른다.
- 공통 실행 인프라의 물리 구현과 운영 기준은 `runtime/`에서 관리한다. `common/runtime`은 여덟 번째 도메인 모듈이 아니다.
- 모듈 내부 조사·실험·결정은 `modules/<module>/`에서 해당 Owner가 관리한다.
- 프로젝트 운영·역할·회의 안건은 `management/`에서 관리한다.
- 과거 제출물과 발표자료는 `archive/`에 보관하고 living document의 근거로 직접 사용하지 않는다.
- Research는 근거이지 결정이 아니다. 조사 결과가 결정으로 바뀌면 해당 모듈의 `decisions/` 또는 합의된 상위 문서에 반영한다.
- 빈 문서를 채우기 위해 새로운 결정을 만들지 않는다. 미결은 미결로 남긴다.
- 다른 모듈의 규칙을 자기 문서에 복제하지 않는다.

## 어떤 작업이면 어느 문서를 읽나

전체를 읽지 않는다. 아래 표에서 자기 작업에 해당하는 문서만 연다. 루트 `CLAUDE.md`는 이 표를 가리키는 얇은 포인터다.

| 하려는 일 | 읽을 문서 | 읽지 않아도 되는 것 |
| --- | --- | --- |
| 제품이 무엇을 약속하고 무엇을 안 하는지 | `product/product-spec.md` (§5 Must/Won't · §7 불변 경계) | 나머지 product 문서 |
| 화면 흐름·실패 UX·어떤 화면이 있는지 | `product/core-user-flow.md` | `design/` (화면 상세는 그쪽) |
| 내 모듈의 경계·계약·금지사항 | `architecture/module-architecture.md` §1 → §2 → **§4 내 모듈** → §5 → §11 내 항목 | 다른 모듈의 §4 |
| 내 모듈의 조사·실험·결정 | `modules/<module>/` (`research/` `experiments/` `decisions/` `contracts/`) | 다른 모듈의 폴더 |
| 전체 데이터 관계·cardinality·저장 후보를 볼 때 | `architecture/erd-draft.md` (Logical ERD) | Runtime의 실제 queue/index/FK 세부 |
| DB Queue · claim · retry · lease/heartbeat · JobExecution/Usage persistence를 구현할 때 | `runtime/runtime-tech-spec.md` + 관련 Final Contract + Logical ERD | `runtime/ops-spec.md`의 배포 운영 상세 |
| 배포 · logging · monitoring · health · storage/retention · capacity · CI/CD를 다룰 때 | `runtime/ops-spec.md` | domain 알고리즘·품질 threshold |
| 누가 무엇을 맡는지 | `management/ownership.md` | — |
| 모듈 경계 밖 운영 결정(승인 경로·리뷰 담당) | `management/cross-cutting-decisions.md` | `archive/management/`의 안건지 |
| 배포 전 점검 | `management/pre-deploy-security-review.md` · `management/tool-trajectory-review.md` | — |
| 계약이 지금 어디까지 합의됐는지 | **현재 상태:** `architecture/contracts/README.md` + 해당 `contract-*.md` · **역사적 종결 근거:** `architecture/contracts/adr/adr-data-contract-call-closure-2026-09-08.md` §9·§10.2 → 09-07 회차 → 09-06 보정/감사 | 2026-09-19 현재 canonical 계약 16건 모두 `Final — Accepted`. 과거 closure ADR의 Pending 표는 당시 snapshot이며 이후 변경은 현재 Contract/모듈 문서를 따른다 |
| 평가 지표·실험 기록 방법 | `modules/eval/metrics/metric-definitions.md`(확정 지표의 계산 정의) · `modules/eval/initial-evaluation-plan.md` · `modules/eval/experiment-guide.md` | — |
| 과거 제출물·발표 맥락 | `archive/` — **현재 문서가 아니다** | — |

## 문서가 서로 다른 말을 할 때

다음 순서로 판정한다.

```text
Product Policy
→ Module Architecture
→ Final Data Contract / Accepted Owner Decision · ADR
→ Logical ERD
→ Runtime Tech / Ops implementation spec
→ Code / migration
```

세부 원칙:

1. 제품의 사용자 약속·범위는 `product/product-spec.md`가 기준이다.
2. 전체 모듈 경계·의존 방향은 `architecture/module-architecture.md`가 기준이다.
3. schema·enum·불변조건처럼 Final Data Contract에서 이미 닫힌 항목은 Final Contract가 기준이다.
4. 해당 Domain Owner의 Accepted Decision/ADR에서 이미 닫힌 항목은 Logical ERD나 Runtime 문서가 다시 결정하지 않는다.
5. `architecture/erd-draft.md`는 cross-domain 논리 관계·cardinality·저장 후보를 통합한다. 상위 결정과 충돌하면 ERD를 정합화한다.
6. `runtime/`은 상위 문서가 열어둔 DB Queue·persistence·배포 운영의 물리 세부를 구현 근거와 함께 닫는다.
7. Research/experiment는 결정의 근거이지 단독 Source of Truth가 아니다.
8. 상위 문서끼리 실제 정책 충돌이 있고 어느 쪽도 우선하지 않으면 임의 보정하지 않고 해당 Owner/주간 회의에서 결정한다.

ERD ↔ Runtime 정합화의 상세 근거는 `architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md`를 따른다.

## 이번 Migration 규칙

이 폴더의 초기 living document는 `전남대학교 2팀 서비스 기획안 제출 1.3`에서 추출·중복 제거한 내용만 사용했다.

- 1.3에 없는 내용을 완성도를 위해 증폭하지 않았다.
- 모듈 구조 설계와 역할 배정안에 이미 흡수된 기술 상세는 다시 복제하지 않았다.
- 모듈별 `spec.md`는 미리 만들지 않았다. 각 Owner가 조사·실험 후 실제로 필요할 때 생성한다.
- 1.3 원본은 `archive/ktc/service-plan-1.3.md`, 모듈 구조 설계는 `architecture/module-architecture.md`, 역할 배정안은 `management/ownership.md`에 있다.
