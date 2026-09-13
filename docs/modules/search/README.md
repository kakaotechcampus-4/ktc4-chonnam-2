# search

**Owner:** 서어진

이 폴더는 `search` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 다루는 범위

- 장시간 영상 Candidate Generation
- Fine visual evidence verification
- 탐색 모델·프롬프트·Reference 실험
- search 내부 failure 분석

## 다루지 않는 범위

- 번호판 OCR 확정
- 신고요건/신고유형 규칙
- 파일 경계 계산
- 평가 정답지를 search 내부에 종속시키기
## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
