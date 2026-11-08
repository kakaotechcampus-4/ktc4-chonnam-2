# #597 B안 통합 실영상 E2E — 상황 응답 없이 초안 · 영상 · 묶음

**날짜:** 2026-11-07 ~ 11-08 · **실행자:** 유소연 · **대상:** [#597](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/597) B안 — Case [#616](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/616) + Evidence [#618](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/618) + Web [#621](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/621)

**목적:** 세 PR을 합친 빌드에서, 준영 님이 RC 포함 판단 기준으로 정한 흐름(#597 2026-11-07 댓글)을 실제 영상 · 실제 모델로 확인한다 — 유형 판별 시 응답 없이 초안 → 영상 자동 생성 → 묶음 → 다운로드, 유형 정정, 영상 생성 중 시각 정정, 판별 불가, 최종 검토 기록.

## 1. 빌드

| 항목 | 값 |
| --- | --- |
| 통합 커밋 | `bfdb8f10fa747810fa827199cd0f504cb0f058e9` — **로컬 merge commit, 원격에 없음**. 아래 네 커밋을 합친 것 |
| Case #616 | `59184b20` |
| Evidence #618 | `225f9bc6` |
| Web #621 | `ec979594` |
| develop 기준 | `784a53d5` (2026-11-07 17:36, #620 머지 시점) — **#617(Coarse 썸네일 발급)은 포함되지 않음** |
| 실행 환경 | 로컬 Docker Compose(API 1 · Worker 1 · MySQL 8.4), 이미지 `daesingo-rt13:local`을 통합 커밋으로 빌드. Worker 시작 로그 `revision`이 통합 커밋과 일치 |
| 모델 · 판독 | 실제 Search(argon) · Intent(Flash) 호출, 실제 PaddleOCR. Recording 설정은 `.env.example` 기본값(분석 4분 · 48 MiB) |
| 화면 | 통합 worktree의 `npm run dev:web`(Vite, 실제 API 모드) |

## 2. 입력

`synthetic_dashcam_e2e_v2/representative/20261102_140000_3min.mp4` — PM이 만든 합성 블랙박스 데이터셋 v2의 대표 3분본(1280×720 · 10fps · 35,660,581 B). 로컬 보관 · 비공개라 저장소에 넣지 않는다. 사건 E01 하나(00:20–00:36, 백색 실선을 넘어 진로를 바꾸는 차량, 테스트 번호판), 화면에 가상 시각(2026-11-02 14:00 KST 시작)이 각인돼 있다. 설명 문장에는 번호판 · 정답 시점을 넣지 않았다.

## 3. 결과

### 3-1. 정상 — Fine `OBSERVED`, 상황 응답 없음 · **PASS**

API로 실행(case `case_b747…`)하고 브라우저로 한 번 더 실행(case `case_21e5…`)했다.

- 탐색 → 1순위 자동 선택 → Fine `OBSERVED`(`SOLID_LINE_LANE_CHANGE`) → clip → 번호판 · 화면 시각 판독. 판독이 끝나자 EvidenceRecord가 **응답 없이** 조립됐다.
- `report_draft`: 「진로변경 위반 차량 신고」 · 「2026-11-02 14:00:23경 … 차량번호 12가3456 차량이 백색 실선을 넘어 진로를 변경하는 것을 확인하여 신고합니다 …」
- `REPORT_VIDEO_EXPORT` · `PLATE_IMAGE_EXPORT`가 **응답 전에** 자동 발주됐다(브라우저 case: export 05:06:47 UTC, 첫 사용자 응답 05:07:48 UTC).
- 상황 응답이 끝까지 `NOT_ASKED`인 채 `READY`. 첫 발주부터 약 221초(API case). 신고용 영상(MP4 16초, HTTP 200)과 번호판 이미지(PNG, HTTP 200)를 내려받았다.
- 화면: 「신고 상황 확인」 단계 없이 「신고자료가 준비됐어요」, 차량 번호 옆 번호판 장면 썸네일과 「신고할 차량의 번호판인지 확인해 주세요」.

### 3-2. 유형 정정 · **PASS**

`RECORD_SITUATION_RESPONSE {CORRECTED, visual_event_type}` — API는 `SIGNAL`, 브라우저는 「다른 상황이었어요」에서 이륜차 유형을 골랐다.

- 신고문이 바뀐 유형으로 다시 렌더링됐다(「신호위반 차량 신고」 / 「이륜차 안전모 미착용 신고」)고 곧바로 `READY`.
- **export를 다시 실행하지 않았다** — 두 case 모두 정정 뒤 export job이 새로 생기지 않았다(영상 · 번호판 이미지 입력이 같아 재사용).

### 3-3. 영상 생성 중 시각 정정 · **PASS**

API case `case_f136…`: `REPORT_VIDEO_EXPORT`가 RUNNING인 동안 `EDIT_EVENT_TIME`(14:00:23 → 14:00:30). 브라우저 case `case_21e5…`: READY 뒤 시각 정정.

- 정정 직후 `report_draft`의 시각이 바뀌고, 사후 각인 입력이 달라져 `REPORT_VIDEO_EXPORT`가 **새로 발주**됐다(API case 약 7초 뒤 `READY`).
- 묶음이 고른 영상은 새 입력의 것이다 — 그 asset의 export transform이 `post_stamp {needed: true, value: 2026-11-02T14:00:30+09:00}`이고, 내려받은 영상 첫 프레임 왼쪽 위에 `2026-11-02T14:00:30+09:00`이 찍혀 있다. 이전 입력의 영상(사후 각인 없음, 재인코딩 없는 복사본)은 묶음에서 빠졌다.

### 3-4. 판별 불가 — Fine `UNCERTAIN` · **PASS**

브라우저 case `case_012c…`. 1순위 Fine이 시간 초과로 실패한 뒤(3-6) 2순위 후보(Coarse 설명: 「야간 및 원거리 조건으로 … 실선인지 점선인지 명확히 판별하기 어려움」)를 「이 장면으로 다시 준비」로 골랐다.

- Fine 성공 → clip → 두 판독까지 끝났지만 EvidenceRecord가 **조립되지 않았다**(`evidence.record_id: null`, `case.situation_response_pending`). export도 발주되지 않았다.
- 화면: 「신고 상황을 확인해 주세요.」 — 사건 유형 · 신고 유형 · 위반 내용은 「상황 응답 뒤에 정해져요」.
- 「잘 모르겠어요」(`USER_UNSURE`) → 조립 → **일반형 신고문** 「교통법규 위반 상황 확인 요청」 · 「구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다. 차량번호는 영상에서 식별하지 못했습니다.」 → 응답 뒤 `REPORT_VIDEO_EXPORT` → `READY`.
- 번호판을 읽지 못해 `PLATE_IMAGE_EXPORT`는 발주되지 않았고 화면에는 신고용 영상 다운로드만 있다. 유형은 「확인 필요」이고 「다른 상황이었어요」는 보이지 않는다(`UNCERTAIN` 정정 미지원).

### 3-5. 최종 검토 기록 · **PASS**

API(`MARK_REVIEWED`)와 브라우저(「안전신문고로 이동」) 모두 뒤에 `user_reviewed: true`.

### 3-6. 같이 관찰한 것

- **Fine 실행 실패:** case `case_012c…`의 1순위 `FINE_VERIFY`가 `SEARCH_DEADLINE_EXCEEDED`(70초)로 실패했다. 같은 입력의 다른 실행은 성공했으므로 모델 응답 지연으로 본다. 화면은 「영상을 살펴보다가 문제가 생겼어요」이고 「처음으로」 · 다른 후보 고르기만 있다 — 같은 후보를 다시 확인하는 버튼은 없다.
- **#583 이전 동작:** 이 빌드에는 #617이 없어, 첫 Fine이 실패하자 다른 후보 카드가 「미리보기가 없어요」였다. #617이 들어간 develop을 합치면 Coarse 단계 썸네일이 있어야 한다(배포본 `bb29d750`에서 따로 확인).
- **후보 영상 미리보기:** `CANDIDATE_VIDEO_PREVIEW` 실행 · 재생 정상.

## 4. 확인하지 못한 것 · 한계

- **영상 생성 중 결과 화면의 캡처 없음.** export가 발주 뒤 10초 안에 끝나 브라우저 캡처 시점을 맞추지 못했다. 그 상태의 서버 응답(초안 있음 · `package` 없음 · export RUNNING)은 3-3 API 기록으로 확인했고, 화면 분기는 #621 web 테스트 근거다.
- **`UNCERTAIN` 응답 대기 화면의 「맞아요」.** 정책상 `UNCERTAIN + CONFIRMED`는 조립되지 않는다. 버튼이 남아 있어 누르면 계속 대기한다(#621에 알려진 한계로 적혀 있음). 이번에는 누르지 않았다.
- **유형 정정 문구.** 차량 번호판이 있는 case를 이륜차 유형으로 고치면 「차량번호 … 차량이 이륜차 운전자 또는 탑승자가 …」처럼 어색하다 — Evidence 템플릿 쪽.
- 단일 입력 · 단회 실행이다. 실제 배포본 · 운영 환경 · 다른 입력에서의 동작을 대신하지 않는다. 통합 커밋은 로컬에만 있으므로 머지 뒤 develop에서 다시 확인한다.
- 원본 영상 · 화면 캡처는 비공개 입력이 담겨 저장소에 넣지 않았다.
