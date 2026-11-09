# web — 브라우저 앱

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
