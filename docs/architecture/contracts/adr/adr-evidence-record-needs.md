# ADR-08: ⑧ EvidenceRecord + EvidenceNeeds Data Contract 확정

**Status:** Accepted

**Contract:** `⑧ EvidenceRecord + EvidenceNeeds`

**Producer:** `evidence` — 김준영

**Consumer:** Runtime `case` — 유소연 / Review·Projection `web` — 신유민

**Owner:** 김준영

**결정일:** `2026-09-04`

**관련 Contract Version:** `evidence-record/v1` / `evidence-needs/v1`

**ADR ID:** `ADR-08`

**관련 Architecture Version:** 대신고 모듈 구조 설계 v4

관련 문서:

- [Data Contract Draft — ⑧ EvidenceRecord + EvidenceNeeds](https://app.notion.com/p/Data-Contract-Draft-EvidenceRecord-EvidenceNeeds-3cf7ae78fc6a8199aa90ef1c47e2f6dd?pvs=21)
- [Final Data Contract — ① Observation<T> v1](https://app.notion.com/p/Final-Data-Contract-Observation-T-v1-3d17ae78fc6a81c1a676f436d65d14a6?pvs=21)
- [Final Data Contract — ⑦ TimeResolution v1](https://app.notion.com/p/Final-Data-Contract-TimeResolution-v1-3d17ae78fc6a81b5a898d341a0bd03e0?pvs=21)
- [PlateReadout / OverlayTimeReadout Final Data Contract](https://app.notion.com/p/PlateReadout-OverlayTimeReadout-Final-Data-Contract-3d17ae78fc6a80efab80d6385aadcc51?pvs=21)
- [Final Data Contract — Contract 5 VisualEvidence v1.0](https://app.notion.com/p/Final-Data-Contract-Contract-5-VisualEvidence-v1-0-3d17ae78fc6a81838841df7302a83929?pvs=21)
- [[Final Data Contract] — RecordingTimeline · AssetSpan · TimeSourceCandidate](https://app.notion.com/p/Final-Data-Contract-RecordingTimeline-AssetSpan-TimeSourceCandidate-3d17ae78fc6a8071ba55d44637b5f3d3?pvs=21)
- Module Architecture v4
- Product Spec

---

# 1. 결정 배경(Context)

## Producer가 생성하는 것

`evidence`는 여러 관찰·판독·시간 resolution·사용자 correction을 종합해 현재 사건에 대해 제품이 사용하는 **authoritative confirmed values**를 만든다.

또 confirmed Evidence가 부족하면 추가 관찰/판독이 필요하다는 사실을 `EvidenceNeeds`로 선언한다.

## Consumer가 필요로 하는 것

`case`는:

- source priority/OCR threshold/evidence rule을 재계산하지 않고 confirmed value를 받아야 한다.
- 무엇이 부족한지 machine-readable하게 알아야 한다.
- 필요하면 실제 JobIntent를 발주할 수 있어야 한다.

`web`은 직접 domain contract를 읽지 않고 `CaseView`를 통해 confirmed value, review 필요 여부, action/notice를 표시한다.

## 계약을 고정해야 했던 이유

계약이 없으면:

- Observation과 confirmed Evidence가 섞일 수 있다.
- correction이 과거 값 overwrite로 처리될 수 있다.
- missing value에 UNKNOWN/ERROR 의미가 중복될 수 있다.
- EvidenceRecord가 Requirement/Package/User workflow까지 떠안는 God Object가 될 수 있다.
- evidence가 readout command DTO를 직접 만들어 orchestration 경계를 침범할 수 있다.
- `optional=false`가 신고 blocker와 혼동될 수 있다.
- post-stamp 같은 파생영상 작업이 Evidence 보강 Need와 뒤섞일 수 있다.

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| Observation과 confirmed Evidence 분리 | Module Architecture v4 | EvidenceRecord만 authoritative confirmed-value 경계로 둠 |
| web은 domain contract 직접 소비 금지 | Module Architecture v4 / CaseView Final | Runtime consumer는 case, web은 safe projection |
| 사건시각은 TimeResolution이 authoritative | TimeResolution Final | EvidenceRecord에는 value + ref + status snapshot만 보존 |
| VisualEvidence는 관찰이며 최종 신고 판단이 아님 | VisualEvidence Final | raw VisualEvidence embed 금지, ref만 연결 |
| 번호판 readout은 abstain 가능 | PlateReadout Final | vehicle_number 부재 + PLATE_REREAD Need 허용 |
| Evidence sufficient / Package ready / User reviewed는 서로 다른 상태 | Architecture / Evidence Memo | EvidenceRecord에서 readiness/workflow 제거 |
| evidence는 다른 모듈을 직접 호출하지 않음 | Architecture / Evidence Memo | EvidenceNeeds는 command가 아닌 declarative value |
| 현재 확인된 executable Need는 2종 | Case Memo / Draft | v1 NeedKind를 2개로 닫음 |
| post-stamp는 confirmed time을 파생영상에 표현하는 작업 | TimeResolution Final + PM 결정 | EvidenceNeeds에서 제외하고 Package/DerivedVideo flow로 이동 |

---

# 3. 검토했던 주요 선택지

## 결정 1. EvidenceRecord lifecycle

### A안 — mutable current-state object

Correction 때 같은 Record를 수정한다.

**장점**

- current state 조회가 단순함

**단점**

- 과거 AI 결과·사용자 correction provenance 소실
- audit/replay 어려움

### B안 — immutable snapshot + `supersedes_ref`

Correction/reassemble마다 새 Record를 만든다.

**장점**

- history/provenance 보존
- case_rev/JobRecord/TimeResolution의 append-only 철학과 정합

**단점**

- current pointer 관리 필요

---

## 결정 2. 확정되지 않은 값의 상태 표현

### A안 — EvidenceRecord에 Observation-like status 추가

각 field에 UNKNOWN/ERROR를 다시 넣는다.

**장점**

- 단일 Record 안에서 이유를 볼 수 있음

**단점**

- Observation 상태와 confirmed-value 상태가 중복
- EvidenceNeeds와 역할 겹침

### B안 — confirmed value만 두고 미확정은 부재/null

왜 없는지는 upstream/Needs/CaseView가 설명한다.

**장점**

- EvidenceRecord 의미가 단순하고 authoritative
- UNKNOWN/ERROR 재발명 방지

**단점**

- missing reason을 다른 계약에서 확인해야 함

---

## 결정 3. confirmed field provenance

### A안 — scalar만 저장

값만 저장한다.

**장점**

- 단순

**단점**

- 자동 관찰/정책 mapping/사용자 correction 구분 불가

### B안 — nested `EvidenceValue<T>`

value + source + support_refs + user_corrected를 보존한다.

**장점**

- confirmed value provenance 추적
- correction 표시 가능

**단점**

- schema가 조금 커짐

---

## 결정 4. TimeResolution 연결

### A안 — 전체 TimeResolution embed

**장점**

- self-contained

**단점**

- conflict/considered/provenance를 중복 복제

### B안 — value + ref + status snapshot

**장점**

- downstream 사용성 유지
- TimeResolution authoritative source 유지

**단점**

- 상세 conflict 조회 시 reference lookup 필요

---

## 결정 5. VisualEvidence 연결

### A안 — 전체 embed

**장점**

- 한 Record에서 모든 근거 조회

**단점**

- search observation과 evidence confirmed boundary 약화

### B안 — confirmed snapshot + `visual_evidence_ref`

**장점**

- ownership 선명
- Search 내부 변경 전파 감소

**단점**

- 상세 primitive 조회 시 ref lookup 필요

---

## 결정 6. EvidenceRecord에 readiness 포함 여부

### A안 — READY/4/5 등을 Record에 포함

**장점**

- UI 단순

**단점**

- Requirement/Package/User workflow가 EvidenceRecord에 섞임

### B안 — confirmed Evidence만 소유

**장점**

- 책임 분리

**단점**

- CaseView가 여러 계약을 조합해야 함

---

## 결정 7. EvidenceNeeds container

### A안 — `EvidenceNeed[]`

**장점**

- 단순

**단점**

- 어느 EvidenceRecord 기준인지 알기 어려움

### B안 — `{basis_record_ref, items[]}`

**장점**

- stale 판별 가능
- correction 이후 lineage 명확

**단점**

- wrapper가 하나 늘어남

---

## 결정 8. NeedKind 확장 방식

### A안 — 자유 문자열

**장점**

- 확장 쉬움

**단점**

- case가 모르는 workflow가 runtime에 등장 가능

### B안 — v1 closed enum

`OVERLAY_TIME_OCR | PLATE_REREAD`

**장점**

- case needs_map과 항상 정합
- 새 workflow가 몰래 추가되지 않음

**단점**

- 신규 Need마다 Contract 갱신 필요

### C안 — controlled namespaced string

**장점**

- 확장성

**단점**

- 현재 2개뿐인데 registry 관리가 과함

---

## 결정 9. Need payload

### A안 — kind만 전달

**장점**

- 가장 순수한 value

**단점**

- case가 필요한 input을 다시 찾아야 함

### B안 — semantic `context_refs[]`

**장점**

- public refs만 전달
- evidence가 readout 구현 parameter를 몰라도 됨

**단점**

- role 규약 필요

### C안 — 실제 command DTO

**장점**

- case 구현 단순

**단점**

- evidence가 orchestration을 소유하게 됨
- readout API 변경이 EvidenceNeeds에 전파

---

## 결정 10. `optional` 의미

### A안 — `optional=false = 신고 blocker`

**단점**

- RequirementReport 책임 침범

### B안 — Evidence 보강 필요성만 표현

**장점**

- Requirement severity와 분리

**단점**

- 이름만 보고 오해할 수 있어 문서화 필요

### C안 — optional 제거 후 severity 추가

**단점**

- RequirementReport severity와 다시 혼동 가능

---

## 결정 11. post-stamp를 EvidenceNeeds에 포함할지

### A안 — `POST_STAMP` Need 추가

**장점**

- 모든 후속 작업을 하나의 Need 체계로 볼 수 있음

**단점**

- EvidenceNeeds가 Evidence 확보를 넘어 generic workflow command registry가 됨
- 파생영상 export와 Evidence observation 책임이 섞임

### B안 — Package/DerivedVideo export flow로 분리

**장점**

- Evidence 보강과 파생물 생성을 분리
- TimeResolution/Package ownership과 정합

**단점**

- 후속 실행 흐름이 두 계약으로 나뉨

---

# 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| EvidenceRecord lifecycle | B안 | B안 | case 승인 | 유지 |
| missing value | B안 | B안 | case/web 승인 | 유지 |
| EvidenceValue provenance | B안 | B안 | case 승인 | 유지 |
| TimeResolution 연결 | B안 | B안 | case/web 승인 | 유지 |
| VisualEvidence 연결 | B안 | B안 | case/web 승인 | 유지 |
| readiness 제외 | B안 | B안 | case/web 승인 | 유지 |
| EvidenceNeeds container | B안 | B안 | case 승인 | 유지 |
| NeedKind | B안 closed enum | B안 | case 승인 | 유지 |
| Need payload | B안 semantic refs | B안 | case 방향 동의, readout Final과 정합 확인 | 조건 명확화 |
| `optional` 의미 | B안 | B안 | case/web 승인 | 자동 발주 해석 추가 |
| post-stamp | B안 Package/DerivedVideo | Draft에서는 미결 | PM 최종 결정 | 확정 |

## 결정 1. immutable EvidenceRecord

**최종 선택:** B안

correction/reassemble은 기존 Record를 overwrite하지 않고 새 `record_ref`를 생성하며 필요하면 `supersedes_ref`로 연결한다.

**선택 이유:**

- case_rev/JobRecord/TimeResolution의 append-only lifecycle과 정합
- Consumer case가 승인
- correction provenance/audit 보존 필요

## 결정 2. confirmed values만 Record에 둔다

**최종 선택:** B안

확정하지 못한 값은 부재/null로 두고 upstream UNKNOWN/ERROR를 새 Evidence status로 재생성하지 않는다.

**선택 이유:**

- Observation은 관찰 상태, EvidenceRecord는 confirmed value라는 Architecture 경계 유지
- missing reason은 EvidenceNeeds/CaseView로 전달 가능하다는 Consumer 동의

## 결정 3. `EvidenceValue<T>` provenance envelope

**최종 선택:** B안

confirmed field마다 source/support/user correction provenance를 보존한다.

**선택 이유:**

- Product가 번호판/시각/위치 user correction과 source 추적을 요구
- case는 `user_corrected` 등 필요한 값만 projection 가능

`EvidenceValue<T>` 자체는 공통 Contract로 승격하지 않는다. 현재 다른 Contract에서 실제 재사용 가치가 충분히 확인되지 않았기 때문이다.

## 결정 4. TimeResolution은 최소 snapshot + Ref

**최종 선택:** B안

EvidenceRecord가 timestamp source priority/conflict를 다시 소유하지 않는다.

## 결정 5. readiness는 Requirement/Case 영역으로 분리

**최종 선택:** B안

`EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED`를 EvidenceRecord에 넣지 않는다.

## 결정 6. EvidenceNeeds는 Record-bound declarative container

**최종 선택:** B안

`basis_record_ref`로 어느 Evidence snapshot에서 나온 Need인지 보존한다.

## 결정 7. NeedKind v1은 2개로 닫음

**최종 선택:** B안

```
OVERLAY_TIME_OCR
PLATE_REREAD
```

새 kind는 계약 review/version 변경 없이 runtime에 추가하지 않는다.

## 결정 8. semantic refs만 전달

**최종 선택:** B안

Consumer case의 수정요청은 방향 반대가 아니라 **readout public input과 실제로 맞는지 확인 필요**였다.

Final readout Contract는 PlateReadout/OverlayTimeReadout 입력을 source-derived incident clip/span 계열로 두고 target hint를 optional로 허용하므로, Final에서는:

- `evidence.interval`을 기본 context로 제공
- `evidence.target_hint`는 available한 경우 제공
- case가 이를 readout public input으로 조립

으로 명확화했다.

실제 함수명/threshold/retry는 계약에 넣지 않는다.

## 결정 9. `optional=false`의 실행 의미

**최종 선택:** B안 + PM 해석 확정

`optional=false`는 Requirement BLOCK이 아니라 **현재 Evidence policy상 기본적으로 수행해야 하는 보강 작업**이다.

PM 최종 결정에 따라 현재 revision에서 유효한 `optional=false` Need는 case가 별도 사용자 승인 없이 JobIntent를 자동 발주할 수 있다.

## 결정 10. post-stamp를 EvidenceNeeds에서 제외

**최종 선택:** B안

PM 최종 결정으로 `POST_STAMP/REPORT_VIDEO`는 EvidenceNeeds v1에 넣지 않는다.

이유:

- `OVERLAY_TIME_OCR/PLATE_REREAD`는 confirmed Evidence를 얻기 위한 추가 관찰/판독
- post-stamp는 이미 확정된 occurred_at을 신고용 파생영상에 표현하는 작업
- 따라서 Package/DerivedVideo export orchestration이 소유하는 것이 현재 Architecture 경계와 정합

이 결정에 맞춰 `TimeResolution Final`의 EvidenceNeeds 연결 문구도 정합성 보정했다.

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| immutable Record 승인 | 반영 | `record_ref + supersedes_ref` | append-only lifecycle 정합 |
| missing value는 null/부재 | 반영 | Evidence field status 신설 안 함 | Observation/Needs와 책임 중복 방지 |
| TimeResolution 최소 snapshot | 반영 | `value + ref + status` | 중복 방지 |
| VisualEvidence ref만 | 반영 | raw primitive 미복제 | 관찰/확정 경계 |
| readiness 제외 | 반영 | Requirement/Case로 분리 | 중복 상태 방지 |
| `context_refs`만으로 실제 input 조립 가능한지 확인 요청 | 반영 | interval 기본 + optional target hint 규칙 명시 | readout Final input 의미와 정합 |
| `optional=false` 자동 발주 해석 확인 | 반영 | current revision에서 유효하면 case 자동 JobIntent 가능 | PM 최종 결정 |

---

# 6. 최종 Contract 핵심 요약

- `EvidenceRecord`는 immutable confirmed-value snapshot이다.
- missing confirmed value는 부재/null이다.
- confirmed field는 작은 provenance envelope를 가진다.
- TimeResolution/VisualEvidence 상세는 복제하지 않고 ref로 연결한다.
- Requirement/readiness/User workflow는 EvidenceRecord에서 제외한다.
- `EvidenceNeeds`는 basis Record에 결합된 declarative value다.
- NeedKind v1은 `OVERLAY_TIME_OCR`, `PLATE_REREAD` 두 개다.
- 실제 command args 대신 semantic refs를 제공한다.
- `optional=false`는 Evidence 보강 필요성이고 Requirement BLOCK이 아니다.
- 유효한 non-optional Need는 case가 자동 JobIntent 발주 가능하다.
- post-stamp/export는 EvidenceNeeds가 아니라 Package/DerivedVideo 흐름이다.

---

# 7. Invariants / 보장사항

- EvidenceRecord는 생성 후 의미적으로 mutate하지 않는다.
- 확정되지 않은 값을 placeholder로 만들지 않는다.
- `occurred_at`이 있으면 TimeResolution ref가 있다.
- `vehicle_number` 확정과 영상 내 plate visibility를 동일시하지 않는다.
- `items=[]`을 신고 가능으로 해석하지 않는다.
- NeedKind와 would_fill 매핑을 고정한다.
- `optional=false`를 Requirement BLOCK으로 해석하지 않는다.
- EvidenceNeeds는 Job을 직접 발주하지 않는다.
- stale basis의 Need는 delayed dispatch 전에 재검증한다.
- post-stamp를 EvidenceNeeds kind로 추가하지 않는다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

- 관찰 / 확정 / 보강 / 요건 / 파생물 책임이 분리된다.
- correction history와 provenance가 보존된다.
- case가 evidence policy를 재계산하지 않는다.
- readout 구현 세부가 EvidenceNeeds에 새지 않는다.
- Requirement blocker와 Evidence 보강 Need가 혼동되지 않는다.
- post-stamp가 generic Need 체계로 흡수되는 것을 막는다.

## 감수하는 비용 / 단점

- 여러 Contract reference lookup이 필요하다.
- immutable Record 저장량이 늘어난다.
- case가 current Record pointer와 stale Need를 관리해야 한다.
- 신규 EvidenceNeed workflow 추가 시 Contract 갱신이 필요하다.
- Package/DerivedVideo와 EvidenceNeeds가 별도 흐름이라 orchestration 문서가 한 단계 더 필요하다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| mutable EvidenceRecord | correction/audit provenance 손실 |
| Evidence field별 UNKNOWN/ERROR | Observation/Needs와 상태 중복 |
| TimeResolution/VisualEvidence full embed | ownership/authoritative source 중복 |
| EvidenceRecord readiness | Requirement/Package/User workflow와 책임 중복 |
| 자유 NeedKind | case가 모르는 workflow가 runtime에 등장 가능 |
| 실제 command DTO | evidence가 orchestration/readout 구현을 알게 됨 |
| `optional=false = BLOCK` | RequirementReport 책임 침범 |
| `POST_STAMP` Need | Evidence 관찰 보강과 DerivedVideo 생성의 성격이 다름 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `TimeResolution` | `post_stamp`는 EvidenceNeeds가 아니라 Package/DerivedVideo export로 연결 | Final 문구 정합성 보정 완료 |
| `CaseView` | Evidence raw pass-through 금지, confirmed value/review/action safe projection | 현재 Final 원칙과 정합 |
| `PlateReadout / OverlayTimeReadout` | EvidenceNeeds context refs를 readout source-derived input으로 조립 | Tech Spec adapter 확인 |
| `RequirementReport` | plate/time visibility, readiness, BLOCK 판단을 소유 | 해당 Contract에서 확정 |
| `ReportPackage / DerivedVideo` | post-stamp/export 작업을 소유 | 해당 Contract에서 실행 접합 규칙 명시 |
| `JobRecord / JobExecution` | non-optional Need의 실제 발주·실행 lifecycle | 기존 경계 사용 |

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

최소 포함:

- 모든 confirmed value가 있는 정상 Record
- vehicle_number 부재 + `PLATE_REREAD`
- occurred_at 부재 + `OVERLAY_TIME_OCR`
- user correction 후 superseding Record
- `items=[]`
- stale basis Need
- `optional=false` 자동 발주 가능 사례
- `optional=true` enrichment 사례
- post_stamp가 필요하지만 EvidenceNeeds에는 없는 사례

## 구현

### Producer — evidence

- confirmed 값만 Record에 넣는다.
- Need는 semantic refs와 reason만 제공한다.
- 다른 모듈 함수를 직접 호출하지 않는다.

### Consumer — case

- 새 Record를 current pointer로 반영한다.
- basis/current revision 정합성을 확인한다.
- 유효한 `optional=false` Need는 자동 JobIntent 발주 가능하다.
- Requirement blocker는 RequirementReport만 본다.

## Evaluation

자료에서 확인된 범위에서:

- correction 후 provenance 유지 여부
- missing confirmed value가 placeholder로 채워지지 않는지
- Need kind/would_fill 정합성
- stale Need 오발주 방지
- Observation/Readout 원본과 confirmed Evidence의 lineage 추적 가능성

을 검증할 수 있어야 한다.

---

# 12. 변경 규칙

Accepted 이후 의미 변경은:

문제 발견 → Producer/Consumer 확인 → Contract 변경안 → Architecture 영향 확인 → Contract Version 증가 → ADR Supersede/변경 ADR → Mock 갱신

다음은 ADR 변경 대상이다.

- confirmed-value ownership 변경
- immutable lifecycle 변경
- Need kind 추가/삭제
- `optional` 의미 변경
- Requirement/Package 책임 이동
- command payload를 EvidenceNeeds에 포함

---

# 13. 미해결 사항

현재 Final Contract 기준 **미해결 Architecture Decision 없음**.

다만 실제 readout 함수 인자 변환, Evidence policy table, SafetyReportType registry, DB 저장 구조는 Tech Spec/구현 단계에서 구체화한다.

---

# 14. 최종 한 줄 결정

> **우리는 `evidence`가 사건별 confirmed values를 immutable `EvidenceRecord`로 보장하고, 부족한 Evidence 보강 작업만 `EvidenceNeeds`로 선언하며, `case`가 유효한 non-optional Need를 JobIntent로 조율하도록 계약을 확정한다.**
>