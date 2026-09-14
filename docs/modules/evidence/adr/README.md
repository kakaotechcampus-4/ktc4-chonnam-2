# evidence 구현 ADR

이 폴더는 `evidence` 모듈 내부 구현 구조와 그 선택 이유를 기록한다.

- Final Data Contract나 다른 모듈의 Owner 경계를 변경하지 않는다.
- cross-module 계약 결정은 `docs/architecture/contracts/`가, evidence 정책 결정은 `../decisions/`가 우선한다.
- 미결 계약이나 정책을 구현 편의를 위해 확정하지 않는다.

## 목록

- [ADR-EVIDENCE-001 — Final Contract 기반 1차 Mock 통합 구현 구조](adr-first-mock-integration-implementation.md)
- [ADR-EVIDENCE-002 — 1차 완료 후 Owner 정책 결정 K1-K4](adr-first-completion-owner-decisions.md) — K1·K2·K3·K4 accepted
