# web

실행·검사·폴더 구성은 [웹 앱 README](../../../apps/web/README.md)를 본다.

## 화면 목록

| 화면 | 파일·역할 |
| --- | --- |
| 업로드 | `UploadScreen.tsx` — 영상과 기억 단서 입력 |
| 진행 | `FlowScreen.tsx` — 분석 단계 표시 |
| 후보 | `CandidatesScreen.tsx` — 후보 비교·선택 |
| 결과 | `ResultScreen.tsx` — 판단 확인·신고자료 준비 |
| 근거 | `EvidenceScreen.tsx` — 장면 근거 확인 |
| 후보 없음 | `NoResultScreen.tsx` — 탐색 결과가 없는 경우 |
| 미관찰 | `NotObservedScreen.tsx` — 고른 후보에서 위반 미관찰 |
| 실패 | `FailedScreen.tsx` — 분석 실패 안내 |
| 중단 | `StoppedScreen.tsx` — 사용자가 중단한 흐름 |
| 전달 | `HandoffScreen.tsx` — 다음 사용자 단계 안내 |
| 하위 화면 | `SubScreens.tsx` — 후보·번호판·시간 확인 |
| 공식 샘플 | `OfficialSampleEntry.tsx` — 실제 API 샘플 체험 |
| 흐름 연결 | `ApiFlow.tsx`, `DemoFlow.tsx`, `CaseScreen.tsx` — 실제·시연·개발 화면 |

화면 동작의 세부 근거는 [결정 문서](decisions/README.md), [UX 문서](ux/README.md), [실험·접근성 점검](experiments/README.md), [계약 문서](contracts/README.md)에 있다.

**Owner:** 신유민 (공동 개발: 김대원)

이 폴더는 `web` 모듈의 세부 문서 작업공간이다. authoritative 경계는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 다루는 범위

- 단계형 작업공간 화면 — `CaseView` 표현. 자연어 입력은 기억 단서 1곳(`core-user-flow.md` §2)
- Candidate Cards·타임라인·영상 UI
- Evidence Review·번호판 확대·실패 상태 표현
- 실제 화면 — 업로드(`UploadScreen`), 진행(`FlowScreen`), 결과·신고자료(`ResultScreen`), 공식 샘플(`OfficialSampleEntry`), 대기 중 주행 게임(`components/driving/`)

## 다루지 않는 범위

- 파일 경계 계산
- AI/Rule의 제품 책임을 화면 코드에 복제
- 시각·번호판·신고요건의 최종 판정

제품 수준 데모 흐름은 `docs/product/core-user-flow.md`가 소유하며, 이 폴더는 실제 UI 상세를 소유한다.

## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `docs/architecture/contracts/`로 승격

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.
