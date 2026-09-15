# prototype

핵심 사용자 흐름을 화면으로 확인하기 위한 **흐름 프로토타입**이다. 제품 코드가 아니다.

## 무엇인가

- 10개 화면과 그 사이 전환을 실제로 눌러볼 수 있게 만든 것
- 데이터는 전부 mock (`src/mock/`). 백엔드·영상 파이프라인·AI 호출이 없다
- 상태는 단일 reducer (`src/machine.ts`) 하나로만 움직인다
- `ScenarioBar` 데모 컨트롤로 결과 없음·검색 실패·범위 확장 같은 분기를 실제 데이터 없이 이동할 수 있다

## 무엇이 아닌가

- 실제 웹 앱이 아니다. 인증·영속성·에러 복구·성능 고려가 없다
- 접근성은 프로토타입 수준까지만 봤다
- mock 값은 예시다. 차량번호 `12가 3456` 같은 것은 자리표시자다

## 근거 문서

이 코드의 좌표·문구·색상은 추측이 아니라 아래 문서에서 옮긴 것이다. 소스 주석이 파일명과 행 번호로 인용한다.

| 문서 | 소유 범위 |
|---|---|
| `docs/design/DESIGN-stage1-mockups.html` | 실제 목업. 좌표·간격·클래스명의 출처 |
| `docs/design/DESIGN.md` | 디자인 토큰, Mono-Is-Evidence 등 규칙 |
| `docs/design/PROTOTYPE-SPEC.md` | 화면별 동작 명세, mock 데이터 |
| `docs/product/core-user-flow.md` | 제품 수준 흐름 (이쪽이 상위) |

## 실행

```bash
npm install          # 저장소 루트에서 한 번
npm run dev:prototype
```

## 이 코드를 실제 앱의 출발점으로 쓸 것인가 — 결정됨

**표현 레이어는 승계하고 상태 레이어는 새로 짓는다.** 실제 앱은 `apps/web`이며, 이 프로토타입에서 토큰(`styles/tokens.css`)·표현 컴포넌트·화면 구조를 가져가고 `machine.ts`·`types.ts`·`mock/*`는 가져가지 않는다. 화면이 값을 스스로 판정하는 코드(hint 정규식 파싱·진행 게이트 계산·범위 확장 계산)가 거기 있고, 그것이 `CaseView` 계약과 충돌하기 때문이다.

근거와 기각안은 `docs/modules/web/decisions/web-stack.md`에 있다.

**이 프로토타입은 그대로 둔다.** 흐름 검증 결과물이자 목업·문구의 근거이며 `npm run dev:prototype`도 유지한다.
