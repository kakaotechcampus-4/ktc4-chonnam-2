# Final Data Contract — AnalysisScope v1

**Status:** `Final — Accepted`

> **`analysis-scope/1.1.0` — timeline-relative range 직렬화 확정 (2026-09-07 결정 · 2026-09-08 반영 · Decider 유소연 · 확인 서어진·김대원·정철원).** `time_ranges[]` 원소에 **`kind: ABSOLUTE | TIMELINE_RELATIVE`**를 두고, relative range는 `start_ms`·`end_ms`·`timeline_ref{timeline_id, revision}`를 필수로 갖는다(§5·§6·§7). 한 scope 안에서 두 kind를 섞지 않는다(§10-2). **하위 호환:** `kind`가 없고 `start`/`end`가 있는 기존 형식은 `ABSOLUTE`로 해석한다 — 기존 absolute 입력은 수정 없이 유효하다(minor bump). B08 방향(2026-09-07, `adr/adr-data-contract-call-closure-2026-09-07.md` §4.7)은 그대로이고, 직렬화 근거·기각안은 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.4.

**Accepted:** 확인 대기 — 최초 수락일과 2026-09-05 closure 보완일의 관계는 Owner 확인 필요 · `2026-09-07` (1.1.0 relative range, 유소연)

**수락 근거:** 본문 머리말 「ADR-003 확정 내용을 반영한 최종 계약… 아래는 잠금(locked) 스키마」 · §5 「확정 Contract 스키마 (JSON, locked)」 · §11 Draft→Final 확정표. Status는 본문의 종결 근거를 옮겼다. 수락일을 같은 회차로 추정한 C1-13 판정은 철회했다(후속 ADR §2 B12). 과거 헤더는 PM이 채웠다(`adr/adr-consistency-2026-09.md` C1-13). 유소연 이견 시 되돌린다

**Architecture Contract:** v4 §5-1 ④

**Contract Version:** `analysis-scope/1.1.0` (1.0.0 → 1.1.0: `time_ranges[].kind`·relative range 추가, 2026-09-08)

**Producer / Owner:** `case` — 유소연 · `eval` — 김대원 (fixture 생산. v4 §5-1 ④ 「case / eval fixture」)

**Consumers:** `search` — 서어진

**Related ADR:** `adr/adr-analysis-scope.md` · **1.1.0 근거 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.4**

## 계약 개요

> ADR-003 확정 내용을 반영한 최종 계약입니다. Draft의 A/B/C 선택지는 모두 확정되었으며, 아래는 잠금(locked) 스키마입니다. 원본 Draft 양식(섹션 순서)을 유지했습니다. (2026-09-08: locked 스키마에 Owner 결정으로 `time_ranges[].kind`와 relative range가 추가됐다 — 1.1.0.)
> 

---

### 1. 계약 목적

case가 사용자의 사건(case) 상태로부터 "무엇을, 언제 범위에서, 얼마의 예산으로 분석할지"를 search에게 전달하기 위한 요청(Intake) 스키마를 정의한다.

**핵심 불변조건(자료에서 확인됨, v1/v3 근거)**: search는 case_id, selection_rev, 파일/asset 참조, 위치(location) 정보를 알아서는 안 된다. AnalysisScope는 case 내부 상태를 search가 이해할 수 있는 "순수 분석 파라미터"로 변환하는 경계 계약이다.

### 2. Producer / Consumer

- **Producer**: case (유소연)
- **Consumer**: search (서어진). eval (김대원)은 v4 §5-1의 fixture Producer다.

### 3. 책임 경계

**case(Producer)가 보장하는 것**

- scope_id는 유일하며, 동일 scope_id 재사용 없음
- time_ranges는 최소 1개 이상 존재
- target_event_types는 최소 1개 이상 존재 (ADR-003 결정3, B안 반영 — 아래 참고)
- hint, budget 필드 형태는 본 계약에 명시된 구조를 그대로 따름

**search(Consumer)가 이 계약으로부터 기대할 수 있는 것**

- case_id/selection_rev/파일 경로/위치 정보 등 case 내부 참조가 전혀 섞이지 않은 입력
- target_event_types가 여러 개일 수 있음을 전제로 한 처리 (단일값 가정 금지)
- budget은 scope 전체에 대한 총합 예산이며, per-time_range 분배 로직은 search 자체 책임

**본 계약이 보장하지 않는 것**

- `budget.max_cost_krw` / `max_latency_sec`의 제품 기본 숫자값 — 벤치마크에 따라 config로 조정하며 Data Contract의 필드 의미·validation과 분리한다.
- budget 초과/부분 처리의 실행 결과 표현 — `contract-analysis-run-candidate-event.md` §5의 `AnalysisRun.outcome/issues[]` 책임이다.
- 복수 `time_ranges`를 eval에서 어떤 비율·시나리오로 테스트할지 — eval manifest/test plan 책임이다.

### 4. 조사에서 확인된 제약

| 제약 | 근거 |
| --- | --- |
| search는 case_id/selection_rev를 알 수 없음 | v3 모듈 경계 원칙 |
| search는 위치(location) 정보를 받지 않음 | v3 모듈 경계 원칙 |
| search는 파일/asset 참조를 직접 다루지 않음 | v3 모듈 경계 원칙 |
| target_event_types는 검색 대상 이벤트 유형을 필터링하는 용도 | v1/v3 |

### 5. 확정 Contract 스키마 (JSON, locked)

json

```json
{  "scope_id": "string",  "time_ranges": [    { "kind": "ABSOLUTE", "start": "ISO8601", "end": "ISO8601" }  ],  "target_event_types": ["EventType"],  "hint": {    "vehicle": "string | null",    "free_text": "string | null"  },  "budget": {    "max_cost_krw": "number (> 0)",    "max_latency_sec": "number (> 0)"  },  "contract_version": "string"}
```

`time_ranges[]` 원소는 `kind`로 구분되는 두 모양 중 하나다(1.1.0).

```json
{ "kind": "ABSOLUTE", "start": "ISO8601 (timezone 포함)", "end": "ISO8601 (timezone 포함)" }
```

```json
{ "kind": "TIMELINE_RELATIVE", "timeline_ref": { "timeline_id": "string", "revision": "int (>= 1)" }, "start_ms": "int", "end_ms": "int" }
```

> A/B/C 선택은 종료되었습니다. 결정 내역은 §11 참고. `kind`·relative range 추가(1.1.0)의 결정 내역은 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.4.
> 

### 6. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| scope_id | string | Y | 이 분석 요청의 고유 식별자 |
| time_ranges | array (min 1) | Y | 분석 대상 시간 범위 목록. 복수 구간 허용. 한 scope 안의 모든 원소는 같은 `kind`다(§10-2) |
| time_ranges[].kind | enum `ABSOLUTE` \| `TIMELINE_RELATIVE` | 조건부 (1.1.0) | 원소 discriminator. `TIMELINE_RELATIVE`이면 필수. **하위 호환:** `kind`가 없고 `start`/`end`가 있으면 `ABSOLUTE`로 해석한다(§7) |
| time_ranges[].start / .end | ISO8601 (timezone 포함) | `kind=ABSOLUTE`일 때 Y | 각 구간의 시작/종료 시각. `start <= end` |
| time_ranges[].timeline_ref | `{ timeline_id: string, revision: int }` | `kind=TIMELINE_RELATIVE`일 때 Y (1.1.0) | 좌표의 기준 `RecordingTimeline` identity와 **revision**(둘 다 필수). `timeline_id`는 recording 공개 identity이며 case 내부 참조·파일/asset ref가 아니다(§10-1 유지). revision이 없으면 rebase 이후 좌표·정답지 무효화를 감지할 수 없다 |
| time_ranges[].start_ms / .end_ms | int (ms) | `kind=TIMELINE_RELATIVE`일 때 Y (1.1.0) | timeline 시작 기준 상대 offset. `CandidateEvent.span.start_ms/end_ms`와 같은 ms 좌표계 — search 입력과 출력의 단위를 일치시켜 초/ms 변환 지점을 하나로 둔다. `start_ms <= end_ms` |
| target_event_types | array<string> (min 1) | Y | 탐지 대상 이벤트 유형. **1개 이상 다중 허용** (ADR-003 결정3, B안) |
| hint.vehicle | string | null | Y (nullable) | 차량 관련 soft hint. `hint` 객체와 키는 항상 존재하며 힌트가 없으면 null |
| `hint.free_text` | string | null | Y (nullable) | 자유 텍스트 soft hint. case가 사용자 PII를 sanitize하며 힌트가 없으면 null |
| budget.max_cost_krw | number | Y | scope **전체**에 대한 총 비용 한도 (per-time_range 아님, ADR-003 결정1 A안). non-null 양수이며 제품 기본값은 benchmark/config에서 관리 |
| budget.max_latency_sec | number | Y | search가 준수해야 하는 실행 마감 기한(execution deadline). non-null 양수이며 제품 기본값은 benchmark/config에서 관리 |
| contract_version | string | Y | 계약 버전 문자열 |

### 7. Enum / State / Special Value

- `time_ranges[].kind` (1.1.0): **`ABSOLUTE` | `TIMELINE_RELATIVE`** 둘로 닫는다. 계약에는 `TIMELINE_RELATIVE`만 쓴다(`RELATIVE` 같은 축약 표기를 등재하지 않는다).
  - **하위 호환 규칙:** `kind` 필드가 없고 `start`/`end`가 존재하는 기존(1.0.0) 형식은 `ABSOLUTE`로 해석한다. 이 규칙으로 기존 absolute 입력은 수정 없이 1.1.0에서 유효하다. `TIMELINE_RELATIVE` range는 `kind`를 반드시 명시한다.
  - `TIMELINE_RELATIVE`는 `RecordingTimeline.timeline_status=USABLE_RELATIVE_ONLY`인 영상의 정상 입력 경로다. 가짜 기준일·가짜 ISO8601을 만들어 `ABSOLUTE`로 위장하지 않는다(§10-7).
- `target_event_types`: 최소 1개. v4 baseline enum은 `SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE`로 고정한다. 신규 유형 추가 시 계약 enum을 갱신한다.
- `hint`: 객체 자체는 항상 존재한다.
- `hint.vehicle` / `hint.free_text`: null 허용. null은 "힌트 없음"을 의미한다. `free_text`는 soft hint이며 이름·연락처 등 사용자 PII를 포함하지 않도록 case가 sanitize한다.
- `budget.max_cost_krw` / `budget.max_latency_sec`: null 금지, 각각 `> 0`.

### 8. 정상 예시

json

```json
{  "scope_id": "scope_2026_0912_001",  "time_ranges": [    { "kind": "ABSOLUTE", "start": "2026-09-01T08:00:00Z", "end": "2026-09-01T09:00:00Z" }  ],  "target_event_types": ["SIGNAL", "SOLID_LINE_LANE_CHANGE"],  "hint": {    "vehicle": "white sedan",    "free_text": null  },  "budget": {    "max_cost_krw": 300,    "max_latency_sec": 180  },  "contract_version": "1.1.0"}
```

> target_event_types가 2개인 예시로 교체 — ADR-003 결정3(B안, 다중 허용) 반영. 이전 Draft 예시는 단일값 기준이었음. 1.1.0에서 `kind: "ABSOLUTE"`를 명시했다 — `kind`가 없는 1.0.0 형식도 같은 의미로 유효하다(§7).
> 

**relative-only timeline 예시 (1.1.0, `kind=TIMELINE_RELATIVE`)** — absolute anchor가 없는 영상. 두 range가 같은 `timeline_id`·`revision`을 참조한다.

```json
{  "scope_id": "scope_2026_0912_002",  "time_ranges": [    { "kind": "TIMELINE_RELATIVE", "timeline_ref": { "timeline_id": "tl_h001", "revision": 2 }, "start_ms": 300000, "end_ms": 480000 },    { "kind": "TIMELINE_RELATIVE", "timeline_ref": { "timeline_id": "tl_h001", "revision": 2 }, "start_ms": 900000, "end_ms": 960000 }  ],  "target_event_types": ["SOLID_LINE_LANE_CHANGE"],  "hint": {    "vehicle": null,    "free_text": null  },  "budget": {    "max_cost_krw": 300,    "max_latency_sec": 180  },  "contract_version": "1.1.0"}
```

### 9. 실패 / 부분성공 / UNKNOWN 예시

- **입력 검증 실패**: time_ranges가 빈 배열이거나 target_event_types가 빈 배열인 경우 → case 측에서 요청 자체를 생성하지 않음 (본 계약 진입 전 케이스에서 차단, §10 불변조건 참고)
- **budget 초과로 인한 부분 처리**: AnalysisScope 자체는 실행 결과를 담지 않으므로 부분성공/실패 표현은 본 계약 범위 밖. 해당 표현은 `contract-analysis-run-candidate-event.md` §5(AnalysisRun.outcome: SUCCEEDED/PARTIAL/FAILED)에서 다룸
- **absolute anchor가 없는 영상(`RecordingTimeline.timeline_status=USABLE_RELATIVE_ONLY`)**: 정상 입력이다. `kind=TIMELINE_RELATIVE` range로 표현한다(§8 두 번째 예시). **임의 기준일이나 가짜 ISO8601을 만들어 채우지 않는다**(`product-spec.md` §7) — anchor 부재만으로 Search를 차단하는 것도 금지다(§12). 실패/UNKNOWN 케이스가 아니라 정상 경로라서 여기 적어 두는 것은 「이 경로에서 실패로 처리하지 말라」는 뜻이다
- **혼합 입력**(`ABSOLUTE`와 `TIMELINE_RELATIVE`가 한 `time_ranges`에 함께 있음) · **`TIMELINE_RELATIVE`에 `timeline_ref` 누락** · **relative range끼리 `timeline_id`/`revision` 불일치** · **`start_ms > end_ms`**: 입력 검증 실패 → case 측에서 요청을 생성하지 않는다(§10-2)

### 10. 불변조건

1. search는 case_id, selection_rev, 파일/asset 참조, location을 절대 수신하지 않는다 (본 계약 필드에 해당 값이 존재하지 않음이 그 자체로 강제 수단)
2. `time_ranges`는 최소 1개 이상이다. (1.1.0 · `kind`별 분기)
   - `kind=ABSOLUTE`(또는 `kind` 부재 + `start`/`end` 존재): 각 range는 timezone을 포함한 ISO8601을 사용하고 `start <= end`를 만족한다.
   - `kind=TIMELINE_RELATIVE`: `start_ms <= end_ms`이고 `timeline_ref`(`timeline_id`+`revision`)가 필수로 존재한다.
   - 한 `AnalysisScope` 안에서 `ABSOLUTE`와 `TIMELINE_RELATIVE`를 **섞지 않는다**. scope는 하나의 시간 기준만 쓴다. `TIMELINE_RELATIVE` range가 여럿이면 모두 같은 `timeline_id`와 `revision`을 참조한다.
3. `target_event_types`는 최소 1개 이상이며 v4 baseline enum 값만 허용한다.
4. `budget`은 scope 전체 단일 값이며 time_range별로 분리되지 않는다 (ADR-003 결정1 유지).
5. `budget.max_cost_krw` / `budget.max_latency_sec`는 필수 non-null 숫자이며 반드시 `> 0`이다. 기본 숫자값은 benchmark/config에서 관리한다.
6. `hint` 객체는 항상 존재하며 `vehicle`/`free_text`는 null 가능하다. case는 `free_text`에서 사용자 PII를 제거한다.
7. (2026-09-07) `time_ranges`에 **가짜 기준일·가짜 ISO8601을 생성해 넣지 않는다.** relative-only timeline의 구간은 `kind=TIMELINE_RELATIVE` range로만 전달한다(§7·§12).

### 11. Consumer Review 반영 요약

| 결정 항목 | Draft 원안 | Final 확정 | 반영 사유 |
| --- | --- | --- | --- |
| 결정1 (budget 구조) | A안 (scope 전체 총예산) | **A안 유지** | Consumer 이견 없음 |
| 결정2 (hint 구조) | A안 (minimal {vehicle, free_text}) | **A안 유지** | Consumer 이견 없음 |
| 결정3 (target_event_types) | A안 (정확히 1개) | **B안으로 변경 (1개 이상 다중 허용)** | 서어진(search) "수정요청" — 구현 관점에서 다중 허용 필요. Producer(유소연) 수용 |

전체 결정 근거 및 trade-off는 ADR-003 참고.

### 12. Closure / 후속 운영 범위

- `budget` validation은 **non-null + 양수(`> 0`)**로 확정했다. 실제 제품 기본 숫자는 Search benchmark 결과에 따라 config에서 조정하며 계약 변경 사유가 아니다.
- `target_event_types`는 v4 baseline 4종 enum으로 확정했다: `SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE`.
- 다중 target의 eval 귀속은 `CandidateEvent.event_type_hint`에 의존하지 않는다. `contract-analysis-run-candidate-event.md`의 기존 결정대로 `event_type_hint`는 Recall-first Candidate 단계의 optional visual-event hint로 유지한다. Eval의 유형별 Recall은 Ground Truth의 event type과 Candidate span 매칭으로 귀속하며, hint가 있으면 진단/분석 보조값으로만 사용한다.
- 복수 `time_ranges`는 Contract 차원에서 정식 허용한다. 구간별 처리·partial coverage는 `contract-analysis-run-candidate-event.md`의 `AnalysisRun/issues[]`가 표현하며, eval manifest의 테스트 비율/시나리오는 Eval 계획으로 분리한다.
- `hint` 객체는 항상 존재하고 하위 두 필드는 null 가능하며, case는 PII sanitize 책임을 가진다.

**B08 — timeline-relative range (2026-09-07 방향 확정 → 2026-09-08 직렬화 반영 · 종결)**

`recording`은 다음 불변조건을 유지한다(`contract-recording-timeline-asset-span.md` §4·§23): relative-only `RecordingTimeline`은 정상 usable 상태다 · 가짜 absolute datetime 생성은 금지다 · absolute anchor 부재만으로 Search를 차단하는 것은 금지다 · relative 좌표는 실제 `RecordingTimeline`의 `timeline_id + revision`을 참조한다 · rebase 이후에도 기존 Scope와 결과가 사용한 revision provenance는 보존된다. recording의 `SpanResolution`은 초 단위를 유지하며, ms↔초 변환은 recording 공개 경계에서 명시적으로, 동일 revision 기준으로 한다.

**직렬화(확정 · Decider 유소연 · 확인 서어진·김대원·정철원):** 원소 discriminator `kind: ABSOLUTE | TIMELINE_RELATIVE`(§5·§7) · relative는 `start_ms`/`end_ms` + range마다 `timeline_ref{timeline_id, revision}`(§6) · 혼합 불허(§10-2) · `contract_version` `1.1.0` · 하위 호환 규칙(§7). `eval`은 아직 `AnalysisScope` fixture를 생산하지 않아 마이그레이션 대상 fixture가 없다 — 앞으로 만드는 fixture가 이 형식을 따른다. **범위 밖(별건 유지):** `timeline_id`+ms offset ↔ eval 정답지 `clip_id` 대응은 이번 결정으로 닫히지 않았다(eval Owner 항목). 기각안(별도 배열 · `start_sec` · 혼합 허용 · scope 상위 단일 `timeline_ref`)과 근거는 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.4. 회차 중간에 나온 「anchor가 없으면 case가 검색을 막고 notice로 표현」안은 recording 불변조건과 충돌해 채택되지 않았다(`adr/adr-data-contract-call-closure-2026-09-07.md` §4.7).
