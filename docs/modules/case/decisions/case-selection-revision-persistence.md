# Case 내부 `selection_rev` 저장 설계 — 단일 현재값, 별도 이력 테이블 없음

> 결정일 2026-09-13 · 담당 유소연(`case`) · 근거 `docs/architecture/erd-draft.md`(`codex/erd`, 미머지) 리뷰 항목 ①

## 배경

`codex/erd` 브랜치의 논리 ERD 초안이 `cases` 엔티티에 `selection_rev`를 확정 컬럼처럼 그렸으나, 같은 문서 §5.2는 "Selection 및 Case 변경 이력"을 "미정 — case 내부 현재 포인터·이력 구조 검토"로 남겨뒀다. 도표와 본문이 서로 어긋나 있어 case Owner로서 내부 저장 설계를 확정한다.

## 결정된 것

**`selection_rev`는 `Case` aggregate 내부의 단일 현재값 필드로 둔다. 별도 "선택 이력" 테이블은 만들지 않는다.**

- `case_rev`와 마찬가지로 후보 선택 시점에 함께 증가시킨다(`module-architecture.md` "[case] selection_rev + case_rev" 흐름과 일치).
- `CaseView`에는 노출하지 않는다 — 지금까지 web(신유민)·eval(김대원) 어느 쪽도 이 값의 외부 노출을 요청한 적이 없고, `contract-job-record-case-view.md`의 현재 CaseView 스키마도 `selection_rev`를 포함하지 않는다.
- 과거 선택 맥락이 필요하면 이미 존재하는 구조로 재구성한다: `CorrectionRecord`/`EvidenceRecord`가 생성 시점의 `selection_rev`를 immutable snapshot으로 갖고 있고(`contract-correction-record.md` §6, `contract-evidence-record-needs.md`), `supersedes_id` 체인으로 과거 값까지 추적 가능하다. `JobRecord` 자체도 append-only로 `case_rev`별 요청 이력을 이미 남긴다. 이 둘로 "사건 단위 학습 이력"(`docs/modules/case/decisions/correction-log-reuse.md`) 목적은 충분히 커버되므로 별도 이력 구조를 새로 만들 필요가 없다고 판단한다.

## 소유 경계

내부 저장 구조 결정은 case 단독 권한이다 — `CaseView`가 이 필드를 외부에 노출한 적이 없으므로 다른 모듈 계약에 영향을 주지 않는다.

## 관련

- `docs/architecture/module-architecture.md` "[case] selection_rev + case_rev" 흐름
- `contract-correction-record.md` §6 `selection_rev` 필드 정의
- `docs/modules/case/decisions/correction-log-reuse.md`
