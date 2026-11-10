# web

**Owner:** 신유민 (공동 개발: 김대원)

이 폴더는 `web` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 한눈에

- **하는 일:** 영상 업로드 → 장면 찾기 진행 → 후보 확인 → 번호판·발생 시각 확인 → 신고 문구 복사와 신고용 영상 다운로드. 제출은 사용자가 안전신문고에서 직접 한다.
- **입출력:** 입력은 HTTP API `/cases/*`가 주는 `CaseView`(`/public/*` 공식 샘플 포함), 출력은 사용자 화면과 `/commands` 요청이다.
- **코드:** [`apps/web/`](../../../apps/web/) — 실행 방법과 URL 진입은 [`apps/web/README.md`](../../../apps/web/README.md)
- **테스트:** 루트에서 `npm run test:web` (e2e는 `npm run test:e2e --workspace=daesingo-web`)

## 다루는 범위

- 단계형 작업공간 화면 — `CaseView` 표현. 자연어 입력은 기억 단서 1곳(`core-user-flow.md` §2)
- Candidate Cards·타임라인·영상 UI
- Evidence Review·번호판 확대·실패 상태 표현
- 실제 화면 — 업로드(`UploadScreen`), 진행(`FlowScreen`), 결과·신고자료(`ResultScreen`), 공식 샘플(`OfficialSampleEntry`), 대기 중 주행 게임(`components/driving/`)

## 다루지 않는 범위

- 파일 경계 계산
- AI/Rule의 제품 책임을 화면 코드에 복제
- 시각·번호판·신고요건의 최종 판정

제품 수준 데모 흐름은 `product/core-user-flow.md`가 소유하며, 이 폴더는 실제 UI 상세를 소유한다.

## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
