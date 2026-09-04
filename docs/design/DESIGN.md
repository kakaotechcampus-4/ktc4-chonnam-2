---
name: 대신고 (Daesingo)
description: 블랙박스 영상에서 사건을 찾아 신고 준비까지 돕는 도구. 보고보고 안전관제 디자인 시스템을 상속한다.
colors:
  app-bg: "#f7f9fc"
  panel: "#ffffff"
  panel-soft: "#f8fafc"
  surface-sunken: "#eef2f7"
  ink: "#111827"
  ink-2: "#344054"
  muted: "#5e6a79"
  muted-2: "#8a94a6"
  border: "#d9dee7"
  border-strong: "#c8d0dc"
  green: "#10933f"
  green-solid: "#0c8236"
  green-deep: "#087a35"
  green-soft: "#eaf7ef"
  green-border: "#bbf7d0"
  blue: "#2563eb"
  blue-soft: "#edf4ff"
  blue-border: "#bfdbfe"
  orange: "#ff8a00"
  orange-ink: "#b45309"
  orange-soft: "#fff7e6"
  orange-border: "#fed7aa"
  red: "#ef1b2d"
  red-soft: "#fff1f2"
  red-border: "#fecdd3"
  slate: "#526074"
  slate-soft: "#f1f5f9"
  slate-border: "#cbd5e1"
  video-ground: "#0b1220"
typography:
  display:
    fontFamily: "Pretendard, 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', system-ui, sans-serif"
    fontSize: "calc(36px * var(--font-scale))"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "0"
  headline:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "calc(22px * var(--font-scale))"
    fontWeight: 750
    lineHeight: 1.25
  title:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "calc(21px * var(--font-scale))"
    fontWeight: 800
    lineHeight: 1.25
  body:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "calc(17px * var(--font-scale))"
    fontWeight: 500
    lineHeight: 1.6
  label:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "calc(15px * var(--font-scale))"
    fontWeight: 900
    lineHeight: 1.4
  data:
    fontFamily: "'Roboto Mono', 'SF Mono', Consolas, monospace"
    fontSize: "calc(16px * var(--font-scale))"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "8px"
  lg: "14px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "20px"
  xl: "28px"
components:
  button-default:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "48px"
    typography: "{typography.body}"
  button-primary:
    backgroundColor: "{colors.green-solid}"
    textColor: "{colors.panel}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.green-deep}"
    textColor: "{colors.panel}"
  button-blue:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.blue}"
    rounded: "{rounded.md}"
    height: "48px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
    padding: "20px"
  field:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "52px"
  segment:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "0 20px"
    height: "54px"
  segment-active:
    backgroundColor: "#f0fbf4"
    textColor: "{colors.green}"
  badge-confirmed:
    backgroundColor: "{colors.green-soft}"
    textColor: "{colors.green}"
    rounded: "7px"
    padding: "4px 10px"
    height: "28px"
  badge-attention:
    backgroundColor: "{colors.orange-soft}"
    textColor: "{colors.orange}"
    rounded: "7px"
    padding: "4px 10px"
    height: "28px"
  badge-estimated:
    backgroundColor: "{colors.blue-soft}"
    textColor: "{colors.blue}"
    rounded: "7px"
    padding: "4px 10px"
    height: "28px"
  badge-unknown:
    backgroundColor: "{colors.slate-soft}"
    textColor: "{colors.slate}"
    rounded: "7px"
    padding: "4px 10px"
    height: "28px"
---

# Design System: 대신고

> **출처.** 이 시스템은 새로 만든 것이 아니라 이전 프로젝트인 **보고보고 안전관제 대시보드**(퍼블릭 레포 `bogobogo-incident-ops`, `apps/dashboard`)에서 추출했다. 토큰·타이포·컴포넌트 문법은 그 프로젝트가 원본이며, 대신고는 그것을 상속한 뒤 **정보 상태 5종**을 추가하고 접근성(AA 대비)을 위해 몇 값을 조였다. **값이 충돌하면 `apps/prototype/src/styles/tokens.css`가 이긴다** — 측정을 거친 현재 정본이다. 이 문서의 파일명 인용(`Badge`·`KVRow` 등)은 출처 각주일 뿐이며, 규칙은 이 문서만 읽어도 이해되게 적었다.

## Overview

**Creative North Star: "관제실의 명료함, 개인의 책상 위에서"**

보고보고는 관제요원이 여러 사고를 동시에 감시하는 콘솔이었다. 대신고는 운전자 한 명이 자기 사건 하나를 준비하는 책상이다. **시각 언어는 그대로 가져오고, 셸만 바꾼다.** 밝은 회청색 바탕(`#f7f9fc`) 위에 흰 패널을 얹고, 1px 테두리와 얕은 그림자로 층을 만들고, 상태는 항상 색·점·아이콘 세 가지로 동시에 말한다. 글자는 크고 굵다 — 본문 기본 굵기가 500이고 제목이 800인 것은 취향이 아니라 **가독성 결정**이다.

이 시스템의 성격은 "차분한 공공 도구"다. 화려하지 않고, 어둡지 않고, 유행하지 않는다. 색은 의미가 있을 때만 나타난다. 넓은 여백보다 **큰 글씨와 큰 터치 영역**을 택했다 — 버튼 48px, 입력 52px, 세그먼트 54px, 주요 판단 버튼 64px. 40–55세 사용자가 실수 없이 누를 수 있어야 한다.

**확인된 안티레퍼런스:** 다크 테마 작업공간, 트래킹 넓은 마이크로 라벨(9–10px), IBM Plex 계열 기관용 서체, AI SaaS의 그라디언트·글래스·반짝임. 앞의 세 가지는 대신고 1차 시안에서 시도했다가 "직관적이지 않고 AI티가 난다"는 이유로 폐기됐다.

**Key Characteristics:**
- 밝은 배경, 흰 패널, 8px 라운드, 얕고 넓은 그림자
- Pretendard 기반의 크고 굵은 한글 타이포
- 상태 = 색 + 점 + 아이콘 (색 단독 금지)
- `--font-scale` 사용자 배율(1 / 1.1 / 1.2)이 모든 글자 크기에 곱해짐
- 퍼센트로 위험도·확신도를 말하지 않는다

## Colors

밝은 회청색 기반의 실무형 팔레트다. 무채색이 화면의 90%를 덮고, 유채색은 **상태를 말할 때만** 등장한다.

### Primary
- **관제 그린** (`#10933f`): 브랜드색. 확인된 것, 완료된 것, 진행시키는 것. **밝은 바탕 위 글자·테두리 전용이다.** 흰 글자를 얹는 면(주요 버튼·`사용자 확인됨` solid 배지)에는 **`#0c8236`(`--green-solid`)**을 쓴다 — `#10933f` 위 흰 글자는 3.99:1로 AA(4.5:1) 미달이고 `#0c8236`은 4.93:1이다. Hover는 `#087a35`(`--green-deep`)로 깊어지며, 이 색은 `출처 확인됨` 배지의 글자색이기도 하다.

### Secondary
- **정보 블루** (`#2563eb`): **`AI 추정`** — 시스템이 말했고 아직 사람이 확인하지 않은 값. 파랑은 경고가 아니라 *출처 표시*라는 점이 중요하다.

### Tertiary
- **주의 오렌지** (`#ff8a00`): `확인 필요` — 사용자의 손이 필요하다는 뜻. **이 색이 보이면 할 일이 있다** — 그 외 용도로 쓰지 않는다. 주황 면 위에 글자를 얹어야 하면 **`#b45309`(`--orange-ink`)**를 쓴다; `#ff8a00` 위 글자는 대비가 부족하다.
- **부재 슬레이트** (`#526074`): `알 수 없음(UNKNOWN)`. 실패가 아니라 비어 있음이므로 무채색이다.

### Neutral
- **잉크** (`#111827`): 본문과 제목.
- **잉크2** (`#344054`): 보조 본문, 버튼 라벨.
- **뮤트** (`#5e6a79`): 부제, 메타, 필드 라벨. 라이트 배경 위 4.5:1을 넉넉히 넘긴다.
- **테두리** (`#d9dee7`) / **진한 테두리** (`#c8d0dc`): 패널 경계와 구분선.
- **앱 배경** (`#f7f9fc`) / **패널** (`#ffffff`) / **가라앉은 면** (`#eef2f7`).
- **영상 바탕** (`#0b1220`): 영상·썸네일 영역에만 쓰는 어두운 면. UI 배경으로 쓰지 않는다.

### Named Rules

**The Red-Is-Failure Rule.** `#ef1b2d`는 **시스템 오류에만** 쓴다. 분석 실패, 연결 끊김, 파일 손상. AI가 찾은 사건 후보나 위반 가능성에는 절대 쓰지 않는다. 빨강이 "위반"으로 읽히면 대신고는 법적 판정을 하는 제품이 되어버린다.

**The Forbidden-Percentage Rule.** **확신도·정확도·일치율을 어떤 숫자로도 표시하지 않는다.** 상태는 다섯 단어뿐이다. (원본 시스템이 「위험도 X%」 표현을 금지하고 등급으로만 표시하던 규칙을 더 강하게 적용한 것이다.)

**The Color-Never-Alone Rule.** 상태를 색만으로 구분하지 않는다. 모든 배지는 `점 + 아이콘 + 라벨 텍스트`를 함께 갖는다. 색각 이상과 흑백 인쇄에서도 읽혀야 한다.

## Typography

**Body / Display Font:** Pretendard (fallback: Noto Sans KR → Apple SD Gothic Neo → Malgun Gothic → system-ui)
**Data / Mono Font:** Roboto Mono (fallback: SF Mono → Consolas → monospace)

**Character:** Pretendard는 한글 화면용으로 만들어진 서체이고, 한국 사용자에게 "낯설지 않은" 것이 이 제품에는 장점이다. 개성보다 **즉시 읽힘**을 택했다. 숫자와 시각·번호판·파일명만 Roboto Mono로 빠져나가 데이터임을 표시한다.

### Hierarchy

모든 크기는 `calc(Npx * var(--font-scale))` 형태로 쓴다.

- **Display** (800, 36–38px, 1.15): 페이지 제목. 화면당 하나.
- **Headline** (750, 22px, 1.25): 카드 제목, 사건 제목.
- **Title** (800, 21px, 1.25): 패널 제목.
- **Body** (500–600, 16–17px, 1.6): 본문. 기본 굵기가 500인 것이 이 시스템의 특징이다.
- **Label** (900, 15–16px): 필드 이름, 섹션 라벨. `KVRow`는 라벨 15px/900 + 값 16px/700, `SecLabel`은 16px/900에 아래 1px 구분선.
- **Data** (700, 16–17px, Roboto Mono): 발생시각, 차량번호, 파일명, 구간.
- **Badge** (750, 14px): 상태 배지 전용.

### Named Rules

**The 15px Floor Rule.** 사용자가 읽어야 하는 어떤 글자도 15px 아래로 내려가지 않는다. 영상 위 오버레이 라벨만 예외이며 그마저 11px가 하한이다. (1차 시안이 9–10px 마이크로 라벨을 썼다가 대비 3.0–3.9:1로 무너진 것이 이 규칙의 근거다.)

**The Font-Scale Rule.** 새로 쓰는 모든 글자 크기는 `var(--font-scale)`을 곱해야 한다. 사용자가 설정에서 1.0 / 1.1 / 1.2를 고를 수 있고, 곱하기를 빼먹은 텍스트만 안 커지면 레이아웃이 깨진다.

**The Mono-Is-Evidence Rule.** Roboto Mono는 **영상·파일에서 나온 값**에만 쓴다. 시각, 번호판, 파일명, 구간. AI가 쓴 문장이나 UI 라벨에는 쓰지 않는다. 고정폭이 곧 "이건 기록에서 온 값"이라는 신호다.

## Layout

**셸.** 원본 시스템의 236px 사이드바 + 다중 페이지 구조는 **가져오지 않는다.** 대신고 사용자는 하나의 작업을 끝까지 진행한다. 대신 상단 진행 표시 + 단일 작업 영역을 쓴다.

**그리드.** 주 작업 화면은 `minmax(620px, 1fr) / minmax(420px, 500px)` 2열 — 왼쪽 영상·근거, 오른쪽 기록·판단. 1380px 아래에서 1열로 접힌다.

**여백.** 페이지 좌우 `clamp(14px, 1.45vw, 24px)`. 패널 내부 20px, 조밀한 패널 12–14px. 카드 그리드 간격 20px.

**밀도.** 낮다. 한 화면에 한 가지 결정. 후보는 최대 3개이고, 3개를 나란히 비교하는 것이 목적이므로 3열 고정이다.

**터치 영역.** 버튼 48px / 입력 52px / 세그먼트 54px / 사이드 내비 58px / 주요 판단 버튼 64px. 이 값들은 협상 대상이 아니다.

**브레이크포인트.** 1380 (2열→1열), 1180 (카드 3열→2열), 980 (툴바 세로), 720 (단일 열).

## Elevation & Depth

**하이브리드.** 바탕(`#f7f9fc`)과 패널(`#ffffff`)의 명도 차이로 기본 층을 만들고, 그 위에 얕고 넓은 그림자를 얹는다. 그림자는 장식이 아니라 "이것은 떠 있는 표면"이라는 구조 신호다.

### Shadow Vocabulary
- **패널 기본** (`0 4px 14px rgba(15,23,42,0.05)`): 모든 흰 패널과 카드의 기본 상태.
- **얕음** (`0 3px 10px rgba(15,23,42,0.06)`): 사이드 카드, 상태 알약, 버튼 hover.
- **떠오름** (`0 8px 22px rgba(15,23,42,0.08)`): 강조 패널.
- **카드 hover** (`0 10px 20px rgba(15,23,42,0.12)` + `translateY(-2px)`): 클릭 가능한 카드에만.
- **오버레이** (`0 14px 30px rgba(15,23,42,0.24)`): 영상 위 마커, 팝오버.

### Named Rules

**The Hover-Lifts-Only-Links Rule.** `translateY(-2px)` 상승은 **누르면 다른 화면으로 가는 것**에만 쓴다. 토글이나 인라인 편집 버튼은 뜨지 않는다. 뜨는 것 = 이동한다는 약속.

## Shapes

라운드는 8px가 기본이다(`--radius`). 6px는 영상 위 작은 오버레이 칩, 7px는 상태 배지, 14px는 큰 아이콘 박스, `999px`는 알약형 카운트와 우선순위 배지.

테두리는 항상 1px `#d9dee7`. 2px는 지도의 구역 경계처럼 **영역을 주장할 때**만 쓴다. 활성 상태는 테두리 색 변경 + `inset 0 0 0 1px`로 두께감을 만든다 (`.segment.active`) — 실제 border-width를 바꾸면 레이아웃이 1px 밀린다.

영상 프레임은 `aspect-ratio: 16/9`에 라운드를 부모에서 상속(`border-radius: inherit`)한다.

## Components

### Status Badge — 정보 상태 5종
`배경(soft) + 1px 테두리 + 색 텍스트 + 8px 점 + 아이콘`, 높이 28px(작은 것 24px), 라운드 7px, 14px/750. (원본 `Badge`의 구조에서 상태 어휘만 교체했다.)

| 정보 상태 | 색 | 배경 | 테두리 | 아이콘 |
|---|---|---|---|---|
| 출처 확인됨 | `#087a35` (글자 대비 4.95:1) | `#eaf7ef` | `#bbf7d0` | check-circle |
| 사용자 확인됨 | 흰 글자 | `#0c8236` solid 채움 (4.93:1) | `#0c8236` | check-circle (흰색) |
| AI 추정 | `#2563eb` | `#edf4ff` | `#bfdbfe` | info |
| 확인 필요 | `#ff8a00` | `#fff7e6` | `#fed7aa` | bell |
| 알 수 없음 | `#526074` | `#f1f5f9` | `#cbd5e1` | (점만) |

### 작업 상태 — 배지를 쓰지 않는다
`완료 / 진행 중 / 대기 / 부분 완료 / 중단 / 실패`는 **정보 상태와 같은 배지 컴포넌트를 절대 공유하지 않는다.** 진행 목록의 행 아이콘(체크 / 채운 원 / 빈 원)과 뮤트색 보조 텍스트로 표현한다. 이 분리가 Core User Flow §3의 요구사항이다.

### Button
높이 48px, 라운드 8px, 17px/700, 1px 테두리. 변형: `primary`(`--green-solid #0c8236` 채움 + 흰 글자), 기본(흰 바탕), `blue`(파란 글자 + `#9fc1ff` 테두리), `red`, `orange`. Hover는 테두리를 `#b8c2d1`로 조이고 얕은 그림자를 더한다. Disabled는 `#f8fafc` 바탕에 `#98a2b3` 글자.

### Panel
흰 배경 + 1px `#d9dee7` + 8px 라운드 + 패널 그림자. 제목은 `.panel-title`(21px/800), 그 아래 섹션 라벨은 `SecLabel`(16px/900 + 하단 구분선).

### KVRow — 값 + 출처 + 상태
좌측 라벨 / 우측 값의 8px 패딩 행(원본 `KVRow`)에 **세 번째 요소(상태 배지)와 네 번째(출처 한 줄)** 를 더한 확장형을 쓴다. 이것이 Product Spec §7의 「값 + 출처 + 상태」를 담는 그릇이다.

### CctvFrame → EvidenceFrame
`aspect-ratio: 16/9`, 어두운 바탕(`#0b1220`), 이미지 없으면 아이콘 placeholder. 하단 `.video-controls`는 `linear-gradient(180deg, transparent, rgba(0,0,0,0.82))` 위에 흰 컨트롤과 `#08c853` 진행 바. 영상 위 오버레이 칩은 `rgba(17,24,39,0.7)` 바탕에 흰 글자, 6px 라운드.

### Field / Segment
입력 52px, 세그먼트 54px(최소 너비 120px). 활성 세그먼트는 그린 테두리 + `#f0fbf4` 바탕 + inset 링.

## Do's and Don'ts

**Do**
- 상태를 말할 때 색·점·아이콘·라벨을 함께 쓴다.
- 영상·파일에서 나온 값은 Roboto Mono로 쓴다.
- 새 글자 크기에 `var(--font-scale)`을 곱한다.
- 정보 상태와 작업 상태를 다른 컴포넌트로 그린다.
- 클릭하면 이동하는 카드만 hover에서 띄운다.

**Don't**
- 확신도·정확도·위험도를 퍼센트로 쓰지 않는다.
- 빨강을 AI 결과에 쓰지 않는다. 빨강은 시스템 실패 전용이다.
- 오렌지를 "찾음"이나 "강조"에 쓰지 않는다. 오렌지는 사용자의 할 일 전용이다.
- 15px 아래 본문 글자를 쓰지 않는다.
- 다크 배경을 UI 표면으로 쓰지 않는다. 어두운 면은 영상 프레임 안에만 있다.
- 태극·무궁화·정부 상징 계열 형태를 쓰지 않는다. 「접수」「처리 중」 같은 접수기관 어휘를 쓰지 않는다.
