# management

역할, 프로젝트 운영, 회의 의사결정, 배포 전 cross-cutting review를 관리한다.

## 이 폴더에 들어갈 authoritative 문서

- `ownership.md` — 현재 역할 배정안 (모듈 Owner + 운영 역할)
- `project-operating-plan.md` — 1.3에서 옮긴 운영 원칙과 주간 리듬. 실제 일정은 팀 Notion
- `pre-deploy-security-review.md` — 배포 전 보안·개인정보 검수표 (담당 Owner · 확인일 · PASS/WARN/BLOCK)
- `tool-trajectory-review.md` — 결과가 아니라 **경로**가 맞았는지 판정하는 절차 (목데이터 통합 1회 + 데모 직전 1회)
- `cross-cutting-decisions.md` — 모듈 경계 밖 운영 책임 11건의 결정 기록

## 회의 안건지의 수명

모듈 R&R만으로 닫히지 않는 항목은 회의 안건지로 만들어 결정하고, 결정된 내용은 `ownership.md`·`module-architecture.md`·각 module `decisions/`·product 문서 등 알맞은 authoritative 문서로 다시 반영한다. **안건지 자체를 영구 Source of Truth로 쓰지 않는다.** 결정이 끝난 안건지는 `docs/archive/management/`로 옮긴다.

## 이 폴더에 두지 않는 것

- 팀원 평가·부하 판단·공개 전 검수 메모 — PM 내부 문서는 gitignore된 `secret/`에 둔다. 공유가 필요하면 공개 가능한 형태로 다시 써서 여기 둔다.
- 외부 제출용 사본 — `submissions/`(gitignore). 원본은 항상 `docs/`다.
