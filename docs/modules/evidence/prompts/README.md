# evidence/prompts

이 모듈의 작업을 AI 에이전트나 다른 담당자에게 발주·handoff할 때 그대로 전달하는 지시 문서를 둔다. 대화에서 즉석으로 쓰고 버리는 프롬프트가 아니라, 전달 이력이 남아야 하는 작업 지시만 여기에 보존한다.

## 사용 규칙

- 한 파일은 한 번의 발주다. 수신자(모델·사람), 목표, 범위 밖, 완료 기준을 파일 안에서 명시한다.
- 규칙 원문을 복제하지 않는다. 체크리스트·계약·결정 문서를 링크로 가리킨다. 여기의 프롬프트는 어느 문서를 기준으로 삼을지 지정할 뿐 기준 자체를 소유하지 않는다.
- 프롬프트에 박아 둔 저장소 상태(브랜치·커밋·파일 수)는 작성 시점 스냅샷이다. 재사용할 때는 현재 상태를 다시 확인한다.
- 실행 결과·검수 기록은 여기 쓰지 않는다. 검수 보고서는 `../reviews/`, 확정된 내부 결정은 `../decisions/`가 소유한다.
- evidence 밖 모듈에 보낼 프롬프트는 그 모듈 Owner의 폴더에서 관리한다.

## 현재 프롬프트

- `implementation-prompt-gpt-5.6-sol.md` — GPT-5.6 Sol에게 보내는 김준영 evidence 1차 구현 발주. 완료 기준은 `../first-completion-checklist.md`이며, common/runtime 구현은 범위에서 제외한다.
- `implementation-prompt-adr-002-k1-k4.md` — 1차 완료 이후 확정한 Owner 결정 **K1~K4와 D1**을 코드·정책 데이터·계약·테스트·Artifact에 반영하는 발주. 기준은 `../adr/adr-first-completion-owner-decisions.md`(K1~K4)와 `../adr/adr-location-absent-package.md`(D1, 2026-09-14 추가 — 작업 항목 W10~W12)이며, 통합 항목 I1~I11은 범위에서 제외한다. 파일명은 최초 발주 시점 이름을 유지한다.
