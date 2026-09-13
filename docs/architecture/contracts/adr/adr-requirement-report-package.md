# ADR-10: ⑩ RequirementReport + ReportPackage Data Contract 확정

**Status:** Accepted

**Contract:** `⑩ RequirementReport + ReportPackage`

**Producer:** `evidence` — 김준영

**Consumer:** Runtime `case` — 유소연 / Review·Projection `web` — 신유민

**Owner:** 김준영

**결정일:** `2026-09-04`

**관련 Contract Version:** `requirement-report/v1` / `report-package/v1`

**ADR ID:** `ADR-10`

**관련 Architecture Version:** 대신고 모듈 구조 설계 v4

관련 문서:

- Product Spec
- 대신고 모듈 구조 설계 v4
- Data Contract Draft — RequirementReport + ReportPackage
- Consumer Review — 신유민
- Final Data Contract — ⑩ RequirementReport + ReportPackage v1
- Final Data Contract — EvidenceRecord + EvidenceNeeds v1
- Final Data Contract — TimeResolution v1
- 부록 JobRecord / CaseView Final Data Contract

---

# 1. 결정 배경(Context)

## Producer가 생성하는 것

`evidence`는 confirmed Evidence와 신고용 자산에 현재 신고 정책을 적용해 `RequirementReport`를 만들고, 최종 gate를 통과한 결과를 안전신문고 handoff용 `ReportPackage`로 조립한다.

## Consumer가 필요로 하는 것

`case`는 어떤 단계가 진행 가능한지 판단하고 CaseView를 구성해야 하며, `web`은 신고요건 상태·경고·복사/다운로드/외부 이동 기능을 표시해야 한다. Consumer가 파일 크기, 기한, 번호판/시각 가시성 같은 규칙을 다시 구현해서는 안 된다.

## 계약을 고정해야 했던 이유

계약이 없으면 다음 문제가 생긴다.

- Evidence 충분성, Package 준비 완료, 사용자 검토가 한 상태로 섞일 수 있음
- `WARN`과 실제 blocker가 구분되지 않을 수 있음
- 아직 판단할 수 없는 조건을 BLOCK이나 PASS로 오해할 수 있음
- ReportPackage에 Job/제출 lifecycle이 들어가 evidence와 case ownership이 중복될 수 있음
- web이 신고 규칙의 수치와 계산식을 다시 구현할 수 있음
- 신고문/Package가 자유생성 결과에 결합될 수 있음

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| RequirementReport는 PASS/WARN/BLOCK 중심의 신고 규칙 판정 Contract | Module Architecture v4 | 개별 check와 overall을 구조화하고 Consumer 재판정을 금지 |
| confirmed Evidence와 신고영상의 실제 가시성은 별개 | Architecture / Evidence 경계 | 번호판 문자열·occurred_at 존재만으로 final requirement를 PASS 처리하지 않음 |
| 원본 Source와 신고용 파생물은 분리 | Module Architecture v4 | Report Video를 derived asset reference로 관리 |
| web은 domain Contract를 직접 소유·재계산하지 않음 | Module Architecture v4 / CaseView | Runtime routing을 evidence → case → CaseView → web으로 유지 |
| Package/신고문은 confirmed Evidence에서 결정론적으로 생성 | Package/Handoff 조사 | 고정 template + `template_ref` 사용, LLM 자유생성 제외 |
| 자동 제출·신고자 개인정보 저장은 MVP 범위 밖 | Product/Evidence 정책 | ReportPackage에 인증·PII·SUBMITTED lifecycle을 넣지 않음 |
| EvidenceNeeds는 Evidence 보강용 관찰/판독 need만 소유 | EvidenceRecord + EvidenceNeeds Final | post-stamp/Report Video를 Package/DerivedVideo 흐름에서 처리 |

---

# 3. 검토했던 주요 선택지

## 결정 1. RequirementReport lifecycle

### A안 — 하나의 mutable Report를 단계별 갱신

**장점**

- 하나의 ID만 관리하면 됨

**단점**

- 어떤 Evidence/asset 상태에서 판정했는지 이력이 사라짐
- deadline 등 시간 의존 판정의 재현성이 떨어짐

### B안 — 동일 schema를 scope별 immutable snapshot으로 반복 생성

`scope=EVIDENCE | FINAL_PACKAGE`

**장점**

- 같은 check 구조를 재사용하면서 평가 시점과 basis를 보존
- immutable lifecycle과 일관

**단점**

- latest Report 선택이 필요할 수 있음

### C안 — EvidenceRequirementReport / PackageRequirementReport 분리

**장점**

- 단계별 타입이 분명함

**단점**

- 거의 동일한 schema를 두 개 관리하며 신규 Contract를 불필요하게 늘림

---

## 결정 2. 판정 불가 상태 표현

### A안 — `PASS / WARN / BLOCK`만 사용

**장점**

- Architecture의 기존 표현을 그대로 유지

**단점**

- 정보 부족으로 판단 불가인 경우를 BLOCK 또는 다른 값에 억지로 넣어야 함

### B안 — `UNKNOWN` 추가

**장점**

- 실제 규칙 위반/불충족인 BLOCK과 판단 자체가 성립하지 않은 상태를 구분
- Web 안내가 명확해짐

**단점**

- Architecture의 3개 상태 표현보다 enum이 하나 늘어남

---

## 결정 3. Overall aggregation

### A안 — Consumer가 checks를 보고 재계산

**장점**

- Contract가 단순해 보임

**단점**

- backend/web에서 같은 규칙을 중복 구현할 수 있음

### B안 — Producer가 `overall`까지 확정

v1 precedence:

`BLOCK > UNKNOWN > WARN > PASS`

**장점**

- Consumer가 신고 rule을 다시 해석하지 않음
- 테스트 가능하고 일관된 gate 제공

**단점**

- aggregation 의미가 Contract의 일부가 됨

---

## 결정 4. EVIDENCE_SUFFICIENT 표현

### A안 — 별도 boolean/state 저장

**장점**

- workflow 코드에서 바로 읽기 쉬움

**단점**

- RequirementReport와 동일 판단을 두 곳에서 소유하여 모순 가능

### B안 — RequirementReport에서 gate 파생

`scope=EVIDENCE`이고 `overall∈{PASS,WARN}`이면 sufficient로 해석한다.

**장점**

- Source of Truth 하나 유지

**단점**

- workflow가 파생 규칙을 알아야 함

---

## 결정 5. ReportPackage lifecycle

### A안 — BUILDING/INCOMPLETE/READY/ERROR 상태를 가진 Package

**장점**

- Package 하나로 진행상태 표시 가능

**단점**

- Job lifecycle과 Package domain 의미가 섞임
- `PACKAGE_READY`와 중복 상태기계 발생

### B안 — Ready-only immutable Package

**장점**

- Package 존재 의미가 강함
- 준비/실패는 RequirementReport와 Job/CaseView가 표현

**단점**

- 준비중 UI는 Package만 보고 표현할 수 없음

---

## 결정 6. PACKAGE_READY 표현

### A안 — 별도 field/state 저장

**장점**

- 조회가 단순함

**단점**

- FINAL_PACKAGE report 및 실제 Package 존재와 중복

### B안 — final report + Package 존재에서 파생

`FINAL_PACKAGE overall∈{PASS,WARN} + ReportPackage 존재`

**장점**

- 중복 authoritative state 제거

**단점**

- workflow에서 파생 조건을 적용해야 함

---

## 결정 7. Package에 Evidence를 얼마나 복제할지

### A안 — `EvidenceRecordRef`만

**장점**

- 중복 최소

**단점**

- handoff UI가 EvidenceRecord를 다시 펼쳐야 하고 생성 시점 snapshot이 없음

### B안 — Ref + handoff 최소 snapshot

**장점**

- Package가 handoff bundle로 self-contained
- correction 전후 Package 재현 가능

**단점**

- confirmed value 일부가 의도적으로 중복됨

### C안 — EvidenceRecord 전체 embed

**장점**

- 완전 self-contained

**단점**

- domain provenance 과다 복제, 결합도 증가

---

## 결정 8. Handoff lifecycle ownership

### A안 — Package가 OPENED/SUBMITTED 등 상태 소유

**장점**

- 하나의 객체에서 외부 진행상태 확인

**단점**

- 사용자의 외부 행동을 evidence가 소유하게 됨
- 실제 제출 여부 관찰 신뢰성이 낮음

### B안 — supported capability만 제공

`DOWNLOAD_ASSETS / COPY_FIELDS / OPEN_DESTINATION`

**장점**

- evidence와 case ownership 유지
- Package immutable 유지

**단점**

- 실제 진행상태는 CaseView를 별도로 봐야 함

---

# 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| RequirementReport lifecycle | scope별 immutable snapshot | B안 | 승인 | 유지 |
| UNKNOWN 상태 | 추가 | B안 | 신유민 승인 | 유지 + PM 확정 |
| overall aggregation | `BLOCK > UNKNOWN > WARN > PASS` | B안 | 구조 승인 | 유지 |
| readiness 점수 | 제거, `overall + checks[]` 사용 | 제거 | 승인 | 유지 |
| EVIDENCE_SUFFICIENT | EVIDENCE report에서 파생 | 파생 추천 | 구조상 충돌 없음 | PM 확정 |
| ReportPackage lifecycle | Ready-only immutable object | B안 | 승인 | 유지 |
| Package 생성 gate | FINAL_PACKAGE PASS/WARN만 허용 | B안 | 승인 | 유지 |
| PACKAGE_READY | final report + Package 존재로 파생 | 파생 추천 | 구조상 충돌 없음 | PM 확정 |
| Package payload | Evidence Ref + 최소 handoff snapshot | B안 | 승인 | 유지 |
| 신고문 provenance | 문자열 + `template_ref` | B안 | 승인 | 유지 |
| Handoff lifecycle | capability만 Package에 포함 | B안 | 승인 | 유지 |
| post-stamp | Package/DerivedVideo flow | Draft에서 미결 | 선행 Contract 결정과 정합 | 후속 결정 반영 |

## 결정 1. `UNKNOWN`을 공식 outcome으로 포함

**최종 선택:** B안

**결정 내용:** `PASS / WARN / BLOCK / UNKNOWN`을 사용한다.

**선택 이유:** Consumer Review에서 신유민은 정보 부족과 실제 blocker를 구분해야 Web 표시와 사용자 안내가 명확하다고 승인했다. PM/Owner도 해당 구분을 채택했다.

## 결정 2. EVIDENCE_SUFFICIENT는 파생 gate

**최종 선택:** 별도 state를 만들지 않음.

```
scope=EVIDENCE AND overall∈{PASS,WARN}
→ EVIDENCE_SUFFICIENT
```

**선택 이유:** RequirementReport가 규칙 판정의 authoritative source이므로 동일 판단을 boolean으로 중복 저장하지 않는다.

## 결정 3. PACKAGE_READY는 파생 gate

**최종 선택:** 별도 state를 만들지 않음.

```
scope=FINAL_PACKAGE
AND overall∈{PASS,WARN}
AND ReportPackage exists
→ PACKAGE_READY
```

**선택 이유:** Ready-only Package와 final requirement 판정으로 이미 필요한 사실이 존재하므로 별도 상태 저장은 중복이다.

## 결정 4. post-stamp는 EvidenceNeeds가 아닌 Package/DerivedVideo flow

**최종 선택:** `POST_STAMP`를 EvidenceNeeds v1에 추가하지 않는다.

**선택 이유:** 선행 `EvidenceRecord + EvidenceNeeds Final`에서 EvidenceNeeds는 confirmed Evidence를 보강하는 관찰/판독 Need로 제한했다. 사후 Timestamp 각인은 이미 확정된 정보를 신고용 파생영상에 표현하는 작업이므로 Package/DerivedVideo orchestration에서 처리한다.

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final 변경 | 이유 |
| --- | --- | --- | --- |
| EVIDENCE/FINAL_PACKAGE를 동일 schema + scope로 구분 가능 | 반영 | `scope` 2종 유지 | 중복 Contract 없이 동일 check 구조 재사용 |
| 정보 부족은 BLOCK과 달라 UNKNOWN이 필요 | 반영 | `UNKNOWN` 공식 추가 | UI/사용자 안내 의미 구분 |
| 4/5 readiness 점수는 부적절 | 반영 | 점수 제거 | 중요도가 다른 checks를 단순 개수로 축약하지 않음 |
| 수치 check에는 actual/limit/unit이 유용 | 반영 | optional `measurement` | 설명 가능성 확보, policy 재계산은 금지 |
| FINAL_PACKAGE UNKNOWN이면 Package 보류 | 반영 | Package 생성 gate에 적용 | 준비 완료를 보장할 수 없음 |
| ReportPackage는 READY-only로 충분 | 반영 | Package status 제거 | Job/CaseView lifecycle과 분리 |
| Evidence 전체가 아니라 handoff 최소 snapshot이면 충분 | 반영 | `report_inputs` 최소 snapshot | web handoff에 필요한 값만 제공 |
| PASS/WARN final report만 Package 허용 | 반영 | 생성 gate 확정 | WARN은 사용자 고지와 함께 진행 가능 |
| 신고문 template provenance 필요 | 반영 | `template_ref` 필수 | 결정론적 재현성 |
| Package는 supported actions만 제공 | 반영 | submission lifecycle 제외 | case ownership 유지 |

---

# 6. 최종 Contract 핵심 요약

- `RequirementReport`는 `EVIDENCE / FINAL_PACKAGE` scope별 immutable 판정 snapshot이다.
- outcome은 `PASS / WARN / BLOCK / UNKNOWN`이다.
- `UNKNOWN`은 판단 불가이며 BLOCK과 다르다.
- `overall`은 Producer가 `BLOCK > UNKNOWN > WARN > PASS`로 결정한다.
- readiness percentage를 사용하지 않는다.
- `EVIDENCE_SUFFICIENT`는 EVIDENCE scope 결과에서 파생한다.
- `ReportPackage`는 final report가 PASS/WARN일 때만 생성하는 ready-only immutable bundle이다.
- `PACKAGE_READY`는 final report + Package 존재에서 파생한다.
- Package에는 handoff에 필요한 confirmed 값 snapshot만 복제한다.
- 신고문은 고정 template 기반이며 `template_ref`를 보존한다.
- Package는 handoff capability만 제공하고 제출 lifecycle을 소유하지 않는다.
- post-stamp는 Package/DerivedVideo flow에서 처리한다.

---

# 7. Invariants / 보장사항

1. RequirementReport는 생성 후 mutate하지 않는다.
2. `overall`은 `checks[]`와 모순될 수 없다.
3. `overall=PASS`이면 모든 check가 PASS다.
4. `overall=WARN`이면 BLOCK/UNKNOWN check가 없다.
5. `overall=UNKNOWN`은 실행 실패를 의미하지 않는다.
6. Requirement engine 실행 실패 시 정상 Report를 만들지 않는다.
7. `FINAL_PACKAGE overall∈{BLOCK,UNKNOWN}`이면 ReportPackage를 만들지 않는다.
8. ReportPackage가 존재하면 참조한 `requirement_report_ref`는 FINAL_PACKAGE PASS 또는 WARN이어야 한다.
9. ReportPackage에는 USER_REVIEWED/SUBMITTED 상태가 없다.
10. 신고 규칙 숫자는 Contract schema가 아니라 `policy_ref`로 추적한다.
11. 신고문은 `template_ref`까지 추적 가능해야 한다.
12. source asset과 derived report asset을 동일하게 취급하지 않는다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

- Evidence 충분성, Package 준비, 사용자 검토의 책임이 분리된다.
- 판단 불가와 실제 blocker를 구분할 수 있다.
- Consumer가 신고 규정을 재구현하지 않는다.
- immutable evaluation/history를 유지할 수 있다.
- Package 존재 의미가 명확해진다.
- 신고 규정 숫자 변경이 Contract schema 변경으로 번지지 않는다.
- deterministic handoff snapshot으로 correction 전후 결과를 재현할 수 있다.

## 감수하는 비용 / 단점

- 같은 RequirementReport schema를 단계별로 여러 번 생성한다.
- Consumer/case는 scope와 최신 Report를 구분해야 한다.
- `UNKNOWN`이 추가되어 상태 분기가 하나 늘어난다.
- EVIDENCE_SUFFICIENT/PACKAGE_READY가 저장 field가 아니므로 workflow가 파생 규칙을 알아야 한다.
- ReportPackage가 일부 Evidence 값을 의도적으로 중복 snapshot한다.
- 준비중/실패 상태를 보려면 Package 외에 Job/CaseView를 함께 봐야 한다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| mutable RequirementReport | 평가 시점/basis/history 소실 |
| RequirementReport를 두 Contract로 분리 | 동일 구조 중복과 과설계 |
| UNKNOWN 없이 BLOCK으로 통합 | 불충족과 판단 불가의 의미가 다름 |
| readiness 4/5 점수 | Requirement 중요도와 gate 의미를 왜곡 |
| 별도 evidence_sufficient boolean | RequirementReport와 authoritative 상태 중복 |
| 상태를 가진 incomplete Package | Job lifecycle과 Package 의미 혼합 |
| 별도 package_ready boolean | final report + Package 존재와 중복 |
| EvidenceRecord 전체 embed | 과도한 domain 정보 복제·결합도 증가 |
| Package가 SUBMITTED 상태 소유 | 외부 사용자 행동을 evidence가 소유하게 됨 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `EvidenceRecord` | confirmed 값의 Source of Truth로 사용 | 없음 |
| `EvidenceNeeds` | post-stamp/export를 포함하지 않는 경계 유지 | 없음 |
| `TimeResolution` | `post_stamp` 정책 결과가 DerivedVideo 생성 입력이 됨 | 없음 |
| `CaseView` | Requirement overall/check notice, Package availability/action projection 필요 | CaseView 구현 시 반영 |
| `JobRecord / JobExecution` | Report Video/Package assembly lifecycle 표현 | 구현 mapping 필요 |
| Global Contract Index | Draft ⑨를 Architecture v4의 ⑩으로 통일 | 문서 인덱스에서 통일 |

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

반드시 포함할 상태:

- EVIDENCE PASS/WARN/BLOCK/UNKNOWN
- FINAL_PACKAGE PASS/WARN/BLOCK/UNKNOWN
- measurement가 있는 수치 check
- WARN 기반 정상 ReportPackage
- optional plate image 없음
- post-stamped Report Video Package
- Evidence correction 후 superseded Report/Package
- BLOCK/UNKNOWN에서 Package 부재

## 구현

Producer:

- checks와 overall을 deterministic policy로 생성
- policy/template/evaluated_at provenance 보존
- final gate를 통과한 경우에만 Package 생성

Consumer/case:

- overall을 재계산하지 않음
- EVIDENCE_SUFFICIENT/PACKAGE_READY를 정의된 파생 gate로 사용
- Requirement/Package를 CaseView safe projection으로 변환

web:

- policy 수치를 재계산하지 않음
- WARN/UNKNOWN/BLOCK 의미를 구분해 표시
- supported action만 실행 UI로 사용

## Evaluation

새 평가 metric은 추가하지 않는다. Contract/E2E test에서는 최소한 outcome aggregation, Package 생성 gate, template/policy provenance, BLOCK/UNKNOWN Package 미생성을 검증한다.

---

# 12. 변경 규칙

문제 발견

→ Producer / Consumer 확인

→ Data Contract 변경안 작성

→ Architecture 영향 확인

→ Contract Version 증가

→ ADR Supersede 또는 변경 ADR 작성

→ Mock Dataset 갱신

다음은 ADR/Contract 변경 대상이다.

- outcome enum/의미 변경
- aggregation precedence 변경
- scope 의미 변경
- EVIDENCE_SUFFICIENT/PACKAGE_READY 파생 정의 변경
- Package 생성 gate 변경
- Package 필수 snapshot 의미 변경
- Producer/Consumer ownership 변경
- submission lifecycle을 Package에 포함하도록 변경

신고 한도 수치, template 문구처럼 Contract 의미를 바꾸지 않는 정책 데이터 변경은 `policy_ref` / `template_ref` 버전으로 관리한다.

---

# 13. 미해결 사항

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| 전체 신고 정책 rule data의 실제 제한 수치/세부 조합 | Contract 의미가 아니라 운영 정책 데이터이며 추가 공식 확인 가능 | evidence / PM | policy table 확정·갱신 시 |

이는 Contract Architecture Decision의 미해결이 아니라 **policy data 갱신 항목**이다. 현재 Final Contract 기준 추가 미해결 Architecture Decision은 없다.

---

# 14. 최종 한 줄 결정

> **우리는 `evidence`가 신고요건을 scope별 immutable `RequirementReport`로 판정하고, 최종 `PASS/WARN` 결과와 신고용 파생 자산이 준비된 경우에만 ready-only `ReportPackage`를 생성하여 `case → CaseView → web`이 안전한 handoff에 사용하도록 계약을 확정한다.**
> 

---

# Contract 번호 정합성 메모

초기 Draft는 ⑨로 작성됐지만 Module Architecture v4의 Core Contract index는 이 계약을 ⑩으로 정의한다. Final/ADR은 Architecture Source of Truth에 맞춰 **⑩**으로 통일한다.