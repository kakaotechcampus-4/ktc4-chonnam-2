# [Readout·Web] Architecture Input Memo

> **성격:** 모듈 구조 설계 v4(`docs/architecture/module-architecture.md`) 작성의 근거가 된 Owner 자료조사 메모다. **조사 결과이지 결정이 아니다.** v4에 반영되지 않은 제안은 제안 상태로 남아 있고, 결정은 v4와 이 모듈의 `decisions/`에서만 한다. 문서 안의 `v3 §N`·`테크스펙 §N` 인용은 작성 당시(v3) 번호다.

**Owner:** 신유민

**관련 모듈:** `readout`(Producer) · `web`(Consumer) — 인접 모듈: `recording`, `search`, `evidence`, `case`

**근거 자료:** `[Readout] 기술 자료조사`, `[Web] 기술 자료조사`, `대신고 모듈 구조 설계 v3`(§4 모듈 · §5 계약 · §13 R&R)

**기준 버전:** Module Architecture v3 / R&R(v3 §13) / 기술 자료조사(2026-08-29)

> 참고: 유민이 `readout`(Producer)과 `web`(Consumer)을 함께 소유하므로 한 메모에 두 모듈을 담았다. 두 모듈의 접합부(§4)가 `PlateReadout` ↔ 번호판 검토 UI에서 직접 만나므로 함께 보는 편이 정확하다.
> 

---

## 1. 현재 추천 결론

> **결론:** 번호판은 single-frame confidence로 자동 확정하지 않고 `multi-frame consensus + abstain` 구조로 처리한다.
> 

> **근거:** Recognition-only sanity(15장)에서 오답이 confidence 0.998, 정답이 0.354로 나와 confidence가 정답성과 상관이 약했다. Exact 53.3% / edit-distance-1 이내 86.7% / CER 16.2%.
> 

> **Architecture 영향:** 없음. v3 §5-⑥ `PlateReadout`이 이미 `frame_results[]`·`consensus`·`abstained`를 보존하는 형태라 자료조사 결론과 일치.
> 

> **결론:** 1차 baseline은 `PaddleOCR pretrained`(OCR) + `EasyKoreanLpDetector`(검출), best frame은 `plate_px_height + sharpness`.
> 

> **근거:** detector sanity(test 100장, conf 0.25에서 crop 42장 생성), sauce-git ONNX는 검출률 낮아 후순위. best frame 두 지표만으로 시작.
> 

> **Architecture 영향:** 없음. OCR/detector 교체는 `readout/ocr/`·검출 어댑터 내부 교체로, 모듈 경계 영향 0(v3 §10-2 확인).
> 

> **결론:** `track_ref`는 필수 입력이 아니라 optional hint로 본다. `track_ref`가 없어도 readout이 자체 target association을 시도한다.
> 

> **근거:** 옆 차량 번호판을 읽으면 전체 결과가 오답이 되므로 association이 선행돼야 하지만, 실제 연속 영상이 없어 tracker 필요 여부는 미결. v3 RT10도 "track_ref 없이도 동작"을 요구.
> 

> **Architecture 영향:** 있음(접합부). `read_plate(span, target_hint)`에서 `target_hint`가 optional임을, 그리고 없을 때의 fallback 입력을 계약에 명시해야 함.
> 

> **결론:** 화면 시각(overlay) OCR은 readout이 "읽고 검증"까지만 하고, 최종 시각 source 선택은 `evidence`가 한다.
> 

> **근거:** v3 §3-2 Timestamp Resolver 분리 원칙, 자료조사 §9(format_ok / monotonic / duration_match 검증까지가 readout 역할).
> 

> **Architecture 영향:** 없음. 기존 경계 그대로.
> 

> **결론:** readout은 확정값을 하나도 소유하지 않는다. `PlateReadout.observation.status`를 `NEEDS_REVIEW`로 넘긴다.
> 

> **근거:** v3 §13-4 #4 관찰(`search`·`readout`)/확정(`evidence`) 소유 분리, §1-4 "'이렇게 보인다'와 '이 값이 맞다'를 같은 곳에서 다루지 않는다".
> 

> **Architecture 영향:** 없음.
> 

> **결론:** `web`은 `case.get_view()`가 반환하는 `CaseView` 하나만 소비하고, 도메인 상태(threshold·요건·시각 source)를 직접 계산하지 않는다.
> 

> **근거:** 자료조사 §6·§9, v3 web 모듈(의존은 `case` 하나).
> 

> **Architecture 영향:** 없음(기존 규칙 재확인).
> 

> **결론:** web의 실제 문제는 "화면 로직 부족"이 아니라 "CaseView 계약 부족"이다. 해결은 web 로직 추가가 아니라 `search/readout/evidence/case → CaseView projection` 보강이다.
> 

> **근거:** 자료조사 §7 결론 — 7상태 중 예외·저신뢰 경로(후보0·low-conf·GPS없음·timestamp충돌·plate abstain·timeout+partial)에서 CaseView 필드가 부족.
> 

> **Architecture 영향:** 있음. `CaseView` projection에 예외/저신뢰 상태 필드 보강이 필요(원천 상태는 각 backend 모듈이 생산).
> 

---

## 2. 확인된 기술적 제약

| 제약 | 근거 | Architecture / Data Contract 영향 |
| --- | --- | --- |
| PaddleOCR single-frame Exact 53.3%, CER 16.2% | Recognition-only sanity 15장 | 자동 확정 불가 → `consensus`/`abstain` 계약 필수 |
| confidence가 정답성과 상관 약함(오답 0.998, 정답 0.354) | 같은 실험 | confidence는 보조신호. accept 단독 기준 금지 → 계약에 `confidence`  • `abstained` 병기 |
| detector threshold 트레이드오프(낮추면 FP↑, 높이면 miss↑) | EasyKorean conf 0.15/0.25/0.40 비교 | threshold는 내부 파라미터(미결). 경계 영향 없음 |
| 실제 블랙박스 영상 부재 → tracker 필요 여부/종류, 정식 P/R/mAP 미측정 | 자료조사 §5·§10 | tracker 관련 결정은 `[미결]`. `target_hint` 계약은 tracker와 독립적으로 설계 |
| 2줄/구형/이륜차 번호판 오류 큼 → abstain 빈발 예상 | 자료조사 §2·§8 | abstain은 "정상 상태"로 계약·UI에 명시. 번호판 필수 여부는 `evidence` 요건 규칙 |
| web: 단일 `at` 값으로 timestamp 다중출처/충돌 표현 불가 | web 자료 §4 | `TimeResolution`/`CaseView`가 `considered[]`·`conflict`를 내려줘야 |
| web: candidate score만으로 low-confidence 자체 판정 불가(하면 안 됨) | web 자료 §4 | backend가 "판정 상태"로 내려줘야. web은 raw score 해석 금지 |

---

## 3. 현재 Module Architecture에 미치는 영향

### 그대로 유지 가능한 것

- readout public API 3개(`read_plate`, `read_overlay_time`, `list_impls`) 유지.
- `PlateReadout` / `OverlayTimeReadout` 계약 구조(`frame_results[]`·`best_frame`·`consensus`·`abstained`·`observation`) — v3 §5-⑥ 예시 JSON과 자료조사 필드가 일치.
- `readout → recording`(구간·프레임) 의존 유지, `search` 미의존 유지.
- `web → case` 단일 의존, `CaseView` 단일 소비 유지.
- 관찰/확정 분리(readout=관찰, evidence=확정) 유지.

### 수정 검토가 필요한 것

> **현재 구조:** v3 `CaseView`는 산문(prose)으로만 정의되어 있고 JSON 스키마 예시가 없다(부록 계약 중 유일).
> 

> **조사 결과:** web은 7상태(특히 예외·저신뢰)를 표현하려면 구조화된 필드가 필요.
> 

> **왜 검토가 필요한가:** web이 예외 상태를 추론하면 안 되므로 backend projection이 상태를 필드로 내려야 함.
> 

> **영향받는 모듈:** `case`(CaseView 소유), `evidence`/`search`(원천 상태), `web`(consumer).
> 

> **현재 구조:** `PlateReadout`에 `best_frame.frame_ref`, `frame_results[].frame_ref`가 이미 존재.
> 

> **조사 결과:** web의 `[다른 프레임 보기]/[확대해서 확인]/[번호판 수정]` UI가 이 값들을 직접 소비.
> 

> **왜 검토가 필요한가:** `CaseView` projection이 이 필드를 그대로 통과시키는지(노출 범위) 미확정.
> 

> **영향받는 모듈:** `readout`(producer), `case`(projection), `web`(consumer).
> 

> **현재 구조:** `read_plate(span, target_hint)`; `target_hint`는 `VisualEvidence.target`에서 나옴.
> 

> **조사 결과:** `track_ref` 없이도 동작해야(RT10). `target_hint`를 optional로.
> 

> **왜 검토가 필요한가:** `search` 실패/교체 시에도 readout 독립 동작을 보장하려면 계약에 optional·fallback을 명시해야 함.
> 

> **영향받는 모듈:** `readout`, `search`, `case`(값 전달).
> 

### 판단 불가

- tracker(ByteTrack / BoT-SORT / PP-Tracking / BoxMOT) 실제 필요 여부·종류 — 실제 연속 영상 없이는 판단 불가.
- consensus/abstain threshold 수치(2/3, 3/5 등), best frame weight/Top-K, 최소 pixel height/sharpness threshold — 실측 데이터 필요.
- web frontend framework 최종 확정(현재 React 추천), realtime 방식(polling vs push) — 경계 영향 낮아 후순위.

---

## 4. 접합부 / Data Contract에 영향을 주는 내용 ← 가장 중요

### readout 접합부

| 상대 모듈 | 방향 | 필요한/제공하는 정보 | 조사에서 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| `search` → readout (case 경유) | 받음 | `target_hint`(`VisualEvidence.target.track_ref`  • 사용자 단서) | `track_ref`가 없을 수 있음. readout 자체 association 필요 | `target_hint`를 optional로 할지 / 없을 때 최소 보장 입력(span·차량 특징) |
| readout → `evidence` | 제공 | `PlateReadout`(관찰값, `abstained` 포함) | readout은 확정 안 함. abstain 시 확정 번호판 없음 | `evidence`가 `abstained=true`를 어떻게 소비/재요청(`PLATE_REREAD`)하는지, `observation.status` 매핑 |
| readout → `evidence` (시각) | 제공 | `OverlayTimeReadout.observation`(`source=VIDEO_OVERLAY_OCR`) | 최종 시각 source 선택은 `evidence`(`TimeResolution`) | overlay를 언제 요청하는지(`EvidenceNeeds.OVERLAY_TIME_OCR`), tolerance_sec |
| readout → `recording` | 받음 | `span`(`AssetSpan`), 프레임 조회 | 파일 경계 넘는 span 존재 | `frame_ref` 표기(`asset@offset`), best_frame이 span 밖 프레임 참조 금지 |
| readout → `web` (CaseView 경유) | 제공 | `best_frame`·`frame_results[]`·`consensus`·`disagree_positions[]`·`abstained`·`abstain_reason` | 결과를 문자열 하나로 뭉개면 프레임 UI 불가 | 이 필드들이 `CaseView` projection에 그대로 실리는지·노출 범위 |

### web 접합부

| 상대 모듈 | 방향 | 필요한/제공하는 정보 | 조사에서 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| `case` → web | 받음 | `CaseView` 전체(`case.get_view()`) | web은 이것만 읽음. 도메인 계산 금지 | `CaseView` JSON 스키마 확정(현재 prose만), 예외상태 필드 포함 여부 |
| `evidence` → web (CaseView 경유) | 받음 | `EvidenceRecord`(`plate.prior` 포함), `RequirementReport`(4/5), `TimeResolution`(`considered`/`conflict`) | 단일 `at` 불가. 다중출처·conflict 필요 | `CaseView`가 이들을 어떤 projection으로 노출하는지 |
| `search` → web (CaseView 경유) | 받음 | `candidates[]`  • backend 판정 상태(low-confidence, reason, next action) | score만으로 web이 판정 금지 | low-confidence를 backend 상태로 내릴지, no-result의 reason/action 구조 |

---

## 5. 열린 결정

| 결정할 문제 | 가능한 방향 | 현재 추천 | 추천 근거 | 누구와 확인 |
| --- | --- | --- | --- | --- |
| `consensus`의 disagreement 표현 | A) `12가347?` 마스킹 문자열 · B) `disagree_positions[]` 인덱스 · C) 둘 다 | **C 둘 다** | web이 특정 문자를 강조하려면 위치 인덱스, 사람이 읽으려면 마스킹 문자열이 필요 | web(본인) · evidence |
| abstain의 상태 표현 | A) `status=NEEDS_REVIEW`  • `abstained=true` · B) `status=ABSTAIN` 신설 | **A** (v3 예시 방식) | Observation `status` enum 확장 최소화, `abstained`는 별도 필드로 명확 | 김준영(`Observation` Core 계약) · evidence |
| `target_hint` 필수 여부 | A) 필수 · B) optional + fallback | **B optional** | RT10: `track_ref` 없어도 동작해야 함 | search(서어진) · case |
| overlay OCR 실행 시점 | A) 항상 실행 · B) `EvidenceNeeds` 있을 때만 | **B 조건부** | metadata/filename 우선, 충돌 시에만 overlay(비용·지연) | evidence · case |
| `CaseView` 예외상태를 어디서 만드나 | A) `case` projection에서 종합 · B) 각 모듈이 상태 필드 생산 | **A projection 종합**(원천은 각 모듈) | web은 소비만, 상태 소유는 backend | case(유소연) · evidence |
| frontend framework | React+TS+Vite · 기타 | **React+TS+Vite** | prototype 속도, `CaseView` 타입화, 팀 친숙도. 경계 영향 낮음 | case(유소연) |

---

## 6. 충돌 / 상대 담당자 확인 필요

### A. 기존 Architecture와 충돌

- 직접 충돌 없음. readout 자료조사 결론은 v3 §5-⑥ `PlateReadout` 계약과 일치. 다만 `CaseView`는 v3에서 JSON 스키마 없이 prose로만 정의됨 — 이는 충돌이 아니라 **미완성**(§7·§8에서 결정 대상).

### B. 다른 모듈과 충돌 가능

- **대상 차량 track 기준 중복:** `search`가 `track_ref`를 주지만 readout이 자체 재추적한다. 어느 쪽 track을 기준으로 볼지 정의 안 되면 중복·불일치 가능 → `search`(서어진)와 확인.
- **overlay 시각 vs metadata/filename 시각:** readout이 overlay 값을 내지만 최종 선택은 `evidence`. readout 출력이 "확정처럼" 보이지 않도록 `status`/`note` 규약 필요 → `evidence`(김준영) 확인.

### C. Product / 정책 결정 필요

- **abstain일 때 신고 가능 여부:** readout이 아니라 `evidence` 신고 요건 규칙. 이륜차 안전모 등에서 번호판이 필수인지 여부 → evidence · 기획 결정.
- **개인정보:** `PlateReadout`의 번호판 값은 실제 PII. Mock은 synthetic 값만 사용. baseline 로컬 처리(v3 가정 A5) 유지 확인 → 김준영(Ops).

---

## 7. 후속 Data Contract에서 반드시 다룰 질문

1. `PlateReadout.consensus`의 불일치를 마스킹 문자열과 `disagree_positions[]` 중 무엇으로(또는 둘 다) 표현하나?
2. abstain은 `Observation.status`를 확장(`ABSTAIN`)하나, `NEEDS_REVIEW` + `abstained` 플래그로 두나?
3. `target_hint`는 필수인가 optional인가? `track_ref`가 없을 때 readout에 최소로 보장되는 입력(span·차량 특징)은?
4. `OverlayTimeReadout`는 항상 실행인가, `EvidenceNeeds(OVERLAY_TIME_OCR)`가 있을 때만인가? `tolerance_sec` 기본값은?
5. `best_frame`/`frame_results[]` 중 `CaseView`에 노출되는 필드 범위는? 원본 프레임 이미지 참조(`frame_ref`)를 web에 어떻게 제공하나?
6. `CaseView` JSON 스키마 확정 — 7상태(정상/후보0/low-conf/GPS없음/timestamp충돌/plate abstain/timeout+partial) 각각에 필요한 필드는?
7. low-confidence·no-result의 reason/next-action을 어떤 구조(reason code)로 내리나? (web은 문자열 추론 금지)
8. `ReadoutRun`의 실패 분류(`PLATE_TARGET_ASSOCIATION`/`DETECTION`/`RECOGNITION`/`OVERLAY_VALIDATION`)를 eval·web에 어디까지 노출하나?
9. `plate.prior`(AI 관찰값)를 사용자 수정 후에도 보존·표시하는 규약은?

---

## 8. 아키텍처 반영 우선순위

### 🔴 Architecture v4 전에 반드시 결정

- `target_hint` optional 여부 & readout↔search 대상차량 기준(track 소유) — readout 독립성의 근간.
- abstain의 `Observation.status` 표현 방식 — `Observation`은 Core 합의 계약(①).
- `CaseView`의 예외상태 projection 책임을 `case`가 갖는다는 원칙 확정.

### 🟡 Data Contract 단계에서 결정

- `PlateReadout`/`OverlayTimeReadout` 필드 세부(consensus 표현, overlay 조건부 실행, tolerance).
- `CaseView` JSON 스키마 및 web 노출 필드 범위.
- low-confidence/no-result reason 구조.

### 🟢 모듈 내부 Tech Spec에서 결정

- 최종 detector/tracker, threshold, best frame weight/Top-K, sampling 간격.
- frontend framework, polling vs push, 상태관리 라이브러리.

---

## 9. 원본 자료 Reference

| 자료명 | 근거 내용 |
| --- | --- |
| [[Readout] 기술 자료조사](https://app.notion.com/p/Readout-3cb7ae78fc6a80b0889ee635244bbd70?pvs=21)  | OCR/detector sanity, multi-frame consensus/abstain, timestamp OCR 원칙, `[미결]` 목록 |
| [[Web] 기술 자료조사](https://app.notion.com/p/Web-3cb7ae78fc6a80a1bd69e329e668c006?pvs=21)  | CaseView 7상태 검증, 보강 필요 필드, web 금지 판단 목록 |
| [대신고 모듈 구조 설계 v3](https://app.notion.com/p/v3-3c87ae78fc6a803eb2e5cebbe075a327?pvs=21)  | §4 readout/web 모듈, §5-⑥ `PlateReadout`/`OverlayTimeReadout` · 부록 `CaseView`, §13 R&R |