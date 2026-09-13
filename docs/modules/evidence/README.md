# evidence

**Owner:** 김준영

이 폴더는 `evidence` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 다루는 범위

- 관찰값을 확정 Evidence로 승격
- 발생시각 최종 판정
- 부족분(EvidenceNeeds)
- 신고요건/기한/용량/유형 매핑
- 신고문·Package·handoff

## 다루지 않는 범위

- AI 모델·프롬프트
- OCR 라이브러리
- 영상 코덱/ffmpeg 내부 처리
- 대화 진행 단계·작업 발주
## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
