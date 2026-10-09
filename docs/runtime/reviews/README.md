# Runtime Reviews

특정 시점의 Runtime/Ops 정합성 검수·review 결과를 보존한다.

> review 문서는 **Source of Truth가 아니다.** 특정 `develop` snapshot을 검수한 evidence이고, 결정은 담지 않는다. 결정과 규칙은 Final Contract · ADR · [`runtime-tech-spec.md`](../runtime-tech-spec.md) · [`ops-spec.md`](../ops-spec.md)에서 읽는다. 후속 수정으로 finding이 해소될 수 있으므로 review의 line 번호와 「현재」 표현은 문서 머리의 Audited SHA 기준으로만 읽는다.

## 다른 폴더와의 경계

| 폴더 | 담는 것 | SoT 여부 |
| --- | --- | --- |
| [`official-inputs/`](../official-inputs/README.md) | 카테캠 운영진이 준 외부 제약 사본 | 외부 입력. 결정 아님 |
| [`experiments/`](../experiments/README.md) | Runtime cross-cutting 실험 plan/result | 근거. 반복 가능한 결과만 Spec으로 승격 |
| `reviews/` | 특정 snapshot의 정합성 검수 결과 | evidence. 결정 아님 |
| Runtime Tech/Ops Spec · Contract · ADR | 실제 결정 | SoT |

review가 찾은 Open Decision 후보는 Decision 절차(`runtime-ops-workflow.md` §2)의 입력일 뿐이다. review 문서를 근거로 직접 규칙을 확정하지 않는다.

## 목록

| 문서 | Audited SHA | 날짜 | 범위 |
| --- | --- | --- | --- |
| [Runtime/Ops §0 정합성 검수](./runtime-ops-consistency-audit-2026-10-02.md) | `9c204ee` | 2026-10-02 | `runtime-ops-workflow.md` §0 — Runtime/Ops 문서 · 관련 Contract/ADR · 코드 · CI 현재 상태 |
