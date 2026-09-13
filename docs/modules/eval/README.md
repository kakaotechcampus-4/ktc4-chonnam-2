# eval

**Owner:** 김대원

이 폴더는 `eval` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 다루는 범위

- 정답지·manifest·locked test
- AI 단계 지표 계산
- baseline/challenger 동일 기준 비교
- 실험 실행·집계·리포트

## 다루지 않는 범위

- 제품 런타임 상태 관리
- search 내부 프롬프트/파서에 결합
- 사용자 인터뷰를 코드 평가와 동일시
- 자기 정답지를 구현 편의에 맞게 변경
이 폴더에는 `initial-evaluation-plan.md`와 `experiment-guide.md`가 초기 자료로 들어 있다. 실험 기록 템플릿은 `experiment-guide.md`의 「Experiment Note Template」 절에 있다.

## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
