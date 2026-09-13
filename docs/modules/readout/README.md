# readout

**Owner:** 신유민

이 폴더는 `readout` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 다루는 범위

- 대상차량 판독
- 번호판 Detection/Recognition/Best-Multi-frame/abstention
- 화면 timestamp OCR 판독

## 다루지 않는 범위

- 발생시각 최종 판정
- 긴 영상 사건 탐색
- 신고요건·기한
- 법적 신고유형 확정
## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
