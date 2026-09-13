# ADR-003: AnalysisScope

## ADR-003: `AnalysisScope` Data Contract 확정

**Status:** Accepted

> **후속 변경 (2026-09-08):** `analysis-scope/1.1.0` — `time_ranges[].kind: ABSOLUTE | TIMELINE_RELATIVE` 추가, relative range는 `start_ms`/`end_ms` + `timeline_ref{timeline_id, revision}`, 혼합 불허, `kind` 부재는 `ABSOLUTE`로 해석(하위 호환). Decider 유소연, 확인 서어진·김대원·정철원. 근거·기각안 `adr-data-contract-call-closure-2026-09-08.md` §4.4(B08 방향은 `adr-data-contract-call-closure-2026-09-07.md` §4.7). 아래 본문은 당시 결정 기록이며 고치지 않았다 — 본문의 「timezone 포함 ISO8601」 서술은 1.1.0에서 `kind=ABSOLUTE`에 한정된다.

> **⚠ 2026-09-05 정합성 보정 (PM · 김준영).** 본문의 `LANE_CHANGE`를 **`SOLID_LINE_LANE_CHANGE`**로 고쳤다(1곳). v4 §3-5가 baseline 4종을 `SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE`로 고정하고 Final 계약도 그 이름을 쓰는데 이 ADR만 옛 이름을 갖고 있었다.
>
> **결정 내용은 바뀌지 않았다 — 같은 값의 표기만 v4에 맞췄다.** 지원 범위 4종, 그 안에서 세 번째 항목이 「진로변경(백색 실선 침범)」인 것은 그대로다. 경위는 `adr-consistency-2026-09.md` C1-1.

**Contract:** `AnalysisScope`

**Producer:** case (유소연)

**Consumer:** search (서어진), eval (김대원)

**Owner:** 유소연 (Contract Lead)

**결정일:** 2026-09-05 (closure 보완)

**관련 Contract Version:** `1.0`

**관련 Architecture Version:** `module_architecture.md v4`

관련 문서:

- 대신고_테크스펙_v1 (p.25 등)
- 대신고_모듈_구조_설계_v3 (§5-③, §11-2, §3-4)
- R&R 데이터 계약 분담표
- `AnalysisScope` Data Contract Draft
- Consumer Review (서어진, 김대원)

---

### 1. 결정 배경(Context)

#### Producer가 생성하는 것

case는 사용자의 자연어 단서를 해석한 결과를, search가 사건을 탐색하고 eval이 동일 조건으로 채점할 수 있는 **유일한 입력값**으로 만들어 낸다.

#### Consumer가 필요로 하는 것

search는 사용자·진행 상태·개인정보를 전혀 모른 채로 탐색을 수행해야 하고("이 모듈은 사용자를 모른다"는 방어선), eval은 제품과 완전히 동일한 형식의 입력을 받아야 "채점기에서 나온 숫자가 제품 성능이다"라고 말할 수 있다.

#### 계약을 고정해야 했던 이유

이 계약이 없으면:

- case가 사용자 이름·연락처·진행상태·위치 등을 실수로 search에 흘려보낼 수 있다.
- 제품이 실제로 쓰는 입력 형식과 eval이 채점에 쓰는 형식이 갈라져 채점 결과가 제품 성능을 대표하지 못하게 된다.
- target_event_types 처리 방식(단일/복수)이 case·search·eval 사이에서 각자 다르게 가정될 수 있다.

---

### 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| 사용자 이름·연락처·진행상태 금지(외부 API로 나가기 때문) | v3 §5-③ | hint/free_text에 개인식별정보가 섞이지 않도록 case가 필터링 |
| search의 유일한 입력은 시간 범위뿐이며 파일 위치를 모른다 | v3 §11-2 | AnalysisScope에 파일 경로/asset_id를 두지 않음 |
| 제품과 채점기(eval)는 반드시 동일 포맷을 사용한다 | v1/v3 공통 | 필드 변경 시 eval도 함께 바뀌어야 하므로 9개 계약 중 "Core 합의" 대상 |
| target_event_types는 목록(list) 형태이며 유형별 분기는 search 내부 사정 | v3 §3-4 | 유형 추가는 배열 값 추가만으로 가능, 계약 구조 변경 불필요 |
| budget의 제품 기본 숫자는 실측에 따라 조정 가능 | v1 "[미결]" 표기 + Consumer Review | Contract는 non-null 양수 validation과 의미만 고정하고, 실제 기본 숫자는 benchmark/config로 분리 |

---

### 3. 검토했던 주요 선택지

### 결정 1. budget 필드의 범위 단위

#### A안 — Scope 전체 총예산

scope에서 발생하는 모든 실행의 합산 상한 하나만 둔다.

**장점:** case의 예산 관리가 단순. search 내부 배분은 search 소관.

**단점:** search가 coarse/fine 배분을 스스로 판단해야 함.

#### B안 — 단계별 분리 예산

coarse/fine 각각 별도 상한을 둔다.

**장점:** case가 단계별 통제 가능.

**단점:** case가 search의 내부 stage 구조를 계약에 고정해서 알아야 함 — 모듈 경계 침범 소지.

### 결정 2. hint 필드의 구조화 수준

#### A안 — 현행 최소 구조(`vehicle` + `free_text`)

**장점:** 스키마 단순, 계약 변경 빈도 낮음.

**단점:** search가 free_text를 다시 파싱해야 할 수 있음.

#### B안 — 구조화 확장(색상/방향 등 서브필드 추가)

**장점:** 재해석 비용/불일치 위험 감소.

**단점:** Core 합의 계약이라 필드 추가마다 재합의 비용이 큼.

### 결정 3. target_event_types 복수 허용 기준

#### A안 — 항상 정확히 1개로 확정

**장점:** 비용 예측 쉬움, eval의 유형별 독립 채점과 정합.

**단점:** 사용자 clue가 모호할 때 재질문 왕복 비용 발생, 강제 단일화가 recall을 낮출 수 있음.

#### B안 — 모호하면 복수 유형 동시 전달 허용

**장점:** 재질문 없이 즉시 착수, search의 coarse 단계가 이미 여러 유형을 한 번에 탐색 가능.

**단점:** 유형별 채점 귀속 로직이 추가로 필요.

---

### 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| budget 범위 단위 | A안 | A안 | 서어진 조건부 승인(예산 초과 시 결과에 명시 필요) | 유지(단, 파생 요구사항 발생) |
| hint 구조화 수준 | A안 | A안 | 서어진 승인 | 유지 |
| target_event_types 복수 허용 | **B안** | A안 | 서어진 수정 요청(B안 권장), Producer 수용 | **변경** |

#### 결정 1. budget 범위 단위

**최종 선택:** A안 (Scope 전체 총예산)

**결정 내용:** budget은 `{max_cost_krw, max_latency_sec}` 구조로 scope 실행 전체의 합산 상한을 표현하며, coarse/fine 배분은 search 내부 사정으로 남긴다.

**선택 이유:**

- Architecture/Ownership 측면: "유형별·단계별 처리 분기는 search 내부 사정"이라는 기존 원칙과 정합적이며, case가 search의 내부 stage 구조를 알 필요가 없다.
- Consumer 구현 측면: 서어진이 이 구조에 조건부로 동의했고, 반대 급부로 예산 초과 시 이를 실행 결과에서 드러내야 한다는 요구를 남겼다(§10 참고).

#### 결정 2. hint 구조화 수준

**최종 선택:** A안 (현행 최소 구조 유지)

**결정 내용:** hint는 `{vehicle, free_text}` 두 키를 항상 유지하며 두 값은 nullable이다. `free_text`는 soft hint로만 사용하고 case가 사용자 PII를 sanitize한다.

**선택 이유:**

- Producer 구현 측면: 세분화가 실제로 필요하다는 실측 근거가 없다.
- Consumer 구현 측면: 서어진이 현행 구조로 충분하다고 확인했으며, free_text를 VLM에 soft hint로 그대로 전달하는 방식(하드 필터로 쓰지 않음)에 동의했다.

#### 결정 3. target_event_types 복수 허용

**최종 선택:** B안 (1개 이상, N개 허용)

**결정 내용:** target_event_types는 최소 1개, 현재 baseline 4종 내에서 여러 개를 동시에 담을 수 있다.

**선택 이유:**

- Producer(서어진) 구현 측면: search의 coarse 단계가 이미 한 번의 실행에서 여러 유형을 동시에 탐색할 수 있는 구조이며, 여러 번 나눠 실행하는 것보다 비용·지연상 유리하다.
- Product 측면: 사용자가 사건 유형을 정확히 기억하지 못하는 경우 case가 하나로 강제 확정하면 오히려 Recall이 떨어질 수 있다.
- Draft가 추천했던 A안(항상 1개)은 Consumer의 실제 구현 관점에서 기각되었다.

---

### 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| 서어진: budget A안에 조건부 동의, 예산 초과/부족 시 결과에 명시적으로 드러나야 함 | 반영 | AnalysisScope 자체는 변경 없음(구조상 이미 A안) — 단 이 요구는 `AnalysisRun`(계약④) 쪽 책임으로 이관 | budget 소진 여부 표시는 실행 결과의 책임이지 요청 계약(AnalysisScope)의 책임이 아니므로 |
| 서어진: max_latency_sec의 의미(절대 응답시간 보장 vs 실행 deadline)를 명확히 할 것 | 반영 | 필드 의미를 "search가 준수해야 하는 실행 deadline"으로 명확화(구조 변경 없음) | Consumer 혼동 방지 |
| 서어진: hint 현행 구조로 충분, free_text는 soft hint로만 사용 | 반영 불필요(그대로 유지) | 변경 없음 | Draft 추천과 Consumer 의견이 일치 |
| 서어진: target_event_types를 1개로 제한하지 말고 1..N 허용(B안) | **반영** | **target_event_types를 1개 이상 다중 허용으로 변경** | Producer가 Consumer의 실제 구현 제약(coarse 단계 특성, recall 저하 위험)을 수용 |
| 서어진: budget 실제 숫자는 실측 결과 없이는 확정 불가 | 반영 | Contract는 `>0` validation만 고정하고 실제 제품 기본 숫자는 benchmark/config로 분리 | 운영 기본값과 Data Contract 의미를 분리하여 Final closure를 막지 않도록 함 |
| 서어진: Draft의 null placeholder와 "budget은 0보다 커야 한다"는 invariant가 모순 | 반영 | `budget.max_cost_krw` / `max_latency_sec` 모두 필수 non-null + `>0`으로 확정 | placeholder null을 계약 상태로 취급하지 않고 입력 validation을 명시적으로 고정 |
| 김대원: 전체 승인, 수정 요청 없음 | 반영 불필요 | 변경 없음 | 특별한 반영 대상 없음 |
| (Q5) 다중 time_ranges에 대한 eval manifest 테스트 계획 | 답변 없음 | 변경 없음 | Consumer로부터 구체적 답변을 받지 못함 — §13 미해결로 기록 |

---

### 6. 최종 Contract 핵심 요약

- case가 생성하는 유일한 필드 집합: `scope_id, time_ranges[], target_event_types[], hint, budget, contract_version`
- 사용자 이름/연락처/진행상태/위치/파일 참조/case 내부 식별자는 포함하지 않는다.
- `target_event_types`는 최소 1개, **여러 개를 동시에 담을 수 있다**(Draft의 "항상 1개" 원칙에서 변경).
- `hint`는 구조화하지 않은 최소 형태(`vehicle`, `free_text`)를 유지하며, Consumer는 이를 신뢰도 낮은 soft hint로만 사용한다.
- `budget`은 scope 전체에 대한 단일 총예산이며, 단계별 내부 배분은 search 소관이다. 실제 숫자는 아직 미정이다.
- 전체 필드 정의는 Final Data Contract 문서를 참조한다.

---

### 7. Invariants / 보장사항

- `time_ranges`는 최소 1개 이상, 각 range는 `start <= end`.
- `target_event_types`는 최소 1개 이상이며, baseline 4종(`SIGNAL`, `CENTER_LINE_CROSSING`, `SOLID_LINE_LANE_CHANGE`, `MOTORCYCLE_HELMET_NON_USE`) 중에서만 값을 가진다. 2개 이상도 허용된다.
- `scope_id`는 시스템 전체에서 유일하며 case가 생성 책임을 진다.
- AnalysisScope에는 `case_id`, 사용자 이름/연락처/진행상태, 위치 정보, 파일 경로/asset 참조가 포함되지 않는다.
- `contract_version`은 product 코드와 eval 채점기가 항상 동일 값을 사용한다.
- (미해결) `budget` 값이 존재할 경우 0보다 커야 한다는 규칙은 실제 숫자가 채워지기 전까지 어떻게 적용되는지 확정되지 않았다.

---

### 8. 이번 결정의 결과(Consequences)

#### 긍정적 결과

- 사용자가 사건 유형을 정확히 기억하지 못해도 case가 재질문 없이 즉시 탐색을 시작할 수 있다.
- search의 실제 coarse 단계 구현(한 번에 여러 유형 탐색)과 계약이 어긋나지 않게 되었다.
- budget/hint 구조가 단순하게 유지되어 이후 Mock 작성이 쉽다.

#### 감수하는 비용 / 단점

- target_event_types가 복수가 되면서 eval이 한 실행 결과를 유형별로 나눠 채점하는 로직을 추가로 구현해야 한다.
- case의 자연어 해석(intent LLM)이 이제 "복수 유형을 함께 낼 수 있는 케이스"까지 평가 대상에 포함해야 하므로 intent 평가체계가 더 복잡해진다.
- budget 관련 두 가지(실제 숫자, null-placeholder 모순)가 미해결로 남아 Final Contract가 완전히 닫히지 않은 상태다.

---

### 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| budget 결정 B안(단계별 분리 예산) | case가 search의 내부 stage(coarse/fine) 구조를 계약에 고정해서 알아야 하므로 모듈 경계 침범 위험 |
| hint 결정 B안(구조화 확장) | 세분화가 필요하다는 실측 근거가 없고, Core 합의 계약이라 필드 추가 비용이 큼 |
| target_event_types 결정 A안(항상 1개) | Draft의 추천안이었으나, Producer 자신이 Consumer(서어진)의 구현 관점을 수용해 최종적으로 기각함 |

---

### 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| ④ `AnalysisRun + CandidateEvent` | target_event_types가 복수일 수 있으므로, 각 CandidateEvent가 실제로 어떤 event_type으로 검출됐는지 명시해야 eval의 유형별 독립 채점이 가능함 | 예 — ④ Draft의 `event_type_hint`(optional)가 이 요구를 충족하는지 재확인 필요 |
| ④ `AnalysisRun` | budget 초과/부족 시 이를 실행 결과에서 명시적으로 드러내야 함(서어진 요구) | 예 — ④ Draft의 `outcome`/`issues[]`가 이 케이스를 커버하는지 확인 필요 |
| eval 채점 체계 | 한 scope 요청에 복수 유형이 포함될 수 있으므로 유형별 분리 채점 로직이 필요함 | 예 — 김대원 확인 필요 |

---

### 11. Mock / 구현 / Evaluation에 미치는 영향

#### Mock Dataset

- 단일 유형 정상 케이스
- **복수 유형이 동시에 포함된 케이스**(신규)
- hint가 비어 있는 케이스(단서 없음)
- time_ranges가 넓게 잡힌 모호한 시간 케이스
- budget 값이 아직 없는(미정) 케이스

#### 구현

- case: 자연어 해석 LLM이 복수 유형을 배열로 낼 수 있어야 한다.
- search: 배열 내 여러 유형을 한 번의 coarse 실행에서 함께 탐색하고, budget 초과 시 이를 결과에 표시해야 한다.

#### Evaluation

- eval은 한 scope 요청에 복수 유형이 포함된 경우에도 유형별로 독립적인 Recall 등을 계산해야 한다(기존 "유형별 독립 채점" 원칙을 다중 요청 케이스에도 동일 적용).

---

### 12. 변경 규칙

문제 발견 → Producer/Consumer 확인 → Data Contract 변경안 작성 → Architecture 영향 확인 → Contract Version 증가 → ADR Supersede 또는 변경 ADR 작성 → Mock Dataset 갱신.

사소한 설명 문구 변경은 새 ADR 대상이 아니다. 필수/선택 의미 변경, Ownership 변경, State/Enum 의미 변경, 실패/UNKNOWN 의미 변경, 다른 모듈 계약에 영향을 주는 필드 변경은 ADR 변경 대상으로 본다.

---

### 13. Closure 완료 / 후속 운영 범위

| 항목 | 처리 결과 / 후속 범위 | 담당자 | 시점 / 상태 |
| --- | --- | --- | --- |
| `budget.max_cost_krw` / `max_latency_sec` 제품 기본 숫자 | Data Contract 미해결이 아님. 벤치마크 결과에 따라 Search config에서 조정한다. | search | 운영/튜닝 시점 |
| budget validation | 해결 완료: 두 값 모두 필수 non-null + `>0`. 실제 제품 기본 숫자는 config로 분리 | case/search | Closure 완료 |
| target_event_types 복수 허용에 따른 Eval 유형 귀속 | 해결 완료: Contract④의 `CandidateEvent.event_type_hint`는 Recall-first 설계에 따라 optional을 유지한다. Eval의 유형별 귀속은 Ground Truth event type + Candidate span matching으로 수행하며 hint에는 의존하지 않는다. | eval/search | AnalysisScope closure 규칙으로 확정; Contract④ 변경 불필요 |
| 다중 `time_ranges` 시나리오의 eval manifest 테스트 계획 | Data Contract 미해결이 아니라 Eval test-plan 항목으로 분리. 계약은 복수 구간을 정식 허용하고 구간별 partial coverage는 Contract④ `issues[].scope_ref`로 표현 | eval | Eval manifest 설계 시점 |

---

### 14. 최종 한 줄 결정

> **우리는 `case`가 사용자 개인정보·내부 식별자·위치·파일 참조 없이 `time_ranges` · `target_event_types`(v4 baseline 4종, 1개 이상 다중 허용) · 항상 존재하는 nullable `hint` · non-null 양수 `budget`으로 구성된 `AnalysisScope`를 생성하고, `search`가 이를 사건 탐색의 유일한 입력으로, `eval`이 동일 포맷으로 채점 재현에 사용하도록 계약을 확정한다. 제품 budget 기본값과 eval 시나리오 구성은 계약 밖 운영/config 영역으로 분리하며, 유형별 Eval 귀속은 optional `event_type_hint`가 아니라 Ground Truth event type과 Candidate span matching으로 수행한다.**
>