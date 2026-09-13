# evidence + 공통 Runtime/Ops Architecture Input Memo

> **성격:** 모듈 구조 설계 v4(`docs/architecture/module-architecture.md`) 작성의 근거가 된 Owner 자료조사 메모다. **조사 결과이지 결정이 아니다.** v4에 반영되지 않은 제안은 제안 상태로 남아 있고, 결정은 v4와 이 모듈의 `decisions/`에서만 한다. 문서 안의 `v3 §N`·`테크스펙 §N` 인용은 작성 당시(v3) 번호다.

# `evidence` + 공통 Runtime/Ops Architecture Input Memo

**Owner:** 김준영 (PM)

**관련 모듈:** `case`, `recording`, `readout`, `search`, `web`, `eval`, 공통 Runtime/Ops

**근거 자료:**

- `대신고 모듈 구조 설계 v3`
- `대신고 모듈 기반 역할 배정안 v1`
- `안전신문고 실제 신고 요건 및 초기 4종 유형 매핑 조사`
- `Timestamp / Evidence Policy — 사건 발생시각을 어떻게 확보하고 신고영상에 표시할 것인가`
- `신고문 / Package / Handoff — 확정된 증거를 실제 신고 가능한 형태로 어떻게 넘길 것인가`
- `대신고 백엔드 Runtime · Ops 고도화 설계 v1`

R&R상 `evidence`는 **확정값·발생시각 최종 판정·요건 검사·규정표·신고문·꾸러미·handoff**, 공통 기반/운영은 **작업 큐·비용 장부·마스킹 로거·CI/CD·테스트·운영 시나리오**를 담당한다.

---

## 1. 현재 추천 결론

### 1) `evidence`의 현재 모듈 경계는 유지한다

**결론:** `evidence`는 여러 관찰값을 받아 **시스템에서 유일한 확정값을 만들고**, 신고요건을 검사하며 `ReportPackage`를 결정론적으로 생성하는 순수 로직 영역으로 유지한다.

**근거:** v3는 `EvidenceRecord`를 유일한 확정값으로 정의하고, `evidence`가 다른 모듈을 호출하지 않으며 필요한 추가 작업은 `EvidenceNeeds`라는 값으로만 반환하도록 한다.

**Architecture 영향:** 없음. 핵심 경계 유지.

---

### 2) Timestamp는 `수집`과 `판정`을 계속 분리하되 계약은 보강한다

**결론:** 시간 후보는 `recording`·`readout`에서 수집하고, 어느 시각을 사용할지는 `evidence`만 판정한다. 시각은 임의 생성하지 않고 **source + verification + 충돌 + 계산 provenance**를 보존한다.

**근거:** metadata는 수정 가능하므로 촬영시각의 절대적 증명이 아니며, 조사 결과는 임의 confidence 점수보다 `VIDEO_OVERLAY / FILE_METADATA / FILENAME / USER_INPUT` 등의 출처와 `AGREED / UNVERIFIED / CONFLICT / UNKNOWN` 상태를 남기는 방식을 권장한다.

**Architecture 영향:** **있음.** 현 v3 `TimeResolution` 예시의 숫자형 `confidence` 사용 방식은 재검토 필요.

---

### 3) `Visual Event`·안전신문고 `Report Type`·위반행위 표현을 동일 값으로 취급하지 않는다

**결론:** 초기 4종 사건 관찰값과 실제 안전신문고 신고유형은 별도 개념으로 유지한다. 초기 3종은 `교통위반(고속도로 포함)`, 안전모 미착용은 `이륜차 위반`으로 매핑한다.

**근거:** 안전신문고 UI 구조상 Visual Event, 신고 유형, 구체적 위반행위는 서로 다른 단계다.

**Architecture 영향:** **있음.** `EvidenceRecord`/`ReportPackage`에서 세 값을 혼동하지 않는 계약이 필요.

---

### 4) 신고 준비 상태를 하나의 `READY_TO_REPORT`로 뭉치지 않는다

**결론:** 최소한

`EVIDENCE_SUFFICIENT` → `PACKAGE_READY` → `USER_REVIEWED`

를 개념적으로 분리한다.

**근거:** 증거 자체는 충분하지만 파일 용량 문제로 Package가 준비되지 않을 수 있고, Package가 준비됐지만 사용자가 아직 최종 검토하지 않았을 수도 있다.

**Architecture 영향:** **있음.** 단, `USER_REVIEWED`의 소유자는 아래 충돌 항목에서 별도 결정 필요.

---

### 5) 신고문·Package·Handoff는 AI 생성/자동제출 영역으로 확장하지 않는다

**결론:** 신고문은 **확정 Evidence → 고정 Template**, Package는 파일 + 구조화 입력값 + provenance로 만든다. 안전신문고 자동입력·자동제출 및 신고자 개인정보 저장은 MVP 범위에서 제외한다.

**근거:** Handoff 경계는 다운로드·복사·안전신문고 열기까지이며 인증·인적사항·최종 제출은 사용자 영역이다.

**Architecture 영향:** 없음. 기존 경계를 더 명확히 함.

---

### 6) 공통 Runtime은 Modular Monolith를 유지하면서 `FastAPI + DB Queue + Worker 1`로 구체화한다

**결론:** 긴 작업은 HTTP 요청에서 처리하지 않고 `JobRecord` 생성 후 `202 Accepted`, Worker가 처리한다. 공통 기반은 도메인 모듈이 아니라 DB/Job/Logging/Usage/Config만 담당한다.

**근거:** Runtime 조사에서 단일 배포, FastAPI 1 + Worker 1 + MySQL 1 구조를 결정했으며 `common/`은 새 도메인 모듈이 아니라고 명시한다.

**Architecture 영향:** **있음.** v3의 DB 선택 가정은 수정 필요.

---

## 2. 확인된 기술적 제약

| 제약 | 근거 | Architecture/Data Contract 영향 |
| --- | --- | --- |
| 위반 전·위반·위반 후 장면과 번호판 식별이 필요 | 경찰민원24 조사 | `RequirementReport`에서 별도 check 필요. 전·후 몇 초인지는 공식 규칙 아님 |
| `occurred_at`과 증거영상 내 시각 표시 여부는 다른 상태 | 안전신문고 UI | `occurred_at_confirmed`와 `evidence_time_visible` 분리 필요 |
| OCR 문자열 확정과 영상에서 번호판이 실제 식별되는 것은 다름 | 신고요건 조사 | `vehicle_number_confirmed` / `plate_visible_in_evidence` 분리 필요 |
| 신고기한은 단순 `+48h`가 아님 | 초일 불산입 + 주말·공휴일 연장 | deadline 계산 로직/상태 필요 |
| 기한 초과는 현재 조사상 hard submission blocker로 두지 않음 | 제품 정책상 warning 권장 | PASS/FAIL만으로 표현하면 부족할 수 있음 |
| 첨부 제한 | 이미지 30MB, 동영상 130MB, 총 180MB | `RequirementReport`의 규정 데이터 |
| 첨부 개수 제한은 존재하지만 정확한 조합 규칙 미확정 | 실제 UI 조사 | 현재 hard schema 값으로 확정 금지 |
| metadata는 immutable한 촬영시각 증명이 아님 | FFmpeg로 변경 가능 | 시간 후보에 provenance/verification 필수 |
| metadata 기반 사후 timestamp는 조건부 지원 | 공식 인정은 미확인, 실사용 관행은 확인됨 | `post_stamp_allowed`/고지 정보 필요 |
| 원본과 신고용 파생본은 분리 | 원본 덮어쓰기 금지, 원본 동시 제출은 선택 | `source_ref`와 `derived_ref` 혼동 금지 |
| 안전신문고 앱이 업로드 과정에서 재압축할 수 있음 | 최종 서버 파일 hash 동일성 보장 불가 | 대신고 export lineage만 보장 |
| 긴 작업은 비동기 실행 | FastAPI → JobRecord → 202 → Worker | `JobRecord`가 모든 장시간 작업의 공통 실행 계약 |
| 늦게 도착한 결과는 현재 상태를 덮으면 안 됨 | `case_rev` 불일치 → `STALE` | 모든 Job 결과에 revision 연계 필요 |
| 외부 API 비용은 호출 단위로 기록 필요 | 별도 `UsageRecord` | 평가/운영을 위해 비용·latency 보존 |
| 로그에 번호판/GPS/영상/API payload 원문 금지 | allowlist logging | Contract 원문과 운영 로그를 분리 |
| 업로드/storage 전략은 아직 확정 불가 | 실제 블랙박스 실측 필요 | 파일 계약은 위치가 아니라 Ref 중심으로 유지해야 함 |

---

## 3. 현재 Module Architecture에 미치는 영향

### 그대로 유지 가능한 것

- `evidence`만 확정 Evidence를 소유한다.
- `recording`/`readout`은 관찰값만 생산한다.
- `case`만 작업을 발주한다.
- `EvidenceNeeds`는 명령이 아니라 값이다.
- `RequirementReport`와 `ReportPackage`는 재계산 가능한 파생값이다.
- `evidence`는 AI 모델·OCR·ffmpeg·사용자 진행 흐름을 모른다.
- 원본과 파생영상을 분리한다.
- 실제 안전신문고 제출은 사용자가 한다.

### 수정 검토가 필요한 것

#### A. `TimeResolution`의 confidence 표현

**현재 구조:** v3 예시는 최종 시각에 `confidence: 0.82`를 포함한다.

**조사 결과:** metadata 자체의 신뢰도를 임의 숫자로 표현하기보다 출처·독립 출처 간 일치·충돌 상태를 보존하는 것이 적절하다고 정리됨.

**왜 검토가 필요한가:** `0.82`가 객관적으로 무엇을 의미하는지 근거가 없음.

**영향받는 모듈:** `recording`, `readout`, `evidence`, `web`.

#### B. 신고 준비 상태

**현재 구조:** v3 예시는 `state = READY_WITH_WARNINGS`, `readiness = 4/5` 형태.

**조사 결과:** Evidence 충분 여부 / Package 준비 여부 / 사용자 최종확인을 분리할 필요가 있음.

**왜 검토가 필요한가:** 증거 부족, 파일 생성 실패, 사용자 workflow 상태가 서로 다른 실패 경계다.

**영향받는 모듈:** `evidence`, `case`, `web`.

#### C. 신고유형 계약

**현재 구조:** `visual_event` 및 `report_type`가 존재하지만 일부 예시는 구체적 위반행위와 안전신문고 신고유형의 경계가 모호하다.

**조사 결과:** `Visual Event → SafetyReport Report Type → 구체적 위반행위`는 서로 다른 개념.

**왜 검토가 필요한가:** UI dropdown 값과 AI 관찰 결과를 같은 enum으로 만들면 책임이 섞인다.

**영향받는 모듈:** `search`, `evidence`, `case`, `web`.

#### D. DB 제품

**현재 구조:** v3는 `SQLite → 필요하면 PostgreSQL`을 열린 결정으로 둠.

**조사 결과:** Runtime/Ops에서는 처음부터 `MySQL 8.4 LTS + InnoDB` 사용으로 결정. DB Queue의 row-level claim도 MySQL에서 가능하다고 확인함.

**왜 검토가 필요한가:** v4의 공통 기반 설명을 최신화해야 함.

**영향받는 모듈:** 공통 Runtime, `case`.

#### E. `JobRecord` 확장

**현재 구조:** v3의 `JobRecord`는 발주·비용·실패·fingerprint 중심.

**조사 결과:** `STALE`, lease/heartbeat, `available_at`, progress, masked error 및 별도 `UsageRecord`가 추가됨.

**왜 검토가 필요한가:** 복구·재시도·비용 측정을 위해 공통 실행 계약이 커짐.

**영향받는 모듈:** `case`, 공통 Runtime, 모든 장시간 작업 생산자.

### 판단 불가

- 정확한 첨부파일 **개수** 제한.
- 전체 원본/부분 원본/proxy 중 실제 서버 업로드 전략.
- S3/Object Storage 사용 범위.
- proxy 해상도/FPS/bitrate.
- 실제 1시간 영상 disk/network/latency 수치.
- Managed Source의 정확한 보관기간.

---

## 4. 접합부 / Data Contract에 영향을 주는 내용

| 상대 모듈 | 방향 | 필요한/제공하는 정보 | 조사에서 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| `recording` | `recording → evidence` | 시간 후보 배열, source, 기준시각/anchor, source asset ref | metadata/filename은 후보일 뿐 확정값 아님 | `TimeSourceCandidate`가 verification까지 주는지, raw observation만 주는지 |
| `readout` | `readout → evidence` | `PlateReadout`, `OverlayTimeReadout`, 근거 frame ref, abstain/실패 상태 | UNKNOWN과 ERROR가 다르고 번호판은 틀린 확정보다 abstain 중요 | `plate_visible_in_evidence`를 누가 관찰값으로 생산할지 |
| `search` | `search → evidence` | 선택 사건의 `visual_event_type`, 근거 참조 | AI 관찰과 신고유형/법적 판정은 별도 | Visual Event enum과 Report Type enum의 정확한 경계 |
| `case` | `case → evidence` | `selection_ref/rev`, 사용자 correction, 수집된 observations | 선택의 소유자는 `case`; 선택 변경 시 Evidence 무효화 | correction 입력 형식, `selection_rev`/`case_rev` 관계 |
| `case` | `evidence → case` | `EvidenceNeeds[]` | `evidence`가 직접 작업 발주 금지 | `kind`, `why`, `would_fill`, `optional`의 최종 enum/형식 |
| `web/case` | `evidence → CaseView → web` | Evidence 검토상태, requirement 결과, ReportPackage, warning | 최상위 구조상 web은 case만 호출함 | v3의 “web이 evidence consumer”가 **직접 호출**인지 단순 논리 소비인지 명확화 |
| `recording` | `recording → evidence` | `DerivedVideoRef`, bytes, source range, transformations | 원본/파생본 분리, 최종 SafetyReport 저장본 hash 동일성 보장 불가 | 실제 파일 객체 대신 어떤 Asset Ref를 전달할지 |
| `evidence/web` | `evidence → web` | report type, location display/search keyword, title, description, vehicle number, occurred_at, attachment | PC에는 title, mobile에는 없음; 하나의 Package 공유 | 채널별 optional 여부를 Package에 둘지 Handoff adapter에 둘지 |
| 공통 Runtime | `case ↔ common/jobs` | `JobRecord`, fingerprint, status, retry/lease/progress | domain상 Owner는 `case`, 물리 queue infra는 common | **도메인 데이터 소유권과 DB/queue 구현 소유권을 구분해 명문화** |
| 각 실행 모듈 | `module → common/usage` | provider/model/operation/input duration/bytes/tokens/latency/cost | Job당 여러 외부 호출 가능 | `UsageRecord` 생성 책임과 `JobRecord.cost_krw` 집계 시점 |
| 각 실행 모듈 | `module → common/jobs` | `impl_ref` | fingerprint는 구현 변경 시 stale cache를 막아야 함 | 각 모듈이 opaque `impl_ref`를 어떻게 제공할지 |

**중요:** `Observation<T>`는 계속 공통 핵심 계약으로 유지할 가치가 있다. 현재 v3는 관찰값을 immutable한 `value + source + status + evidence_ref + produced_by` 봉투로 정의하고, `UNKNOWN`과 `ERROR`도 구분한다.

---

## 5. 열린 결정

| 결정할 문제 | 가능한 방향 | 현재 추천 | 추천 근거 | 누구와 확인 |
| --- | --- | --- | --- | --- |
| `USER_REVIEWED`의 소유 위치 | `evidence` / `case` | **미결** | Package 조사에는 readiness로 들어가지만 v3상 사용자 workflow는 `case` 책임이라 충돌 | `case`, `web` |
| Timestamp 숫자 confidence | 유지 / optional / TimeResolution에서 제거 | **TimeResolution에서는 source+verification 중심** | metadata 신뢰도를 객관적 숫자로 환산할 근거 없음 | `recording`, `readout`, `web` |
| Report Type 계약 | Visual Event와 통합 / 별도 enum | **별도** | 실제 안전신문고 UI 계층이 다름 | `search`, `web` |
| Requirement 결과 형식 | bool만 / PASS·WARN·BLOCK 계층 | **추가 검토 필요** | deadline exceeded처럼 warning이지만 submission blocker가 아닌 규칙 존재 | PM, `web` |
| ReportPackage provenance | 값을 복제 / EvidenceRecord·Asset를 Ref로 연결 | **Data Contract에서 결정** | Package는 파생값이며 재생성 가능 | `case`, `web`, `recording` |
| 첨부 개수 제한 | 지금 확정 / 미확정 유지 | **미확정 유지** | 제한 존재만 확인됨 | 추후 안전신문고 재확인 |
| 업로드/storage | 전체/부분/proxy/local | **실측 전 결정하지 않음** | recording 실측 필요 | `recording`, `search` |
| 보관기간 | 고정 일수 / 정책 데이터화 | **정책 데이터화, 숫자는 후속** | 업로드 방식·제품 정책 미확정 | `recording`, PM |
| JobRecord ownership | common 소유 / case 소유 | **domain Owner=`case`, infra=`common` 방향 검토** | 현재 두 문서의 표현이 다르게 읽힐 여지 있음 | `case` |

**추가 검토 제안:** 신고기한 계산에는 한국 공휴일 판단이 필요하지만, 제공 자료에서는 공휴일 데이터를 어떤 소스로 계산할지 정해지지 않았다. 외부 API/정적 calendar/라이브러리 중 무엇을 사용할지는 `evidence` Tech Spec에서 별도 결정해야 한다.

---

## 6. 충돌 / 상대 담당자 확인 필요

### A. 기존 Architecture와 충돌

**1. DB 선택**

- **충돌:** v3 `SQLite → PostgreSQL` 가능성 ↔ Runtime 조사 `MySQL 8.4 LTS부터 사용`.
- **이유:** DB가 단순 저장소가 아니라 Job Queue로 동시에 사용되고, MySQL에서도 `SKIP LOCKED` 기반 claim이 가능하다고 조사됨.
- **같이 볼 담당:** `case`, 공통 Runtime.

**2. Timestamp confidence**

- **충돌:** v3 `TimeResolution.confidence` ↔ Timestamp 조사에서 출처+검증상태 우선.
- **이유:** FILE_METADATA에 임의의 0.x 신뢰도를 붙일 객관적 기준이 없음.
- **같이 볼 담당:** `recording`, `readout`, `web`.

**3. Readiness 표현**

- **충돌:** v3 `READY_WITH_WARNINGS`/`4/5` 중심 ↔ 조사 문서의 3단계 readiness.
- **이유:** evidence 부족과 package 생성 실패, 사용자 workflow가 서로 다른 실패다.
- **같이 볼 담당:** `case`, `web`.

**4. 신고유형 표현**

- **충돌 가능:** 기존 예시의 `report_type`이 안전신문고 dropdown과 위반행위 설명을 완전히 분리하지 못함.
- **이유:** 실제 UI에서 Visual Event / Report Type / 구체적 위반은 다른 개념.
- **같이 볼 담당:** `search`, `web`.

### B. 다른 모듈과 충돌 가능

**1. `USER_REVIEWED`**

Package 조사에서는 `USER_REVIEWED`를 readiness로 제안했지만, v3는 `evidence`가 사용자 진행상태를 알아서는 안 되고 `case`가 workflow를 소유한다고 규정한다. **어느 모듈이 authoritative하게 소유할지 계약 단계에서 결정 필요.**

**2. `plate_visible_in_evidence`**

`evidence`는 번호판 가시성을 신고요건으로 검사해야 하지만, 실제 픽셀을 보지 않는다. 따라서 `readout` 또는 사용자 검토 결과 중 어떤 observation을 사용해 이 사실을 전달할지 합의가 필요하다.

**3. `evidence_time_visible` / 사후각인**

사후각인 허용 여부는 `evidence`가 판단하고 실제 파생영상 생성은 `recording`이 담당한다. 따라서 `evidence → case → recording`으로 전달되는 **각인 요구값과 결과값**의 경계를 합의해야 한다.

**4. `JobRecord`**

v3에서는 `JobRecord` Owner가 `case`이고, R&R상 공통 기반은 작업 큐 표를 담당한다.

논리적 데이터 소유권과 물리적 DB/claim 구현 책임을 혼동하지 않도록 명시해야 한다.

### C. Product/정책 결정 필요

1. metadata 기반 사후 timestamp를 **Known Uncertainty / Accepted Product Risk**로 실제 제품 정책에 채택할지.
2. 기한 초과를 `BLOCK`이 아니라 `WARNING`으로 둘지.
3. 안전신문고 130MB 상한보다 낮은 내부 target(예: 120MB)을 둘지.
4. 원본 동시 제출을 사용자 선택/권장으로 둘지.
5. Managed Source의 보관기간.
6. 사용자 입력만으로 수정한 시각을 파생영상에 각인할 때 고지 수준.

---

## 7. 후속 Data Contract에서 반드시 다룰 질문

1. `TimeSourceCandidate`/`Observation`은 raw source만 전달하는가, `AGREED / CONFLICT` 같은 검증 결과까지 producer가 전달하는가?
2. `TimeResolution`에서 숫자형 `confidence`를 계속 유지할 것인가, 아니면 `source + verification + conflict + computation`으로 대체할 것인가?
3. `VisualEventType`, `SafetyReportType`, `violation_description`을 각각 어떤 별도 필드/enum으로 표현할 것인가?
4. `vehicle_number_confirmed`와 `plate_visible_in_evidence`는 각각 어떤 producer의 어떤 Observation으로 충족시킬 것인가?
5. `EvidenceNeeds`가 사후 Timestamp 각인을 요구할 때 어떤 값이 `case → recording`으로 전달되고, 완료 후 어떤 `DerivedVideoRef`가 돌아오는가?
6. `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED`, `HANDOFF_STARTED` 중 **어디까지 `evidence`가 소유하고 어디부터 `case`가 소유하는가?**
7. `RequirementReport`의 결과는 단순 `ok: bool`인가, `PASS / WARNING / BLOCK`처럼 severity를 표현해야 하는가?
8. `ReportPackage`는 provenance를 복제해 snapshot으로 보존하는가, `EvidenceRecordRef`·`TimeResolutionRef`·`DerivedVideoRef`만 보유하는가?
9. `JobRecord`의 authoritative Owner=`case`와 DB queue infra Owner=`common`을 코드/Schema에서 어떻게 분리할 것인가?
10. 각 장시간 작업 module이 idempotency용 opaque `impl_ref`를 어떤 공통 계약으로 제공할 것인가?

---

## 8. 아키텍처 반영 우선순위

### 🔴 Architecture v4 전에 반드시 결정

- Timestamp `수집 ↔ 판정` 경계 유지 + 새로운 `TimeResolution` 표현 방향.
- `Visual Event ↔ SafetyReport Type ↔ 위반행위` 분리.
- `EVIDENCE_SUFFICIENT / PACKAGE_READY / USER_REVIEWED`의 **소유권 경계**.
- `web → case만 호출` 원칙과 “web이 evidence contract consumer” 표현의 정확한 의미.
- `case`의 `JobRecord` 소유권과 공통 Runtime의 queue infrastructure 책임 구분.
- 원본/Managed Source/Derived/Remote Copy가 서로 다른 asset이라는 원칙.

### 🟡 Data Contract 단계에서 결정

- `Observation` 최종 필드와 Timestamp verification 표현.
- `PlateReadout` → `plate_visible_in_evidence` 전달 방법.
- `EvidenceNeeds` enum/optional/why/would_fill.
- `RequirementReport`의 PASS/WARN/BLOCK 표현.
- `ReportPackage`의 Ref vs snapshot.
- PC/Mobile 필드 optional 규칙.
- DerivedVideo lineage와 timestamp 각인 정보.
- `JobRecord` 확장 필드 및 module `impl_ref`.
- `UsageRecord` 생산/집계 계약.

### 🟢 모듈 내부 Tech Spec에서 결정

- 신고문 실제 문장 템플릿.
- 내부 target video size.
- MySQL table/index 상세.
- retry backoff 구체 수치.
- Ruff/mypy/pytest/gitleaks 세부 설정.
- Worker polling 구현 세부.
- public-holiday 계산 구현체.
- 파일명 규칙.
- CI workflow 세부 단계.
- 추후 storage/upload 실측 뒤 선택되는 S3/proxy 세부 구현.

---

## 9. 원본 자료 Reference

- **`대신고 모듈 구조 설계 v3`**
    
    현재 `evidence` 책임·소유 데이터·공개 함수·`EvidenceNeeds`·전체 호출방향·기존 계약의 기준. 특히 `evidence`는 유일한 확정 주체이며 다른 모듈에 일을 직접 시키지 않는다는 경계가 핵심이다.
    
- **`대신고 모듈 기반 역할 배정안 v1`**
    
    김준영의 `evidence` 및 공통 기반/운영 Owner 범위와 상대 담당자 접합부의 기준.
    
- **`안전신문고 실제 신고 요건 및 초기 4종 유형 매핑 조사`**
    
    신고 Evidence 요건, 4종→신고유형 매핑, 번호판·시간·장소·기한·용량 규칙의 근거. 현재 baseline rule 목록은 문서 말미에 정리되어 있다.
    
- **`Timestamp / Evidence Policy`**
    
    시간 출처, metadata의 한계, source verification, 사후 Timestamp 조건, 원본/파생본 분리, Known Uncertainty 근거. 최종 원칙은 **시각을 만들지 않고, 출처를 숨기지 않으며, 불확실하면 그대로 남기는 것**이다.
    
- **`신고문 / Package / Handoff`**
    
    신고문 deterministic template, `ReportPackage`, PC/Mobile 공용 Package, 개인정보 제외, 자동제출 금지 및 Handoff 경계의 근거.
    
- **`대신고 백엔드 Runtime · Ops 고도화 설계 v1`**
    
    FastAPI + MySQL DB Queue + Worker 1, Job/Usage/Logging/CI와 아직 결정하지 않은 Storage/Upload 영역의 근거. 공통 운영 원칙은 장시간 작업의 Job화, idempotency, 최소 실패경계, stale 결과 차단, 비용 기록, 민감정보 로그 금지다.