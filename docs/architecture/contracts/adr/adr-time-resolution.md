# ADR-07: ⑦ TimeResolution Data Contract 확정

**Status:** Accepted

**Contract:** `⑦ TimeResolution`

**Producer:** `evidence`

**Consumer:** `case` (Runtime), `web` (Review / CaseView projection)

**Owner:** 김준영

**결정일:** `2026-09-04`

**관련 Contract Version:** `time-resolution/v1`

**ADR ID:** `ADR-07`

**관련 Architecture Version:** 대신고 모듈 구조 설계 v4

관련 문서:

- [Product Spec](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/product/product-spec.md)
- [Module Architecture v4](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/module-architecture.md)
- [R&R / Ownership](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/management/ownership.md)
- [Data Contract Draft — TimeResolution](https://app.notion.com/p/Data-Contract-Draft-TimeResolution-3cf7ae78fc6a81a3a27bff05171668fe?pvs=21)
- [Final Data Contract — ① Observation<T> v1](https://app.notion.com/p/Final-Data-Contract-Observation-T-v1-3d17ae78fc6a81c1a676f436d65d14a6?pvs=21)
- [부록 `JobRecord / CaseView - Final Data Contract`](https://app.notion.com/p/JobRecord-CaseView-Final-Data-Contract-3d07ae78fc6a801aaa2bfed560a9d19e?pvs=21)
- Final Data Contract — `TimeResolution v1` (본 ADR과 함께 확정)

---

# 1. 결정 배경 (Context)

### Producer가 생성하는 것

`evidence`는 `recording`·`readout`의 시간 Observation과 명시적 사용자 correction을 비교하여 제품이 사용할 사건 발생시각과 source·verification·conflict·계산 provenance를 확정한다.

### Consumer가 필요로 하는 것

`case`는 최종 시각과 사용자 검토 필요 여부를 받아 workflow 및 `CaseView`를 구성해야 한다. `web`은 domain contract를 직접 재판정하지 않고 CaseView projection을 표시한다.

### 계약을 고정해야 했던 이유

- Overlay / Filename / Metadata / User 등 서로 다른 시각 source를 한 의미로 비교해야 했다.
- `resolved value`가 존재하면서 source conflict도 존재할 수 있어 단일 status만으로는 표현이 부족했다.
- Consumer가 source priority를 다시 계산하면 evidence ownership이 깨진다.
- UNKNOWN, 사용자 correction, 사후 Timestamp 각인의 provenance를 잃으면 AI가 만든 값과 원본 관찰을 구분하기 어렵다.
- 사용자 수정 시 기존 결과를 덮어쓸지 새 result로 남길지 lifecycle을 고정해야 했다.

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| Timestamp 값과 출처를 함께 관리 | Product Spec | `resolved.value`만이 아니라 source/provenance를 보존 |
| 신뢰 가능한 source가 없으면 AI가 임의 시각 생성 금지 | Product Spec | `UNKNOWN`을 정상 상태로 지원 |
| 관찰과 확정 분리 | Module Architecture v4 | recording/readout은 Observation, evidence만 TimeResolution 판정 |
| 검증된 Video Overlay 우선 | Module Architecture v4 | source priority는 evidence 내부 정책이며 Consumer가 재계산하지 않음 |
| Filename/metadata 충돌 시 fallback 값과 conflict provenance 동시 보존 | Module Architecture v4 | `resolved + conflict=true` 허용 |
| Metadata가 없거나 신뢰가 약할 수 있음 | Recording/Evidence 조사 | numeric confidence보다 verification/provenance 중심 |
| web은 domain contract를 직접 읽지 않음 | Module Architecture v4 / CaseView Final | Runtime Consumer는 case, web은 safe projection만 사용 |
| MVP는 대한민국 안전신문고 신고 준비 제품 | Product Spec + PM 최종 결정 | timezone 정보 부재 시 `Asia/Seoul (+09:00)` 제품 context 적용 |

---

# 3. 검토했던 주요 선택지

## 결정 1. TimeResolution 상태 체계

### A안 — 별도 TimeResolution Status Enum

TimeResolution만의 상태를 새로 정의한다.

**장점**

- resolution 의미에 맞춘 이름을 만들 수 있다.

**단점**

- Observation과 유사한 UNKNOWN/검토필요 의미를 다시 정의한다.
- CaseView projection 규칙이 복잡해진다.

### B안 — Observation 상태 언어의 subset 재사용

`OK / NEEDS_REVIEW / UNKNOWN`만 사용하되 TimeResolution 자체를 Observation으로 만들지 않는다.

**장점**

- 공통 상태 언어를 유지하면서 관찰/확정 책임은 분리된다.
- Consumer 분기가 단순하다.

**단점**

- status만으로 verification/conflict를 모두 표현할 수 없어 별도 축이 필요하다.

## 결정 2. VERIFIED / AGREED / CONFLICT 표현

### A안 — 단일 Enum

검증·합의·충돌을 한 상태 공간에 넣는다.

**장점**

- 필드 수가 적다.

**단점**

- `VERIFIED + conflict=true`처럼 동시에 성립 가능한 상태를 표현하기 어렵다.

### B안 — `verification`과 `conflict` 분리

검증 상태와 후보 간 충돌을 서로 다른 축으로 둔다.

**장점**

- 실제 Architecture 의미를 그대로 표현한다.
- resolved fallback과 conflict를 동시에 보존할 수 있다.

**단점**

- Consumer가 두 필드를 함께 이해해야 한다.

## 결정 3. 사용자 입력 provenance

### A안 — 모든 입력을 Observation으로 통일

사용자 입력도 Observation으로 재포장한다.

**장점**

- 입력 형태가 하나다.

**단점**

- case/user를 Observation Producer로 추가해야 하며 관찰/확정 경계가 흐려진다.

### B안 — `OBSERVATION | USER_INPUT` 별도 허용

자동 관찰은 Observation reference, 사용자 입력은 별도 USER_INPUT provenance로 둔다.

**장점**

- 자동 관찰과 사용자 correction을 명확히 구분한다.
- 기존 Observation Producer 범위를 바꾸지 않는다.

**단점**

- USER_INPUT reference의 authoritative 대상을 명확히 해야 한다.

## 결정 4. `considered[]` 보존 수준

### A안 — Reference만 보존

최소 reference만 저장한다.

**장점**

- 가장 작다.

**단점**

- CaseView/설명에 필요한 source/value/verification을 매번 재조회해야 한다.

### B안 — Summary snapshot + Reference

판정에 사용한 최소 summary와 authoritative ref를 같이 보존한다.

**장점**

- Consumer가 Producer 내부 diagnostics를 몰라도 된다.
- provenance 설명에 필요한 최소 정보가 한 곳에 있다.

**단점**

- 일부 snapshot 중복이 생긴다.

### C안 — 원본 Observation 전체 복제

**장점**

- self-contained하다.

**단점**

- 불필요한 diagnostics/confidence까지 결합되고 stale/중복 위험이 커진다.

## 결정 5. 최종 Timestamp numeric confidence

Draft는 최종 numeric confidence를 유지할지, upstream confidence를 조합할지, 제거하고 verification/provenance로 표현할지를 검토했다.

최종적으로 **TimeResolution 자체의 numeric confidence를 제거**하고 source·verification·conflict·provenance를 사용한다.

## 결정 6. 시간 형식 / timezone

Draft는 offset-aware RFC3339를 추천했으나 timezone source가 미결로 남아 있었다.

Final에서 PM 결정으로 **MVP 기본 제품 context를 `Asia/Seoul (+09:00)`로 확정**했다. Source가 explicit timezone/offset을 제공하면 이를 provenance로 보존하고, 제품 context와의 충돌을 조용히 덮어쓰지 않는다.

## 결정 7. 사용자 correction lifecycle

기존 TimeResolution을 mutate하는 안과, 새 immutable result + `supersedes_ref`로 연결하는 안을 검토했다. Final은 후자를 채택한다.

## 결정 8. UI 노출 상태 소유권

`shown_to_user`를 evidence가 소유하는 안과, evidence는 `requires_user_notice`만 내리고 실제 노출은 CaseView/web이 관리하는 안을 검토했다. Final은 후자를 채택한다.

## 결정 9. 사후 Timestamp 각인 provenance

`post_stamp`는 필요 여부/이유만 소유하고 실제 export 상태는 별도 runtime/asset 흐름에 둔다. PM 최종 결정으로 **USER_INPUT 기반 사후 각인은 반드시 non-blocking notice 대상**으로 한다.

---

# 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| 상태 체계 | `OK / NEEDS_REVIEW / UNKNOWN` | B안 | case/web 승인 | 유지 |
| verification / conflict | 별도 축 | B안 | 승인 | 유지 |
| 사용자 입력 provenance | `USER_INPUT`  • `CorrectionRecord` ref | B안 | case가 실제 ref 대상 명확화 요청 | 수정 |
| `considered[]` | summary snapshot + Ref | B안 | case/web 승인 | 유지 |
| numeric confidence | 제거 | 제거 추천 | web 승인 | 유지 |
| 최종 시간 형식 | offset-aware RFC3339 | 추천 | 반대 없음 | 유지 + timezone source 확정 |
| timezone source | explicit source 우선 보존, 없으면 `Asia/Seoul (+09:00)` 제품 context | 미결 | Consumer blocker 아님 | PM 최종 결정으로 확정 |
| 사용자 수정 lifecycle | 새 immutable Resolution + `supersedes_ref` | B안 | case 승인 | 유지 |
| 실제 UI 노출 상태 | `requires_user_notice`만 evidence가 제공 | B안 | case/web 승인 | 유지 |
| USER_INPUT 사후 각인 | non-blocking notice 필수 | 고지 수준 미결 | Consumer blocker 아님 | PM 최종 결정으로 확정 |

## 결정 1. USER_INPUT reference를 `CorrectionRecord`로 닫는다

**최종 선택:** B안 + Consumer 수정 반영

**결정 내용:**

`considered[].input_kind=USER_INPUT`이면 `input_ref`는 case 소유 `CorrectionRecord`를 직접 참조한다. 별도의 TimeResolution 전용 사용자 입력 entity를 만들지 않는다.

`EVENT_TIME_MANUAL`은 최종 사건시각 correction provenance로 사용할 수 있다. `TIME_HINT_EDIT`는 Search 범위용 단서이므로 그 자체를 확정 `occurred_at`으로 사용하지 않는다.

**선택 이유:**

- 사용자 입력을 Observation으로 위장하지 않는다.
- case가 이미 소유하는 correction history를 재사용한다.
- Consumer가 요청한 안정적 reference 대상을 추가 entity 없이 제공한다.

## 결정 2. Timezone은 `Asia/Seoul` 제품 context를 기본으로 한다

**최종 선택:** offset-aware RFC3339 + timezone provenance

**결정 내용:**

Source에 explicit timezone/offset이 있으면 이를 보존하고, 없으면 현재 MVP의 대한민국 신고 제품 context에 따라 `Asia/Seoul (+09:00)`을 사용한다.

**선택 이유:**

- 신고에 사용할 실제 사건시각은 timezone 없는 local string으로 둘 수 없다.
- 대한민국 안전신문고 MVP 범위에서 기본 context가 명확하다.
- explicit source timezone과 제품 context의 충돌을 provenance/review로 남겨 자동 오해석을 방지한다.

## 결정 3. USER_INPUT 기반 사후 각인은 non-blocking notice 대상이다

**최종 선택:** 명시적 provenance 고지

**결정 내용:**

원본 화면에 없던 Timestamp를 USER_INPUT 기반 TimeResolution으로 Report Video에 사후 각인할 경우 사용자에게 사후 표시임을 알린다. 이 고지는 신고 준비를 자동 차단하지 않는다.

**선택 이유:**

- 원본에 존재한 Timestamp와 대신고가 만든 파생 표시를 구분해야 한다.
- 사용자 입력이 원본 증거처럼 오해되는 것을 방지한다.
- Source/Incident Clip은 변경하지 않고 Report Video에만 각인한다는 Architecture 원칙과 맞는다.

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| `OK / NEEDS_REVIEW / UNKNOWN`으로 충분 | 반영 | 상태 3개 유지 | case/web workflow 표현에 추가 enum 불필요 |
| verification과 conflict 분리 승인 | 반영 | 별도 축 유지 | 동시에 성립 가능 |
| `considered[]` summary + Ref면 충분 | 반영 | 원본 Observation 전체 복제 안 함 | case가 Producer 내부 diagnostics를 알 필요 없음 |
| USER_INPUT ref 대상이 불명확 | 반영 | `CorrectionRecord` 직접 참조로 확정 | case에 새 ref entity 소유 책임을 추가하지 않음 |
| `requires_user_notice`만 evidence가 제공 | 반영 | `shown_to_user` 제거 | 실제 UI lifecycle은 CaseView/web 책임 |
| numeric Timestamp confidence 불필요 | 반영 | 최종 numeric confidence 제거 | verification/conflict/provenance로 충분 |
| immutable 새 Resolution + `supersedes_ref` 승인 | 반영 | append-only correction history | case revision 철학과 정합 |

---

# 6. 최종 Contract 핵심 요약

- TimeResolution은 Observation이 아니라 **evidence의 최종 시각 판정 결과**다.
- 상태는 `OK / NEEDS_REVIEW / UNKNOWN`을 사용한다.
- `verification`과 `conflict`는 서로 다른 축이다.
- `considered[]`는 최소 summary + authoritative reference를 보존한다.
- USER_INPUT은 Observation이 아니며 `CorrectionRecord`를 provenance로 참조한다.
- 최종 numeric confidence를 만들지 않는다.
- `resolved.value`는 offset-aware RFC3339다.
- timezone 정보가 없으면 MVP 제품 context `Asia/Seoul (+09:00)`을 사용한다.
- correction/recompute는 새 immutable Resolution을 만들고 `supersedes_ref`로 연결한다.
- USER_INPUT 기반 사후 Timestamp 각인은 non-blocking provenance notice 대상이다.

전체 필드 정의는 Final Data Contract — `TimeResolution v1`을 따른다.

---

# 7. Invariants / 보장사항

1. `status=OK`이면 resolved time이 존재한다.
2. `status=UNKNOWN`에서는 임의의 시각을 생성하지 않는다.
3. `resolved + conflict.exists=true`를 허용한다.
4. resolved가 존재하면 selected input provenance가 존재한다.
5. 최종 time은 offset-aware RFC3339다.
6. `BASE_PLUS_OFFSET`이면 base ref와 offset을 보존한다.
7. USER_INPUT 기반 final time은 `CorrectionRecord`까지 추적 가능하다.
8. `TIME_HINT_EDIT` 자체는 최종 occurred_at source가 아니다.
9. TimeResolution 자체에는 numeric confidence를 생성하지 않는다.
10. 기존 Resolution은 correction/recompute로 overwrite하지 않는다.
11. `shown_to_user`는 TimeResolution 책임이 아니다.
12. USER_INPUT 기반 사후 Timestamp 각인은 non-blocking notice가 필요하다.

---

# 8. 이번 결정의 결과 (Consequences)

## 긍정적 결과

- 시간 후보 관찰과 최종 판정 ownership이 분리된다.
- conflict가 있어도 fallback 시각을 잃지 않고 provenance를 보존할 수 있다.
- case/web이 Timestamp 정책을 복제할 필요가 없다.
- 사용자 correction과 자동 관찰을 명확히 구분한다.
- immutable history로 사용자 수정 전후를 추적할 수 있다.
- timezone 없는 local time을 신고용 확정 시각으로 사용하는 모호성이 사라진다.
- 사후 각인 영상이 원본 Timestamp처럼 오해될 위험을 줄인다.

## 감수하는 비용 / 단점

- `status`, `verification`, `conflict`를 별도 축으로 다뤄 schema가 단일 enum보다 복잡하다.
- `considered[]` snapshot과 원본 reference가 함께 있어 일부 중복 저장이 생긴다.
- CorrectionRecord / Observation reference lookup이 필요하다.
- timezone provenance를 추가로 관리해야 한다.
- correction마다 새 Resolution이 생기므로 저장·reference 관리가 늘어난다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| TimeResolution 전용 완전 별도 status | 공통 UNKNOWN/검토필요 의미를 재발명하고 Consumer 분기를 늘림 |
| VERIFIED/AGREED/CONFLICT 단일 enum | 검증과 충돌은 동시에 존재 가능하므로 단일 축으로 표현 불충분 |
| 사용자 입력을 Observation으로 포장 | Observation Producer 범위와 관찰/확정 경계를 변경함 |
| TimeResolution 전용 UserInput entity 신설 | case가 이미 `CorrectionRecord`를 소유하므로 중복 책임 |
| 원본 Observation 전체를 `considered[]`에 복제 | 불필요한 diagnostics 결합 및 중복/stale 위험 |
| 최종 numeric confidence 생성 | 서로 다른 source confidence를 합칠 근거가 없고 provenance가 더 직접적임 |
| 사용자 수정 시 기존 Resolution overwrite | correction history 및 재현성을 잃음 |
| `shown_to_user`를 TimeResolution에 저장 | evidence가 UI lifecycle을 소유하게 됨 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `Observation<T>` | 자동 시각 후보만 Observation. USER_INPUT은 Producer 범위를 확장하지 않음 | 없음 |
| `CorrectionRecord` | `EVENT_TIME_MANUAL` correction ID가 USER_INPUT provenance로 참조됨 | stable ID가 이미 존재한다는 전제 확인 필요 |
| `EvidenceRecord` | 확정 event_time은 `resolution_ref`를 참조 | 해당 계약 Final에서 정합 확인 |
| `CaseView` | resolved value/review 필요/notice를 safe projection | 기존 Final 구조로 처리 가능 |
| `EvidenceNeeds` | `post_stamp.needed`를 후속 영상 작업 필요성으로 연결 | Evidence 계약 Final에서 정합 확인 |

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

최소 다음 케이스가 필요하다.

- VERIFIED overlay 기반 정상 `OK`
- Filename/Metadata 충돌 + fallback resolved + `NEEDS_REVIEW`
- usable source 없음 → `UNKNOWN`
- USER_INPUT (`EVENT_TIME_MANUAL`) correction 기반 resolution
- 기존 자동 판정 → 사용자 correction → `supersedes_ref`
- timezone 정보 없음 → `Asia/Seoul` product context 적용
- explicit source timezone이 product context와 충돌하는 review case
- USER_INPUT 기반 post-stamp + non-blocking notice

## 구현

**Producer (`evidence`)**

- source priority를 한 곳에서 적용한다.
- provenance와 conflict를 숨기지 않는다.
- USER_INPUT이면 CorrectionRecord를 참조한다.
- timezone source를 기록한다.
- correction/recompute 시 새 Resolution을 생성한다.

**Consumer (`case`)**

- source priority를 재계산하지 않는다.
- `requires_user_notice`/post-stamp notice를 CaseView notice로 projection한다.
- 최신 Resolution 참조와 correction history를 관리한다.

**web**

- raw confidence나 raw source를 재판정하지 않는다.
- CaseView가 제공한 review/notice 의미만 표시한다.

## Evaluation

Draft/Review에서 새 numeric Timestamp confidence 평가는 요구하지 않았다. Eval이 TimeResolution을 검증할 경우 resolved time, source/provenance, conflict/UNKNOWN 표현과 upstream time error를 구분해 다룬다. 새로운 평가 지표는 이 ADR에서 추가하지 않는다.

---

# 12. 변경 규칙

Accepted 이후 계약 의미 변경이 필요하면 다음 절차를 따른다.

문제 발견 → Producer/Consumer 확인 → Data Contract 변경안 → Architecture 영향 확인 → Contract Version 증가 → ADR Supersede 또는 변경 ADR → Mock 갱신

다음 변경은 ADR 변경 대상으로 본다.

- `status / verification / conflict` 의미 변경
- Timestamp source priority 변경
- timezone 기본 정책 변경
- USER_INPUT provenance ownership 변경
- CorrectionRecord가 아닌 새로운 입력 identity 도입
- immutable/supersedes lifecycle 변경
- post-stamp provenance/notice 책임 변경

설명 문구나 예시 수정만으로 계약 의미가 바뀌지 않으면 새 ADR을 요구하지 않는다.

---

# 13. 미해결 사항

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| `CorrectionRecord` stable ID / 직렬화 세부 | TimeResolution은 해당 record를 직접 참조하도록 확정했지만 CorrectionRecord 자체의 최종 필드 형식은 이 Contract 소관이 아님 | `case` — 유소연 | Case/Correction 구현 전 정합 확인 |

위 항목은 TimeResolution의 Architecture Decision을 다시 열지 않으며, 참조 대상 Contract의 세부 직렬화 정합 확인 사항이다.

---

# 14. 최종 한 줄 결정

> **우리는 `evidence`가 자동 시간 Observation과 명시적 사용자 correction을 비교해 source·verification·conflict·timezone provenance를 보존한 immutable `TimeResolution`을 생산하고, `case`가 이를 재판정하지 않고 workflow/CaseView에 투영하도록 계약을 확정한다.**
>