# 대신고 인터랙티브 프로토타입 — 구현 스펙

> **판본.** 이 문서는 프로토타입 구현 지시서로 쓰였고, `apps/prototype/`은 그대로 완성됐다. 이제는 **as-built 스펙**으로 읽는다 — 「만든다」는 「만들었다」로 읽으면 된다. 실제 코드와 어긋나면 코드가 아니라 이 문서를 고친다.
>
> **목적.** 프로덕션 코드가 아니라, **Core User Flow가 실제로 자연스럽게 흐르는지 클릭하며 평가하기 위한** 프로토타입이다.
> 실제 AI·백엔드·DB·인증·영상분석은 만들지 않는다. 모든 결과는 mock이다.
>
> **근거 문서.** `docs/product/product-spec.md` · `docs/product/core-user-flow.md` · `DESIGN.md`
> 충돌 시 **Product Spec 우선.**
>
> **1단계 산출물.** 화면 9개 목업 — `DESIGN-stage1-mockups.html` (브라우저로 연다). 프로토타입은 실패·연결 화면을 더해 10개 화면이다(`apps/prototype/README.md`).
> 이 스펙의 모든 화면 구성·색·크기는 그 목업을 기준으로 한다. 임의로 바꾸지 않는다.

---

## 0. 구현자에게 — 먼저 읽을 것

1. `DESIGN.md`를 읽는다. 토큰·타이포·컴포넌트 규칙이 전부 거기 있다.
2. `DESIGN-stage1-mockups.html`을 브라우저로 열어 화면 9개를 눈으로 본다. **이 스펙은 그 화면의 동작을 정의할 뿐, 생김새를 다시 정의하지 않는다.**
3. 막히면 추측하지 말고 §11 「미결」에 적고 진행한다.

### 절대 어기지 말 것 (Product Spec §7)

| 규칙 | 코드에서의 의미 |
| --- | --- |
| 값에는 항상 출처와 상태가 붙는다 | 모든 증거 필드는 `{ value, source, status }`. 값만 있는 필드 금지 |
| 정보 상태와 작업 상태를 섞지 않는다 | `<StatusBadge>`는 정보 상태 5종 전용. 작업 상태는 `<WorkList>`만 씀 |
| 없는 값을 만들지 않는다 | 확신도·정확도 퍼센트 금지. 남은 시간(ETA) 금지 |
| 빨강은 시스템 실패 전용 | AI 결과·후보에 `--red` 사용 금지 |
| 주황은 「사용자가 할 일」 전용 | 강조·발견 표시에 주황 금지 |
| 원본을 덮어쓰지 않는다 | 신고용 영상은 항상 파생파일로 표기 |
| 제출은 사용자가 한다 | 「접수」 버튼 없음. 안전신문고는 새 창 링크뿐 |

---

## 1. 프로젝트 설정

```
apps/prototype/
├─ package.json
├─ vite.config.ts
├─ tsconfig.json
├─ index.html
├─ public/
│  └─ meerkat.png            # 아래 §1.2
└─ src/
   ├─ main.tsx
   ├─ App.tsx                # 라우팅 없는 상태 머신 셸
   ├─ styles/
   │  ├─ tokens.css          # DESIGN.md 토큰 그대로
   │  └─ global.css          # 컴포넌트 클래스
   ├─ types.ts               # §3
   ├─ mock/
   │  ├─ files.ts            # 업로드 파일 42개
   │  ├─ candidates.ts       # 후보 3개 + 유사 후보 2개
   │  └─ caseData.ts         # 증거 필드 초기값
   ├─ machine.ts             # §4 전이 규칙 (순수 함수)
   ├─ components/
   │  ├─ AppBar.tsx          # 브랜드 잠금형 + 진행 레일
   │  ├─ StatusBadge.tsx     # 정보 상태 5종
   │  ├─ WorkList.tsx        # 작업 상태 (배지 아님)
   │  ├─ SearchAxis.tsx      # 시간 막대
   │  ├─ EvidenceFrame.tsx   # 블랙박스 SVG 프레임
   │  ├─ KVRow.tsx           # 값+출처+상태
   │  ├─ Panel.tsx, Button.tsx, SecLabel.tsx
   │  ├─ Toast.tsx           # 복사 알림
   │  └─ ScenarioBar.tsx     # §8 데모 컨트롤
   └─ screens/
      ├─ UploadScreen.tsx
      ├─ DescribeScreen.tsx
      ├─ ScopeScreen.tsx
      ├─ SearchingScreen.tsx
      ├─ CandidatesScreen.tsx
      ├─ NoResultScreen.tsx
      ├─ FailedScreen.tsx
      ├─ PrepareScreen.tsx
      ├─ ReviewScreen.tsx
      └─ HandoffScreen.tsx
```

**의존성 — 이것만.**

```json
{
  "dependencies": { "react": "^19", "react-dom": "^19", "lucide-react": "^0.460" },
  "devDependencies": {
    "@types/react": "^19", "@types/react-dom": "^19",
    "@vitejs/plugin-react": "^4", "typescript": "^5.8", "vite": "^6"
  }
}
```

라우터 없음(단일 상태 머신). 상태관리 라이브러리 없음(`useReducer` 하나). **Tailwind 쓰지 않는다** — `DESIGN.md`가 CSS 변수로 쓰여 있고 보고보고 `global.css`를 거의 그대로 옮기면 되므로 번역 레이어를 만들 이유가 없다.

### 1.1 폰트

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400..700&display=swap">
```

스택은 `DESIGN.md` 그대로: `'Pretendard','Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif`.

### 1.2 미어캣 마크

`public/meerkat.png`(128×128)은 이미 들어 있다. 원본 대형 아이콘(1295×1214)은 레포에 없다 — 아래 절차를 거친 결과물만 남겼다.

```
투명 여백 트림 → 정사각 캔버스에 중앙 배치 → 128×128 LANCZOS → PNG optimize
```

---

## 2. 디자인 토큰

`DESIGN.md`의 frontmatter가 정본이다. `tokens.css`에 그대로 옮긴다. 아래는 **1단계에서 실측으로 고친 값**이라 반드시 반영해야 하는 것들이다.

```css
:root{
  --font-scale:1;

  --app-bg:#f7f9fc;  --panel:#ffffff;  --panel-soft:#f8fafc;  --sunken:#eef2f7;
  --ink:#111827;     --ink-2:#344054;  --muted:#5e6a79;       --muted-2:#8a94a6;
  --border:#d9dee7;  --border-2:#c8d0dc;

  --green:#10933f;         /* 밝은 바탕 위 글자·테두리 전용 */
  --green-solid:#0c8236;   /* ★ 흰 글자를 얹는 모든 면. #10933f는 3.99:1로 AA 미달 */
  --green-deep:#087a35;    /* 배지 「출처 확인됨」 글자색 */
  --green-soft:#eaf7ef;  --green-bd:#bbf7d0;

  --blue:#2563eb;   --blue-soft:#edf4ff;   --blue-bd:#bfdbfe;
  --orange:#ff8a00; --orange-ink:#b45309;  --orange-soft:#fff7e6; --orange-bd:#fed7aa;
  --red:#ef1b2d;    --red-soft:#fff1f2;    --red-bd:#fecdd3;
  --slate:#526074;  --slate-soft:#f1f5f9;  --slate-bd:#cbd5e1;
  --video:#0b1220;

  /* 브랜드 — 워드마크와 마크 안에서만 산다. 버튼·배지에 쓰지 않는다 */
  --brand-ink:#0a5c46; --brand-sub:#4a6b5f; --brand-mint:#80e0c0;

  --R:8px;
  --sh-panel:0 4px 14px rgba(15,23,42,.05);
  --sh-soft:0 3px 10px rgba(15,23,42,.06);
  --sh-lift:0 8px 22px rgba(15,23,42,.08);
}
```

**모든 글꼴 크기는 `calc(Npx * var(--font-scale))`로 쓴다.** 본문 15px 하한. 터치 영역: 버튼 48px / 입력 52px / 주요 판단 64px.

---

## 3. 타입

```ts
// ---------- 상태 어휘 (Core Flow §3) ----------
export type InfoStatus =
  | 'source-verified'   // 출처 확인됨   green
  | 'user-confirmed'    // 사용자 확인됨 green solid
  | 'ai-estimated'      // AI 추정       blue
  | 'needs-review'      // 확인 필요     orange
  | 'unknown';          // 알 수 없음    slate

export type WorkStatus =
  | 'done' | 'running' | 'waiting' | 'partial' | 'stopped' | 'failed';

/** 정보 상태와 작업 상태는 같은 컴포넌트를 공유하지 않는다. */
export interface Field<T = string> {
  value: T | null;
  source: string;        // 사람이 읽는 출처 문장. 빈 문자열 금지
  status: InfoStatus;
}

// ---------- 화면 ----------
export type Step =
  | 'upload' | 'describe' | 'scope' | 'searching'
  | 'candidates' | 'no-result' | 'failed'
  | 'prepare' | 'review' | 'handoff';

// ---------- 사건 ----------
export interface Hints {          // 사용자가 말한 것을 AI가 구조화한 결과
  time: string;  vehicle: string;  event: string;  location: string;
  raw: string;                     // 원문. 「"흰 SUV"에서」 같은 근거 표시에 쓴다
}

export interface Candidate {
  id: string;
  time: string;                    // 18:31:48
  file: string;                    // FILE_023.MP4
  interval: string;                // 18:31:42 – 18:31:57
  axisPct: number;                 // 시간 막대 위 위치 0~100
  matches: { ok: boolean; text: string; note?: string }[];
  scene: 'solid-cross' | 'ambiguous-line' | 'dark-car';  // EvidenceFrame 변형
}

export interface CaseState {
  hints: Hints;
  scope: { from: string; to: string; files: number; totalFiles: number;
           fromPct: number; toPct: number };
  scannedPct: number;              // scope 내 진행. 0~100
  candidates: Candidate[];
  similar: Candidate[];            // 「비슷하지만 다른 장면」
  selectedId: string | null;
  plate: Field;
  occurredAt: Field;
  situation: Field;
  location: Field;
  reportType: Field;               // 신고유형 — AI 추정
  title: Field;                    // 신고 제목 — AI 추정
  clip: { name: string; size: string; duration: string; source: string };
  correction: null | { kept: string[]; changed: string[] };  // §5.2
}
```

---

## 4. 상태 머신

`machine.ts`는 **순수 함수**로 만든다. `reduce(state, action) => state`. 타이머는 화면이 갖고, 머신은 갖지 않는다.

### 4.1 전이표

| 현재 | 액션 | 다음 | 유지되는 것 |
| --- | --- | --- | --- |
| upload | `NEXT` | describe | 파일 목록 |
| describe | `SUBMIT_MEMORY(raw)` | scope | hints 파싱 결과 |
| scope | `EDIT_HINT(k,v)` | scope | 나머지 전부 |
| scope | `START_SEARCH` | searching | scope |
| searching | `TICK` | searching | scannedPct 증가, 후보 도착 |
| searching | `SEARCH_DONE` | candidates \| no-result \| failed | 시나리오에 따름 |
| searching | `STOP` | candidates | **지금까지 찾은 후보 유지** (partial) |
| searching | `EDIT_CONDITION` | scope | 후보 유지 |
| candidates | `SELECT(id)` | candidates | — |
| candidates | `ACCEPT` | prepare | 선택 후보 |
| candidates | `SHIFT('before'\|'after')` | searching | **차량·상황 유지, 시간만 변경** |
| candidates | `REJECT_ALL` | no-result | 스캔 이력 |
| no-result | `WIDEN` | searching | 이미 스캔한 구간 표시 유지 |
| no-result | `REDESCRIBE` | describe | raw 프리필 |
| no-result | `EDIT_VEHICLE` | scope | — |
| no-result | `SHOW_SIMILAR` | candidates | similar를 candidates로 |
| failed | `RETRY` | searching | **scannedPct 유지 — 처음부터 다시 하지 않는다** |
| failed | `SHOW_PARTIAL` | candidates | 부분 후보 |
| prepare | `SET_FIELD(k, Field)` | prepare | — |
| prepare | `NEXT` | review | 모든 필수 필드 해결 시에만 |
| review | `BACK` | prepare | — |
| review | `BUILD` | handoff | — |
| handoff | `NEW_CASE` | describe | 업로드 파일 |

### 4.2 「다음」이 열리는 조건 (prepare → review)

```
plate.status ∈ {user-confirmed, unknown}      ← needs-review면 막힘
situation.status === 'user-confirmed'          ← ai-estimated면 막힘
```

`occurredAt`·`location`·`reportType`은 **사용자 확인을 요구하지 않는다.**
Core Flow §13: 「사용자가 실제로 검증할 방법이 없는 정보에 억지로 확인 버튼을 요구하지 않는다.」
버튼이 막혀 있을 때는 비활성만 시키지 말고 **무엇이 남았는지 문장으로 말한다** — 「차량번호를 확인해주세요」.

### 4.3 불필요한 재확인 금지

한 번 `user-confirmed`가 된 필드는 **다시 묻지 않는다.**
`review`에서 되돌아와도 상태를 유지한다. `SHIFT`로 재탐색해도 **번호판·상황 확인은 초기화하지 않는다** — 같은 차량이기 때문. 단 후보가 바뀌면(`SELECT` 다른 id) 사건 종속 필드(`occurredAt`, `clip`, `situation`)만 리셋한다.

---

## 5. 화면별 동작

각 화면의 **생김새는 `DESIGN-stage1-mockups.html`을 그대로 따른다.** 여기서는 동작만 적는다.

### 5.1 공통 — AppBar

브랜드 잠금형(미어캣 54px + 대신고 26px/800 `--brand-ink` + 설명줄 15px/600 `--brand-sub` 「신고할 순간을 대신 찾아드립니다」)과 7단계 레일.

레일 매핑: `1 영상 올리기·2 사건 설명·3 범위 확인·4 사건 찾기·5 사건 선택·6 정보 확인·7 신고자료`
`searching`·`no-result`·`failed`는 모두 **4단계**로 표시한다. 오른쪽 상태 텍스트는 화면마다 다르다(목업 참조).

레일은 **표시 전용**이다. 눌러서 이동하지 않는다.

### 5.2 UploadScreen

- 드롭존은 **실제로 drag/drop과 파일 선택을 받는다.** 다만 내용은 읽지 않고 항상 mock 42개 목록을 보여준다. 드롭 시 `.drop.on` 하이라이트.
- 파일 목록 5행(완료 3 · 읽을 수 없음 1 · 올리는 중 1). 올리는 중 행은 68%에서 **3초 뒤 완료로 바뀐다.**
- 파일 상태는 `<WorkList>` 계열 표기 — `<StatusBadge>` 쓰지 않는다.
- 오른쪽 「영상에서 읽은 정보」에 촬영시간·화면시각·**GPS 없음**을 미리 보여준다.
- `다음 · 사건 설명하기` → describe.

### 5.3 DescribeScreen

- textarea. 우측에 예시 4칸(시간·상황·차량·위치) 상시 노출, 닫을 수 없음.
- 입력 중 **실시간으로 칩이 생기지 않는다.** 제출 후 다음 화면에서 구조화 결과를 보여준다. (입력 중 파싱은 틀렸을 때 방해가 된다)
- 프리셋 버튼 하나: `예시 문장 넣기` → `"6시 반쯤 흰 SUV가 실선을 넘어 끼어들었어요. 미금역 근처였던 것 같아요"`. **평가자가 매번 타이핑하지 않게 하는 장치이므로 반드시 넣는다.**
- 빈 입력으로 제출 시: 막지 말고 `시간 단서 없이 전체 찾기`로 안내.
- `SUBMIT_MEMORY` → hints는 **정규식으로 흉내낸다.** 실제 NLU 아님:
  ```
  /(\d+)시\s*(반|\d+분)?/ → time
  /(흰|검은|은색|빨간)\s*(SUV|승용차|오토바이|트럭)/ → vehicle
  /실선|중앙선|신호|끼어들|안전모/ → event
  /(\S+역|\S+IC|\S+사거리)/ → location
  ```
  매칭 실패한 항목은 `null`로 두고 scope 화면에서 **「못 알아들었어요」로 표시**한다. 지어내지 않는다.

### 5.4 ScopeScreen

- 단서 4칸. 각 칸에 `수정` → 인라인 입력으로 바뀜. `"흰 SUV"에서` 처럼 **원문 근거를 함께 보여준다.**
- 시간 막대에 초록 괄호. 범위 밖은 흐리게 남기고 **「나머지 33개는 그대로 남습니다」**를 문장과 그림 둘 다로 말한다.
- `맞아요, 찾아주세요` → searching.
- `구간 직접 조정` → 괄호 양끝을 드래그. **구현이 부담되면 ±15분 버튼 4개로 대체해도 된다.**

### 5.5 SearchingScreen — 가장 중요한 화면

- **퍼센트·ETA 금지.** 보여줄 것은 셋뿐: 시간 막대가 채워지는 모습 / `9개 중 N개 파일 확인` / 경과시간.
- 타임라인(기본 시나리오, 총 9초):

  | 경과 | 일어나는 일 |
  | --- | --- |
  | 0.0s | 「찾아볼 구간 정하기」 done, 「장면 확인」 running |
  | 0–9s | `scannedPct` 0→100 선형, 시간 막대 초록으로 채워짐 |
  | 3.0s | 후보 1 도착 → 오른쪽 목록에 행 추가 (번호 3) |
  | 5.0s | 후보 2 도착 (번호 2) |
  | 7.0s | 후보 3 도착 (번호 1) |
  | 9.0s | `SEARCH_DONE` |

- **`빠르게 건너뛰기` 버튼을 반드시 넣는다.** 평가자가 9초를 여러 번 기다리게 하면 안 된다. 누르면 즉시 완료.
- `prefers-reduced-motion: reduce`면 애니메이션 없이 1초 후 완료.
- `중단하기` → 확인 대화 없이 즉시 candidates로. 상단에 **`부분 결과 · 3개 중 2개 구간만 확인했습니다`** 배너. 「이어서 찾기」 버튼 제공.
- `조건 수정` → scope. 후보는 버리지 않는다.

### 5.6 CandidatesScreen

- 위: 선택된 후보의 큰 영상 + 「영상에서 확인된 것」 목록 + 판단 버튼.
- 아래: 후보 카드 3개. 번호(1·2·3)가 **시간 막대 마커와 같은 번호**다.
- 카드 클릭 = `SELECT`. 선택 카드는 2px 초록 테두리.
- 판단 버튼 배치 (§ Assessment A 지적 반영):
  - 위쪽: `네, 이 사건이 맞아요`(primary) / `조금 전이에요` / `조금 후예요` — **시간 보정만**
  - 아래쪽 우측: `세 개 다 아니에요` — **전체 거절만**
  - 두 종류의 「아니오」를 같은 줄에 두지 않는다.
- **`SHIFT` 동작 (Core Flow §9 — 이 프로토타입의 핵심 검증 대상):**
  1. searching으로 가되 **전체 재탐색이 아님을 화면이 말해야 한다.**
  2. 상단에 유지/변경 대비를 띄운다:
     ```
     유지   차량: 흰색 SUV · 상황: 실선 침범
     변경   시간 범위: 이전 2분 (18:29:48 – 18:31:48)
     ```
  3. 3초만 돈다(전체 9초 아님). 끝나면 후보 시각이 앞/뒤로 이동한 새 목록.
  4. **번호판·상황 확인 상태는 유지된다.**

### 5.7 NoResultScreen

- 「18:15 – 18:45 구간에서는 찾지 못했어요」 + 이유 한 줄.
- 시간 막대에 **이미 확인한 구간(초록)과 새로 확인할 구간(회청)을 겹쳐서** 보여주고 `영상 9개 → 21개 · 약 4분 더 걸립니다`로 **비용을 미리 말한다.**
- 4개 출구: `앞뒤 30분 더 찾아보기`(primary) / `시간을 다시 말할게요` / `차량 특징 고치기` / 유사 후보 2개 보기.
- 유사 후보는 「말씀하신 조건과 일부만 맞습니다」로 명시. 후보와 같은 위계로 두지 않는다.

### 5.8 FailedScreen

- 이 화면에서만 `--red`를 쓴다.
- 「영상 분석 중 문제가 발생했습니다」 + **「지금까지 완료된 작업은 저장되어 있습니다」**
- `다시 시도`는 **scannedPct를 유지한 채** 이어서 돈다. 0부터 다시 돌면 이 화면의 존재 이유가 없다.
- `현재까지의 후보 보기` → 부분 결과로 candidates.

### 5.9 PrepareScreen

- 왼쪽: 번호판 확대 + 프레임 4개(선명/흔들림/반사/가림). 클릭하면 큰 이미지가 바뀐다.
- 오른쪽: 사건 기록 KV 목록. **행 배경 = 그 행의 상태 색** (확인 필요 주황 / AI 추정 파랑 / 확정 흰색).
- 번호판:
  - `번호 직접 입력` → 인라인 입력(mono, 자동 대문자 없음). 저장 시 `user-confirmed`.
  - `읽을 수 없음으로 두기` → `unknown`. **경고 대화 없이 바로 진행 가능.**
  - **「이 번호가 맞아요」 버튼을 만들지 않는다.** `12가 34?6`처럼 물음표가 든 값을 「맞다」고 확인할 방법이 없다.
  - **입력 규칙은 §6-1을 따른다.** 띄어쓰기 안내 문구를 붙이지 않는다.
- 신고 상황: `읽고 확인하기` → 관찰 근거 3줄이 펼쳐지고 `맞아요` / `다른 상황` / `잘 모르겠어요`.
  `잘 모르겠어요`도 **진행을 막지 않는다** — `ai-estimated`로 남고 review에서 그렇게 표시된다.
- 헤더 우측에 `남은 확인 N개`. 0이 되면 `다음` 활성화.

### 5.10 ReviewScreen

- 전체를 다시 읽는 화면은 **흐름 전체에서 여기 한 번뿐이다.**
- KV 6~8행 + 신고문 전문 + 대신고가 준비한 것 / 안전신문고에서 하실 일.
- 신고문은 **편집 가능**(textarea 토글). 수정하면 `user-confirmed`.
- `정보 수정` → prepare (상태 유지).
- `신고자료 만들기` → handoff. 이때만 clip 생성 연출 1.5초.

### 5.11 HandoffScreen — 붙여넣기 / 직접 선택 분리

이 화면의 정확성이 이번 프로토타입에서 두 번째로 중요하다.

- **왼쪽(파랑) 붙여넣을 것 3개**: 제목 · 차량번호 · 신고 내용. 각각 `복사` 버튼.
- **오른쪽(주황) 직접 고를 것 4개**: 신고유형 · 발생일자 · 발생시각 · 발생장소.
  - **복사 버튼을 두지 않는다.** 있으면 누르고 왜 안 붙는지 헤맨다.
  - 각 항목에 「어디를 눌러야 하는지」 안내 한 줄.
  - 발생장소만 예외 — `검색어 「미금역」 복사`(붙여넣고 지도에서 핀).
- 복사는 `navigator.clipboard.writeText`. 실패 시 `document.execCommand('copy')` 폴백.
  성공하면 **Toast 「복사했습니다」 2초**. 버튼 라벨을 바꾸지 않는다(라벨은 동작 이름이어야 한다).
- `세 가지 전체 복사`는 칸 이름을 붙여 복사:
  ```
  제목: 백색 실선 침범 신고 (흰색 SUV 12가 3456)
  차량번호: 12가 3456
  신고 내용: 2026년 8월 24일 18시 31분경, …
  ```
- `안전신문고 열기` → `window.open('https://www.safetyreport.go.kr/', '_blank', 'noopener')`.
- 「접수」 버튼은 존재하지 않는다.

---

## 6-1. 차량번호 표기 규칙 — 확정

사용자가 어떻게 쓰든 받아주고, 화면에는 확정된 값을 그대로 보여준다.

| 층 | 규칙 |
| --- | --- |
| **입력** | `12가3456`과 `12가 3456`을 **모두 허용한다.** 어느 쪽도 고쳐 쓰라고 요구하지 않는다 |
| **내부 처리** | 비교·검증할 때만 공백을 지우고 맞춘다 |
| **표시** | OCR 결과 또는 사용자가 확정한 값을 **그대로** 보여준다. 임의로 공백을 넣거나 빼지 않는다 |
| **안내 문구** | 「띄어쓰기 없이 입력」류 문구를 **넣지 않는다** |

```ts
/** 비교·검증 전용. 화면 표시에 쓰지 않는다. */
export const normalizePlate = (v: string) => v.replace(/\s+/g, '');

/** 형식 검사 — 통과하지 못해도 진행을 막지 않는다(경고만). */
export const isPlateShaped = (v: string) =>
  /^\d{2,3}[가-힣]\d{4}$/.test(normalizePlate(v));
```

구현 시 주의:

- `value`에는 **사용자가 친 문자열을 그대로** 담는다. 저장 시점에 정규화하지 않는다.
- 화면 어디에도 「띄어쓰기」를 언급하지 않는다. 두 표기 모두 유효하므로 안내할 것이 없다.
- 형식이 어긋나도 저장을 막지 않는다. 지역번호판·구형 번호판 등 예외가 있고,
  **최종 판단은 사용자와 접수기관의 몫**이다 (Product Spec §7).
- `handoff`의 복사 버튼은 `value`를 그대로 복사한다.

---

## 6. 컴포넌트 계약

```tsx
<StatusBadge status={InfoStatus} sm? />
// 정보 상태 5종 전용. 색+점+아이콘+라벨을 항상 함께 그린다.
// 작업 상태를 넘기면 타입 에러가 나도록 union을 좁힌다.

<WorkList items={{ label: string; status: WorkStatus; note?: string }[]} />
// 행 아이콘(체크/채운원/빈원) + 뮤트 보조텍스트. StatusBadge를 쓰지 않는다.

<SearchAxis
  from="15:40" to="19:12"
  scope={{fromPct, toPct}} scannedPct={number}
  markers={{ n: number; pct: number; selected?: boolean }[]}
  legend?
/>
// 마커는 28px 번호 원. 시각은 막대에 쓰지 않는다(옆 목록에서 읽는다).
// 겹치면 아래 줄로 내리고 연결선을 늘린다 — 1단계에서 두 번 고친 규칙이다.

<EvidenceFrame scene={Candidate['scene']} time? file? annotations? size? />
// 인라인 SVG. 실선과 점선을 눈에 띄게 다르게 그린다.
// 주석은 전부 초록. 주황 금지.

<KVRow label value source status action? tint? />
```

---

## 7. Mock 데이터

목업의 값을 그대로 쓴다. 새로 지어내지 않는다.

- 주행: `2026-08-24 15:40 – 19:12`, 42개 파일, 3시간 32분, GPS 없음
- 우선 범위: `18:15 – 18:45`, 9개 파일 (막대상 70.9% ~ 85.1%)
- 후보 3: `18:31:48`(FILE_023) / `18:25:40` / `18:19:03`
- 유사 후보 2: `18:38:22` 검은 승용차 / `18:21:05` 점선 구간
- 번호판 `12가 34?6` → 확인 후 `12가 3456`
- 신고유형 `교통위반 › 진로변경 위반`
- 클립 `daesingo_event_001.mp4` · 15초 · 84MB (한도 130MB)

---

## 8. ScenarioBar — 평가용 컨트롤

**반드시 만든다.** 이게 없으면 실패 흐름을 평가할 수 없다.

화면 하단 고정 바(1단계 로고 토글과 같은 형태):

| 컨트롤 | 값 |
| --- | --- |
| 결과 시나리오 | `후보 3개`(기본) · `후보 없음` · `분석 실패` |
| 번호판 | `일부 불확실`(기본) · `판독 불가` · `선명` |
| 진행 속도 | `보통 9초`(기본) · `즉시` |
| — | `처음부터 다시` |

- 시나리오는 `searching` 진입 시점에 읽는다.
- 이 바는 프로토타입 전용임을 라벨로 밝힌다 — 「평가용 · 실제 제품에는 없습니다」.
- `--font-scale` 토글(1 / 1.1 / 1.2)도 여기 넣으면 접근성 확인이 쉽다.

---

## 9. 완료 조건 — 이 4가지가 클릭으로 이어져야 한다

사용자가 요구한 흐름이다. 각각 **처음부터 끝까지 끊기지 않고** 돌아가야 한다.

1. **정상** — upload → describe → scope → searching → candidates → 선택 → prepare(번호판 입력) → review → handoff(복사)
2. **보정** — candidates에서 `조금 전이에요` → 유지/변경 대비 표시 → 3초 재탐색 → 새 후보 → 선택
3. **불확실** — prepare에서 프레임 4개를 넘겨보고 번호 입력 / 또는 `읽을 수 없음`으로 두고 진행 → review에 `알 수 없음`으로 반영
4. **복구** — 시나리오 `분석 실패` → FailedScreen → `다시 시도`가 **이어서** 진행 → 완료
   그리고 시나리오 `후보 없음` → NoResultScreen → `앞뒤 30분 더` → 완료

---

## 10. 검증

구현 후 **실제 브라우저에서 직접 클릭**해 확인한다. claude-in-chrome으로 한다(Playwright 불필요).

### 기능
- [ ] 위 4개 흐름이 끝까지 진행된다
- [ ] `중단하기` 후에도 찾은 후보가 남는다
- [ ] `다시 시도`가 0%부터 다시 돌지 않는다
- [ ] 한 번 확인한 값을 다시 묻지 않는다
- [ ] 「직접 고를 것」 4개에 복사 버튼이 없다
- [ ] `12가3456`과 `12가 3456` 둘 다 저장된다
- [ ] 화면 어디에도 「띄어쓰기」 안내 문구가 없다
- [ ] 「접수」 버튼이 어디에도 없다

### 규칙 위반 자동 점검 (콘솔에서 돌릴 수 있게)
- [ ] 화면 어디에도 확신도·정확도 퍼센트가 없다
- [ ] 남은 시간(ETA) 표기가 없다
- [ ] `--red`가 FailedScreen 밖에서 쓰이지 않는다
- [ ] `--orange`가 「확인 필요」 외의 뜻으로 쓰이지 않는다
- [ ] `StatusBadge`에 작업 상태가 들어간 곳이 없다
- [ ] 15px 미만 본문 텍스트가 없다 (영상 오버레이 제외, 하한 11px)
- [ ] 대비 4.5:1 미만 텍스트가 없다 (1단계에서 0건 달성했다)

### UX
- [ ] 각 화면에서 다음 행동이 한눈에 보이는가
- [ ] 분석 중 지금 무슨 일이 일어나는지 이해되는가
- [ ] 후보 비교와 보정이 부담스럽지 않은가
- [ ] 실패 후 이전 작업을 잃지 않는가
- [ ] 1단계 디자인 방향이 인터랙션에서도 유지되는가

---

## 11. 미결 — 구현하며 정하지 말고 여기 적을 것

Core Flow §26이 「지금 임의로 고정하지 않는다」고 한 것들이다. 프로토타입에서는 아래 **가정값**으로 두되, 값을 바꾸기 쉽게 상수로 뺀다.

| 항목 | 프로토타입 가정 | 실제 결정 근거 |
| --- | --- | --- |
| 단일 후보 vs 비교 분기 임계값 | 항상 Top-3 비교 | 평가 결과 |
| 분석 제한시간 | 9초(연출) | 실측 |
| ETA 제공 여부 | 제공 안 함 | 실측 축적 후 |
| 번호판 UNKNOWN으로 자료 생성 허용 | 허용 | 별도 Product Decision |
| `AI 추정` 상태로 준비 완료 통과 | 신고 상황만 확인 요구 | 미정 |
| 안전신문고 입력 규칙 | 붙여넣기 3 · 선택 4 | **실물 화면 확인 필요** |

마지막 항목이 가장 위험하다. 신고유형 분류 이름과 시·분 선택 단위는 **실제 안전신문고 화면을 보고 맞춰야 하며**, 바뀌면 HandoffScreen 안내 문구가 따라 바뀐다.

**차량번호 표기는 확정됐다** — §6-1. 미결에서 뺀다.

---

## 12. 하지 말 것

- 실제 영상 파일 읽기·재생 (프레임은 SVG로 그린다)
- 라우터·전역 상태 라이브러리 도입
- 새 색·새 서체·새 컴포넌트 언어 발명 (`DESIGN.md`가 정본)
- 로딩 스켈레톤 시머, 그라디언트, 반짝임 아이콘
- 「AI가 분석 중입니다 ✨」류 문구 — AI는 책임 소재를 밝힐 때만 등장한다
- 접수·제출을 대신하는 어떤 동작
