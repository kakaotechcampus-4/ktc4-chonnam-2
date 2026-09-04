# modules

각 모듈 Owner가 자기 영역의 조사·실험·결정·세부 spec을 성장시키는 작업공간이다.

## 공통 규칙

- 모듈 경계는 `architecture/module-architecture.md`를 따른다.
- Owner 배정은 `management/ownership.md`를 따른다.
- 다른 모듈의 규칙을 복사해 소유하지 않는다.
- `research/`는 근거, `experiments/`는 실행 기록, `decisions/`는 내부 결정이다.
- `spec.md`는 실제 조사·실험을 통해 필요해졌을 때 Owner가 만든다. 빈 spec을 미리 만들지 않는다.
- cross-module 계약은 합의 후 `architecture/contracts/`로 승격한다.
- 제품 범위를 바꾸는 결정은 module 내부 결정만으로 확정하지 않는다.
