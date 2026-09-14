# web 스택 — Vite + React + TS를 승계하고, 상태 레이어는 새로 짓는다

> **Owner:** 신유민 (`web`, 공동 개발 김대원) · 단독 결정 범위(모듈 내부)
> **결정:** 2026-09-14 · **구현 반영:** `apps/web` 첫 커밋
> 근거: `apps/prototype/README.md` 「미결」 문단이 이 결정을 Owner에게 넘겼다 · `contract-job-record-case-view.md` B절 · `docs/modules/web/ux/value-state-display.md`

## 확정

**1. `apps/web`을 새 npm workspace로 만든다.** 루트 `package.json`의 `workspaces: ["apps/*"]`·`engines.node >=20`을 그대로 쓴다. 스택은 프로토타입과 동일하게 **React 19 · TypeScript 5.8 · Vite 6**이고, 라우터·상태관리 라이브러리를 추가하지 않는다. 1차 범위에 화면 간 URL 이동도 서버도 없다.

**2. 프로토타입에서 가져오는 것 — 표현 레이어.**
- `src/styles/tokens.css` · `global.css` (토큰 정본)
- 표현 컴포넌트 `StatusBadge` · `KVRow` · `Panel` · `Button` · `SecLabel` · `Toast` · `AppBar` · `EvidenceFrame` · `SearchAxis` · `WorkList`
- 화면 레이아웃 10종의 구조와 문구

**3. 가져오지 않는 것 — 상태 레이어.**
- `src/machine.ts` (동기 reducer)
- `src/types.ts`의 `CaseState` · `AppState` · `Action` · `Step`
- `src/mock/*` (`caseData.ts` · `candidates.ts` · `files.ts`)
- `src/utils/widen.ts` · `utils/plate.ts` · `machine.ts`의 hint 정규식

**왜 버리는가 — 이어 쓰면 Merge 중단 기준에 걸린다.** 프로토타입은 화면이 스스로 판정한다.
- `SUBMIT_MEMORY`가 자연어를 정규식으로 파싱해 `hints`를 만든다 → 계약에서 `hints`는 `CaseView`가 내려주는 값이다
- `NEXT`가 `plate.status !== 'needs-review' && situation.status === 'user-confirmed'`로 진행 게이트를 계산한다 → `stage`·`user_reviewed`는 `case`가 소유하고 `READY`는 `PACKAGE_READY` 파생 gate다(B절 §10-7). 화면이 재계산하면 안 된다
- `computeWidenedScope()`가 범위 확장을 계산한다 → search/case의 몫

1차 완료 체크리스트의 Merge 중단 기준 「web이 `CaseView` 외 계약을 직접 읽거나 threshold를 자체 계산」에 그대로 해당한다. 코드를 물려받으면 이 계산들을 **찾아서 지우는 일**부터 하게 되고, 지우고 나면 `machine.ts`에 남는 게 거의 없다.

**4. 진실의 원천은 `CaseView` 1건이다.** 화면 선택은 `stage × progress × running_jobs × notices`를 읽는 **파생 함수**(`src/state/selectScreen.ts`)이고, 로컬 `step` 상태를 두지 않는다. 사용자 입력은 액션 발주(`JobRecord` 쪽)로 나가고 화면은 다음 `CaseView`를 받아 다시 그린다.

**5. 프로토타입은 지우지 않는다.** 흐름 검증 결과물이자 목업·문구의 근거이고, `npm run dev:prototype`도 그대로 둔다.

## 승계에 실제 가치가 있는 근거

| 프로토타입 | 계약 | 관계 |
| --- | --- | --- |
| `InfoStatus` 5종 (`source-verified`·`user-confirmed`·`ai-estimated`·`needs-review`·`unknown`) | `info_state` 5종 (`INFO_*`) | **1:1.** 둘 다 `core-user-flow.md` §3-1에서 나왔다(B절 §7 등재 문구가 명시) → `StatusBadge`가 값 이름만 바꿔 그대로 산다 |
| `tokens.css`의 `--green-solid` 등 | — | 목업 실측값 + 대비 보정(`#10933f`는 3.99:1로 AA 미달이라 `#0c8236` 분리). 다시 만들 이유가 없다 |
| `Field{value, source, status}` | `*_display{value, info_state, source_label_key, needs_review}` | 모양은 같고 **`source`(사람이 읽는 문장) → `source_label_key`(키)** 로 바뀐다. 라벨 맵이 새로 필요하다(`src/contracts/labels.ts`) |
| `Step` 10종 | `stage` 5종 + `notices`·`candidates`·`progress` 분기 | 화면 자산은 살고, **고르는 주체가 reducer → `CaseView` 파생 함수**로 바뀐다 |
| `Candidate{axisPct, matches, scene}` | `candidates[]{at, at_provenance, observed, thumb_ref, selected, timeline_revision, stale_revision, stale_revision_label_key, situation_confirmation}` | 겹치는 필드가 거의 없다. 카드 **레이아웃만** 재사용하고 데이터 형은 계약으로 새로 짠다 |

## 기각안

**A. `apps/prototype`을 `apps/web`으로 승격(개명)한다.** 이력이 이어지고 시작이 빠르다. 기각 — `machine.ts`·`mock/*`이 그대로 따라와서 위에 적은 자체 판정 코드를 상속한다. 지우는 작업이 새로 짜는 것보다 싸지 않고, 남겨두면 「값 재계산 안 한다」를 증빙할 수 없다. 프로토타입 실행 경로도 사라져 목업 근거가 같이 없어진다.

**B. Next.js·Remix 등으로 교체한다.** 기각 — 1차 범위에 SSR·라우팅·서버가 없다(체크리스트 「1차 완료 제외 범위」: 인증·영속성). 토큰·컴포넌트 승계가 끊기고 monorepo 빌드 설정을 다시 한다. 얻는 게 없다.

**C. 프로토타입을 참조만 하고 전부 새로 만든다.** 부분 채택 — 상태 레이어는 실제로 새로 만든다. 다만 토큰·표현 컴포넌트까지 다시 만드는 것은 검증된 대비값·간격을 버리는 것이라 채택하지 않았다.

## 이 문서에서 확정하지 않는 것

| 항목 | 왜 지금 아닌가 |
| --- | --- |
| `label_key` → 문구 맵의 소유 위치 | 키 공간이 `case`(`label_key`·`message_key`)와 `evidence`(`source_label_key`)에 걸쳐 있다. 첫 구현은 web이 `src/contracts/labels.ts` 한 파일로 갖는다. 키를 내리는 쪽이 문구까지 갖기로 하면 그때 옮긴다 |
| `at_provenance` 문구 매핑 | 값 공간 미등재 — PR #46 Q-3 답변에서 `at_provenance_label_key` 신설(`case-view/v1.4`)이 제안됐다. 확정 전까지 raw 값을 문구로 번역하지 않는다 |
| 테스트 러너(Vitest 도입 여부) | 현재는 `tsc -b` 타입 검사와 로더의 등재값 검사(화면 상단 「스냅샷 N건 파싱 OK」)로 갈음한다. 스냅샷 테스트를 붙일 시점에 정한다 |
| 모바일 반응형 | MVP 제외(§1-7 A1) |

## 첫 커밋 구조

```
apps/web/
  package.json  index.html  tsconfig.json  tsconfig.node.json  vite.config.ts
  src/main.tsx  src/App.tsx
  src/styles/{tokens.css,global.css,web.css}   # 앞의 둘은 프로토타입에서 이식
  src/contracts/caseView.ts                    # B절 §5·§6·§7 타입 (정본)
  src/contracts/fixtures.ts                    # data/mock/case/*.json 로더 + 등재값 검사
  src/contracts/labels.ts                      # label_key → 문구, 미등록 fallback
  src/state/selectScreen.ts                    # stage × progress × running_jobs × notices → 화면
  src/components/  src/screens/
```

루트 `package.json`에 `dev:web`·`preview:web` 스크립트를 추가한다(`--workspace=daesingo-web`).
