# evidence 구현 ADR

이 폴더는 `evidence` Owner가 내린 결정과 그 이유를 기록한다. 내부 구현 구조(ADR-001), 모듈이 단독으로 정할 수 있는 정책(ADR-002), 그리고 `evidence`가 Contract Owner인 계약의 개정 결정(ADR-003)이 여기 들어간다.

- **다른 모듈의 Owner 경계는 바꾸지 않는다.** 다른 Owner의 입출력 계약이 걸리면 이 폴더에서 단독 확정하지 않고 해당 Owner와 별도로 검토한다.
- **계약·정책의 본문은 여기가 아니다.** 규범 원문은 `docs/architecture/contracts/`와 `../decisions/`가 소유하고, 이 폴더는 왜 그렇게 정했는지를 남긴다. 둘이 어긋나면 원문이 이긴다.
- 미결 계약이나 정책을 구현 편의를 위해 확정하지 않는다.

## 목록

- [ADR-EVIDENCE-001 — Final Contract 기반 1차 Mock 통합 구현 구조](adr-first-mock-integration-implementation.md)
- [ADR-EVIDENCE-002 — 1차 완료 후 Owner 정책 결정 K1-K4](adr-first-completion-owner-decisions.md) — K1·K2·K3·K4 accepted
- [ADR-EVIDENCE-003 — 위치를 확보하지 못한 사건의 `ReportPackage` 발행 (D1)](adr-location-absent-package.md) — accepted. 이슈 #48 종결, ADR-002 §5.6·§5.8·§5.11·§5.14 갱신
