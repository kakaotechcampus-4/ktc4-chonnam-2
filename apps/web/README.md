# web — 브라우저 앱

## 처음 실행과 검사

저장소 루트에서 `npm ci` 후 `npm run dev:web`을 실행한다. 실제 흐름(`/`)과 공식 샘플(`?sample`)은 API 서버가 필요하다. API 없이 화면을 확인할 때는 `?demo` 또는 `?dev`를 사용한다.

```bash
npm run test:web
cd apps/web
npx tsc -b
cd ../..
npm run build --workspace=daesingo-web
npm run preview:web
```

`apps/web/package.json`에는 lint 명령이 없다. 빌드 명령에는 타입 검사(`tsc -b`)가 포함된다. [web-tests.yml](../../.github/workflows/web-tests.yml)이 타입 검사·Vitest·Playwright를 실행한다. E2E는 현재 `e2e/a11y.e2e.ts` **한 파일의 접근성·키보드 흐름**을 다룬다. 전체 API 연동 시나리오를 검증한 결과로 읽지 않는다. 로컬 E2E는 Chromium 설치 후 `npm run test:e2e --workspace=daesingo-web`로 실행한다.

## 화면에서 나가는 결과

사용자는 신고 문구를 복사하고 신고용 영상을 다운로드한 뒤 안전신문고로 이동한다. 신고 제출은 사용자가 안전신문고에서 직접 한다.

## 폴더 지도

| 경로 | 역할 |
| --- | --- |
| `src/screens/` | 업로드·진행·후보·결과와 하위 화면 |
| `src/components/` | 화면 공용 UI |
| `src/styles/` | 화면 스타일과 디자인 토큰 |
| `src/contracts/` | CaseView 타입과 표시 문구 |
| `src/api/`, `src/state/` | API 요청과 흐름 상태 |
| `e2e/` | Playwright 검사 |

화면 설계 문서는 [web 모듈 README](../../docs/modules/web/README.md)에 모았다.

**Owner:** 신유민 (공동 개발: 김대원 — 후보 카드·타임라인·번호판 확대) · **경계:** `docs/architecture/module-architecture.md` §4-모듈6 · **문서 작업공간:** `docs/modules/web/`

## 지금 상태

React 19/Vite 6 제품 앱이다. 루트 npm workspace에서 설치·빌드·테스트한다(`README.md`의 실행 방법). 분석을 기다리는 동안 사용자가 주행 게임을 선택하면 Three.js 0.160.1을 지연 로딩한다. 게임은 분석 상태를 읽거나 바꾸지 않는다. 빌드할 때 `VITE_DRIVING_GAME=off`를 주면 게임을 끈다.

## 하는 일

영상 업로드 → 장면 찾기 진행 → 후보 확인 → 번호판 · 발생 시각 확인 → 신고 문구 복사와 신고용 영상 다운로드. 제출은 사용자가 안전신문고에서 직접 한다.

## 입력 · 출력

- HTTP API `/cases/*`(`src/api/client.ts`) — CaseView 조회(`/view`, 2초마다 polling, `src/state/caseFlow.ts`), command(`/commands`), 영상 등록(`/sources`), 장면(`/frames`), 신고자료(`/assets`), 후보 영상(`/candidate-videos`).
- `/public/*` 공식 샘플 API(`src/api/publicSamples.ts`).
- 개발 서버는 `/cases` · `/public`을 API 서버로 넘긴다(`vite.config.ts`). 기본 `http://localhost:8000`, `API_PROXY_TARGET`으로 바꾼다.

## URL 진입 (`src/App.tsx`)

| 주소 | 화면 |
| --- | --- |
| `/` | 실제 흐름(ApiFlow). 이 브라우저가 마지막으로 연 case가 있으면 이어 본다 |
| `?case=<id>` | 그 case를 실제 흐름으로 이어 본다 |
| `?sample` | 공식 샘플 체험(OfficialSampleEntry) |
| `?demo` | mock fixture 시연 흐름(DemoFlow) |
| `?cases` | 시연에서 보여 줄 경우를 고르는 상자 |
| `?dev` | 스냅샷을 하나씩 넘겨 보는 증빙 화면 |

## 실행 · 테스트

루트에서 실행한다.

```bash
npm run dev:web        # 개발 서버. / 는 API 서버가 필요하다
npm run test:web       # vitest
(cd apps/web && npx playwright install chromium)   # e2e 처음 한 번
npm run test:e2e --workspace=daesingo-web           # Playwright e2e
```

결과 화면의 위치 지도는 선택 설정 `VITE_KAKAO_MAP_KEY`를 읽는다. 없으면 지도 칸만 숨는다(루트 `README.md`).

## 이 폴더와 `apps/prototype/`의 관계

- `apps/prototype/`은 **흐름 프로토타입**이다(mock 데이터, 백엔드 없음). 제품 코드가 아니고, 손대지 않는다.
- 실제 제품 화면과 API 연결은 이 폴더에 있다.

## 지켜야 할 것 (원문은 §4-모듈6)

- **`web → case.get_view() → CaseView`** 가 유일한 read dependency다. `evidence`·`search`·`readout` 계약을 직접 읽지 않는다 (§2 원칙 7).
- candidate score threshold · OCR accept threshold · Timestamp 우선순위 · 신고 기한 · 첨부 제한 · Evidence sufficient 여부를 **화면이 계산하면 Architecture 위반**이다.
- 화면 흐름의 상위 문서는 `docs/product/core-user-flow.md`, 디자인 토큰의 정본은 `apps/prototype/src/styles/tokens.css`(`docs/design/DESIGN.md` 참조).
- Desktop Web 우선. 모바일 반응형은 MVP 제외 (§1-7 A1).
