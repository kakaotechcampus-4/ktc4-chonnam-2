# web — 브라우저 앱

**Owner:** 신유민 (공동 개발: 김대원 — 후보 카드·타임라인·번호판 확대) · **경계:** `docs/architecture/module-architecture.md` §4-모듈6 · **문서 작업공간:** `docs/modules/web/`

## 지금 상태

React 19/Vite 6 제품 앱이다. 루트 npm workspace에서 설치·빌드·테스트한다(`README.md`의 실행 방법). 분석을 기다리는 동안 사용자가 주행 게임을 선택하면 Three.js 0.160.1을 지연 로딩한다. 게임은 분석 상태를 읽거나 바꾸지 않는다. 빌드할 때 `VITE_DRIVING_GAME=off`를 주면 게임을 끈다.

## 이 폴더와 `apps/prototype/`의 관계

- `apps/prototype/`은 **흐름 프로토타입**이다(mock 데이터, 백엔드 없음). 제품 코드가 아니고, 손대지 않는다.
- 실제 제품 화면과 API 연결은 이 폴더에 있고, `apps/prototype/`은 별도의 목데이터 시연 앱이다.

## 지켜야 할 것 (원문은 §4-모듈6)

- **`web → case.get_view() → CaseView`** 가 유일한 read dependency다. `evidence`·`search`·`readout` 계약을 직접 읽지 않는다 (§2 원칙 7).
- candidate score threshold · OCR accept threshold · Timestamp 우선순위 · 신고 기한 · 첨부 제한 · Evidence sufficient 여부를 **화면이 계산하면 Architecture 위반**이다.
- 화면 흐름의 상위 문서는 `docs/product/core-user-flow.md`, 디자인 토큰의 정본은 `apps/prototype/src/styles/tokens.css`(`docs/design/DESIGN.md` 참조).
- Desktop Web 우선. 모바일 반응형은 MVP 제외 (§1-7 A1).
