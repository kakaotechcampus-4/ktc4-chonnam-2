# architecture

프로젝트 전체의 **모듈 경계, 의존성 방향, 공통 불변식, cross-module 계약 원칙**을 관리한다.

이 폴더의 authoritative 문서는 `module-architecture.md`다.

## 넣는 것

- 모듈을 왜 이렇게 나눴는지
- 각 모듈이 알고/모르는 것
- 공통 데이터 계약
- 모듈 간 의존성 및 안전 경계

## 넣지 않는 것

- 개별 모듈의 기술 조사·실험 → `modules/<module>/`
- 제품 가설·사용자 흐름 → `product/`
- 담당자·일정 → `management/`

`module-architecture.md`를 요약한 별도 중앙 문서를 만들지 않는다.
