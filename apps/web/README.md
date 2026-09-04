# web — 브라우저 작업공간 (자리만 잡아둔 폴더)

**Owner:** 신유민 (공동 개발: 김대원 — 후보 카드·타임라인·번호판 확대) · **경계:** `docs/architecture/module-architecture.md` §4-모듈6 · **문서 작업공간:** `docs/modules/web/`

## 지금 상태

**코드도 `package.json`도 없다.** 그래서 npm workspace(`apps/*`)에 잡히지 않는다. 다른 모듈과 대칭으로 자리를 잡아둔 것뿐이다.

## 이 폴더와 `apps/prototype/`의 관계

- `apps/prototype/`은 **흐름 프로토타입**이다(mock 데이터, 백엔드 없음). 제품 코드가 아니고, 손대지 않는다.
- 실제 web을 프로토타입을 확장해 만들지, 새로 만들지는 **Owner가 정한다** — 판단에 필요한 사실은 `apps/prototype/README.md`에 있다. 프레임워크도 미결이다(`docs/architecture/module-architecture.md` §10-3).
- **확장하기로 하면** 프로토타입 코드를 이 폴더로 옮기고 `apps/prototype/`은 아카이브한다. **새로 만들기로 하면** 여기서 시작하고 프로토타입은 참고 자료로 남긴다. 어느 쪽이든 「실제 앱」은 이 폴더 하나다.

## 지켜야 할 것 (원문은 §4-모듈6)

- **`web → case.get_view() → CaseView`** 가 유일한 read dependency다. `evidence`·`search`·`readout` 계약을 직접 읽지 않는다 (§2 원칙 7).
- candidate score threshold · OCR accept threshold · Timestamp 우선순위 · 신고 기한 · 첨부 제한 · Evidence sufficient 여부를 **화면이 계산하면 Architecture 위반**이다.
- 화면 흐름의 상위 문서는 `docs/product/core-user-flow.md`, 디자인 토큰의 정본은 `apps/prototype/src/styles/tokens.css`(`docs/design/DESIGN.md` 참조).
- Desktop Web 우선. 모바일 반응형은 MVP 제외 (§1-7 A1).
