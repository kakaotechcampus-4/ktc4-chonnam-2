# management

역할, 프로젝트 운영, 회의 의사결정, 배포 전 cross-cutting review를 관리한다.

## 이 폴더에 들어갈 authoritative 문서

- [역할 배정과 초기 계획 이력](ownership.md) — 모듈·계약 소유, 구현 담당, PM 승인과 공통 검수 역할
- `project-operating-plan.md` — 1.3에서 옮긴 운영 원칙과 주간 리듬. 실제 일정은 팀 Notion
- [11/5 RC 결정](rc-scope-2026-11-05.md) — 당시 포함·제외·차단·조건부 수용과 동결 판정. 현재 상태는 아래 후속 근거에서 확인한다.
- `pre-deploy-security-review.md` — 배포 전 보안·개인정보 검수표 (담당 Owner · 확인일 · PASS/WARN/BLOCK)
- `tool-trajectory-review.md` — 결과가 아니라 **경로**가 맞았는지 판정하는 절차 (목데이터 통합 1회 + 데모 직전 1회)
- `cross-cutting-decisions.md` — 모듈 경계 밖 운영 책임 11건의 결정 기록
- [`environment-and-deployment-config.md`](environment-and-deployment-config.md) — 로컬·AWS 실행/배포 설정 이름, GitHub Secrets/Variables, host·policy 구조, Recording baseline v1. 공개 가능한 명세만 두고 실제 팀 값·Secret 위치는 팀 Notion

11/5 RC 판정 이후 #583의 후보 썸네일은 [이전 AWS에서 검증](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/523#issuecomment-6719540476)했고, 별도 기능인 후보 영상 재생은 [최종 공개본에서 개별 재생을 검증](../runtime/candidate-video-preview.md)했다. 당시 RC에서 제외한 상황 정정(#545)은 이후 #621에 구현됐고 [로컬 실영상 통합 테스트](../modules/case/experiments/real-e2e-20261108-597-integrated.md#3-2-유형-정정--pass)에서 확인했다. 최종 AWS의 실제 입력·운영값과 E2E 범위는 [11/10 공개 인계](../runtime/a1-public-readiness.md#2026-11-10-최종-aws-공개-배포)에서 확인한다.

## 회의 안건지의 수명

모듈 R&R만으로 닫히지 않는 항목은 회의 안건지로 만들어 결정하고, 결정된 내용은 `ownership.md`·`module-architecture.md`·각 module `decisions/`·product 문서 등 알맞은 authoritative 문서로 다시 반영한다. **안건지 자체를 영구 Source of Truth로 쓰지 않는다.** 결정이 끝난 안건지는 `docs/archive/management/`로 옮긴다.

## 이 폴더에 두지 않는 것

- 팀원 평가·부하 판단·공개 전 검수 메모 — PM 내부 문서는 gitignore된 `secret/`에 둔다. 공유가 필요하면 공개 가능한 형태로 다시 써서 여기 둔다.
- 외부 제출용 사본 — `submissions/`(gitignore). 원본은 항상 `docs/`다.
