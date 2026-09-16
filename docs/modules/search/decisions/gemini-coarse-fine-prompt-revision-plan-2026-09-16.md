# Gemini-only 교통위반 탐지 Coarse→Fine 프롬프트 개정 계획

작성일: 2026-09-16

대상: `search` 모듈의 신호위반·중앙선 침범·차선변경 후보 탐지

상태: **제안 및 실험 계획 — 운영 기본값을 아직 변경하지 않음**

> 이 문서는 Gemini를 법적 확정 판정기로 사용하는 안이 아니다. 영상에서 관찰 가능한 사실을
> 구조화하고 후보를 찾은 뒤 재검증하는 MVP의 프롬프트 및 평가 계획이다.
>
> 현재 운영 기준은
> [`gemini-change-application-plan-2026-09-12.md`](./gemini-change-application-plan-2026-09-12.md)에
> 있는 `gemini-3.7-flash` static baseline과 Fine high/2fps다. 본 문서의 `gemini-3.8-flash`
> 전환안과 신규 프롬프트는 아래 실험 게이트를 통과한 뒤 별도 결정으로 승격한다.
>
> 모델 가용성, SDK 필드, 가격, 허용 FPS 등 외부 API 관련 서술은 2026-09-16 시점의 조사 가정이다.
> 구현 직전에 공식 문서와 실제 SDK 요청·usage metadata로 다시 확인한다.

---

## 1. 결정하려는 문제

짧은 블랙박스 영상에서 다음 세 사건의 후보를 높은 재현율로 찾고, 후보 구간을 다시 읽어
시각적·시간적 증거를 엄격하게 검증한다.

- 신호위반 후보(`SIGNAL_VIOLATION`)
- 중앙선 침범 후보(`CENTERLINE_CROSSING`)
- 차선변경 제한 위반 후보(`LANE_CHANGE_RESTRICTION`)

핵심 원칙은 다음과 같다.

> 처음부터 “법을 위반했는가?”를 묻지 않는다. 먼저 “어떤 물리적 사건이 언제 실제로
> 관찰되는가?”를 묻는다.

영상 관찰과 법규 해석을 다음처럼 분리한다.

```text
Video observation
  → observable predicates
  → temporal relations
  → operational violation condition
  → jurisdiction-specific application rule
```

Gemini는 앞의 세 단계와 참고용 `final_status`를 반환한다. 필수 증거 완전성, 불확실성 차단,
관할별 법규 적용은 애플리케이션의 결정적 규칙이 담당한다.

---

## 2. 제안 아키텍처

```text
Original dashcam video
  → Coarse Search
      - 세 유형 동시 탐색
      - recall 우선
      - 후보 span + critical timestamp
      - 애매한 사건도 후보에 포함
  → Candidate span
      - 동일 업로드 파일의 start/end offset 또는 clip
      - 필요하면 원본 시각이 표시된 key frame 추가
  → Type-specific Fine Verification
      - evidence-first
      - 시간 순서 검증
      - OBSERVED / NOT_OBSERVED / UNCERTAIN
  → Application-side Gate
      - required evidence completeness
      - UNCERTAIN blocker
      - jurisdiction-specific policy
  → MVP result
```

### 단계별 기본안

| 항목 | 제안 |
| --- | --- |
| Coarse 입력 | 원본 짧은 video |
| Coarse 호출 | 세 유형을 한 번에 탐색 |
| Coarse 처리 | static 우선, zero-shot operational definition |
| Coarse 목표 | 높은 event recall |
| Fine 입력 | candidate video clip + 필요 시 timestamped key frames |
| Fine 처리 | static, high resolution, 더 촘촘한 FPS 실험 |
| Fine 호출 | candidate의 유형별 verifier와 schema 사용 |
| 상태 | `OBSERVED`, `NOT_OBSERVED`, `UNCERTAIN` |
| 최종 판정 | Gemini evidence + application-side deterministic gate |
| agentic video | 짧은 MVP의 기본값으로 사용하지 않음 |
| self-confidence | 운영 threshold로 사용하지 않음 |

10~15초 이하의 단일 사건 영상은 single-pass high-detail 처리를 반드시 baseline으로 둔다.
Coarse→Fine은 교리가 아니라 비용·정확도·디버깅성을 검증할 아키텍처 가설이다.

---

## 3. 위반 유형을 관찰 가능한 증거로 분해하기

### 3.1 신호위반

필수 관계:

```text
subject vehicle
  → travel direction / maneuver
  → applicable signal
  → signal state
  → stop line or intersection boundary
  → crossing event
  → signal state before/at crossing
```

권장 evidence key:

| key | 확인할 사실 | 확정 불가 시 |
| --- | --- | --- |
| `subject_vehicle` | 판단 대상 차량 | `UNCERTAIN` |
| `travel_direction` | 직진/좌회전/우회전 또는 진행 방향 | 정책에 따라 `UNCERTAIN` |
| `applicable_signal` | 대상 차로·진행에 적용되는 신호 | `UNCERTAIN` |
| `signal_state_before_crossing` | 통과 직전 신호 상태 | `UNCERTAIN` |
| `stop_line` | 정지선 위치 | `UNCERTAIN` |
| `crossing_event` | 실제 선 통과 | 부재면 `NOT_OBSERVED`, 가림이면 `UNCERTAIN` |
| `crossing_time` | 통과 시점 | temporal uncertainty |
| `intersection_entry` | 교차로 진입 | 보조 증거 |
| `temporal_relation` | 정지 신호가 통과 전/당시에 활성화됐는지 | 최종 확정 불가 |

여러 신호 중 단지 적색 신호가 보인다는 이유로 대상 차량의 신호라고 간주하지 않는다.
ego dashcam에서 정지선이 화면 아래로 사라지는 것을 범퍼 통과로 해석하는 경우 직접 관찰과
camera geometry proxy를 구분한다.

```text
crossing_observation_mode = DIRECT | CAMERA_PROXY | UNCERTAIN
```

### 3.2 중앙선 침범

필수 관계:

```text
road-direction structure
  → centerline identity
  → local centerline geometry
  → vehicle footprint over time
  → contact → crossing → occupancy → return
```

권장 evidence key:

- `road_direction_structure`
- `centerline_identity`
- `centerline_marking_type`
- `vehicle_side_before`
- `contact_state`
- `crossing_extent`
- `crossing_time`
- `persistence`
- `local_road_geometry`

`crossing_extent`는 boolean 대신 다음 enum을 사용한다.

```text
NONE | CONTACT_ONLY | PARTIAL_CROSSING | SUBSTANTIAL_CROSSING |
FULL_CROSSING | UNCERTAIN
```

이미지의 좌우 위치나 화면 중심만으로 침범을 판정하지 않는다. 곡선, 원근, 카메라 yaw를 고려해
차량 주변의 local road geometry와 연속 프레임의 선 연결을 사용한다.

### 3.3 차선변경 제한

먼저 차선변경 자체를 관찰하고 그다음 제한 조건을 확인한다.

```text
stable in lane A
  → lateral transition starts
  → vehicle overlaps divider
  → divider crossing
  → stable in lane B
```

권장 evidence key:

- `origin_lane`
- `target_lane`
- `lane_change_observed`
- `divider_identity`
- `divider_type_at_crossing`
- `crossing_time`
- `completed_lane_change`
- `turn_signal_observed`
- `special_zone_observed`
- `rule_inputs_complete`

forward-only ego dashcam에 방향지시등 상태가 보이지 않으면 꺼진 것으로 추론하지 않고
`UNCERTAIN`으로 둔다. 차선변경이 관찰됐다는 사실과 해당 변경이 관할 규칙상 금지라는 해석은
별도 필드로 유지한다.

---

## 4. 프롬프트 전략

### 4.1 공통 원칙

- 법률 조문 전체보다 visual operational definition을 제공한다.
- 관찰 사실, 시간 관계, 운영상 해석을 분리한다.
- verbose chain-of-thought 대신 검증 가능한 evidence field를 받는다.
- 보이지 않는 사실은 `UNCERTAIN`이며 `NOT_OBSERVED`가 아니다.
- schema-valid JSON과 의미상 옳은 증거를 별도로 검증한다.
- scalar confidence는 판정 threshold로 사용하지 않는다.

### 4.2 Coarse

- 한 요청에서 세 유형을 동시 탐색한다.
- recall을 precision보다 우선한다.
- zero-shot + explicit definition으로 시작한다.
- 애매한 신호 적용 관계, 선 종류, crossing 시점도 후보로 남긴다.
- 후보마다 context span과 가능하면 critical timestamp를 반환한다.
- 특정 클래스의 recall이 지속적으로 낮을 때만 해당 클래스의 coarse 호출을 분리한다.

Coarse few-shot은 초기에는 사용하지 않는다. 예시 외형에 과도하게 고정되어 후보 recall이
낮아질 가능성을 먼저 배제한다. false negative 분석이 쌓이면 2~4개의 text/image 예시를
추가한 variant를 별도로 비교한다.

### 4.3 Fine

- candidate 하나만 검증한다.
- 유형별 required evidence와 schema를 고정한다.
- 개별 증거 추출 후 temporal relation을 확인한다.
- mandatory predicate가 보이지 않으면 `UNCERTAIN`을 유지한다.
- hard-negative와 boundary case text few-shot은 별도 실험한다.

권장 hard-negative 예시:

```text
차량이 실선에 접근했지만 넘지 않았다.
→ crossing = NOT_OBSERVED

차량이 정지선을 넘었지만 어느 신호가 해당 차로를 제어하는지 구분할 수 없다.
→ crossing = OBSERVED
→ applicable_signal = UNCERTAIN
→ final_status = UNCERTAIN

forward-facing ego 영상에서 ego 방향지시등이 보이지 않는다.
→ turn_indicator = UNCERTAIN
```

---

## 5. Coarse prompt 초안

아래 prompt는 높은 recall의 후보 위치 탐색에만 사용한다.

```text
<role>
You are a video evidence locator for dashcam traffic scenes.

Do not prove that a legal violation occurred in this stage. Find every time
span that may contain a target event so a later verifier can inspect it.
</role>

<targets>
SIGNAL_VIOLATION:
- A subject vehicle may cross a stop line or enter a signal-controlled
  intersection while a potentially applicable signal requires stopping.
- Identify the subject and movement before associating a signal.
- A red signal for another lane or direction is insufficient.
- Include signal-transition cases when event order is unclear.

CENTERLINE_CROSSING:
- A vehicle may contact or cross a marking that separates opposing traffic.
- Distinguish a possible centerline from a same-direction divider or road edge.
- Do not decide from image x-position alone; consider curvature and perspective.

LANE_CHANGE_RESTRICTION:
- A vehicle changes lanes where the divider or visible road zone may restrict it.
- Identify origin lane, target lane, and the marking at the crossing location.
- Do not infer a turn indicator or jurisdiction-specific rule that is not visible.
</targets>

<search_policy>
Search the complete supplied video. Recall is more important than precision.
Return clear events and plausible ambiguous events. Do not invent signals,
markings, indicators, signs, or vehicle actions. Missing final legal proof is
not a reason to discard a plausible candidate. Multiple and overlapping
candidates are allowed.
</search_policy>

<localization>
For every candidate, return a tight start/end span with enough context before
and after the event. Return the likely crossing/entry/transition time when it
can be located; otherwise return null. All times refer to the original video.
</localization>

<uncertainty>
Report ambiguities explicitly, including signal applicability/color, stop-line
visibility, marking/centerline identity, solid/dashed state, occlusion,
crossing time, perspective, and insufficient frames.
</uncertainty>

<output>
Return only the supplied structured schema.
</output>
```

### Coarse schema

```json
{
  "type": "object",
  "properties": {
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "candidate_id": { "type": "string" },
          "violation_type": {
            "type": "string",
            "enum": [
              "SIGNAL_VIOLATION",
              "CENTERLINE_CROSSING",
              "LANE_CHANGE_RESTRICTION"
            ]
          },
          "subject_description": { "type": "string" },
          "start_time_sec": { "type": "number", "minimum": 0 },
          "end_time_sec": { "type": "number", "minimum": 0 },
          "critical_time_sec": { "type": ["number", "null"], "minimum": 0 },
          "candidate_strength": {
            "type": "string",
            "enum": ["STRONG", "WEAK", "AMBIGUOUS"]
          },
          "observable_evidence": {
            "type": "array",
            "items": { "type": "string" }
          },
          "uncertainty_reasons": {
            "type": "array",
            "items": { "type": "string" }
          },
          "candidate_reason": { "type": "string" }
        },
        "required": [
          "candidate_id", "violation_type", "subject_description",
          "start_time_sec", "end_time_sec", "critical_time_sec",
          "candidate_strength", "observable_evidence",
          "uncertainty_reasons", "candidate_reason"
        ],
        "additionalProperties": false
      }
    },
    "global_visibility_issues": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "required": ["candidates", "global_visibility_issues"],
  "additionalProperties": false
}
```

기존 계약상 `CandidateEvent.span`은 실제 사건 길이가 아니라 coarse 후보 창이다. 정밀 시각 평가는
[`candidate-span-semantics-2026-09-10.md`](./candidate-span-semantics-2026-09-10.md)를 따른다.

---

## 6. Fine prompt 초안

공통 prompt는 엄격한 증거 판정 규칙을 제공하고, 실제 호출에서는 candidate 유형별 required
evidence 목록과 Pydantic schema를 추가한다.

```text
<role>
You are a strict visual-evidence verifier for one dashcam candidate event.
Prioritize precision. Separate observable facts, temporal relationships, and
operational interpretation. Never fill missing evidence with assumptions.
</role>

<status_definition>
OBSERVED: the fact is visibly supported.
NOT_OBSERVED: visibility is adequate and the fact is absent or contradicted.
UNCERTAIN: missing visibility, occlusion, resolution, ambiguity, sampling,
perspective, multiple possible objects/signals, or insufficient temporal evidence
prevents a reliable decision.

Not visible means UNCERTAIN, not NOT_OBSERVED.
</status_definition>

<general_rules>
- Use only supplied media and explicit input context.
- Do not use unstated jurisdiction-specific law.
- Do not infer an ego turn signal from a forward road view.
- Do not associate a signal merely because a red light exists.
- Do not identify a centerline only from color or image position.
- Do not infer a lane change from one frame.
- Anchor positive observations to timestamps when possible.
</general_rules>

<verification>
SIGNAL_VIOLATION:
Verify subject, maneuver, applicable signal, signal state before/at crossing,
stop line, crossing, intersection entry, and temporal order. If controlling
signal association or transition order is unresolved, final_status is UNCERTAIN.

CENTERLINE_CROSSING:
Verify road-direction structure, centerline identity, marking, position before,
contact, crossing extent, persistence, and local geometry. Distinguish NONE,
CONTACT_ONLY, PARTIAL_CROSSING, SUBSTANTIAL_CROSSING, FULL_CROSSING, UNCERTAIN.

LANE_CHANGE_RESTRICTION:
Verify origin/target lanes, transition sequence, divider at the actual crossing
location, marking type, crossing time, visible indicator, and visible special
zone. A lane change alone does not establish a restriction violation.
</verification>

<final_status>
OBSERVED: all mandatory visual predicates in the supplied operational policy are
observed and temporally consistent.
NOT_OBSERVED: at least one mandatory predicate is clearly contradicted under
adequate visibility.
UNCERTAIN: no mandatory predicate is disproved, but at least one cannot be
reliably established.
</final_status>

<output>
Return only the supplied structured schema.
</output>
```

### 공통 Fine envelope

```json
{
  "type": "object",
  "properties": {
    "candidate_id": { "type": "string" },
    "violation_type": {
      "type": "string",
      "enum": [
        "SIGNAL_VIOLATION",
        "CENTERLINE_CROSSING",
        "LANE_CHANGE_RESTRICTION"
      ]
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "evidence_key": { "type": "string" },
          "status": {
            "type": "string",
            "enum": ["OBSERVED", "NOT_OBSERVED", "UNCERTAIN"]
          },
          "observation": { "type": "string" },
          "timestamps_sec": {
            "type": "array",
            "items": { "type": "number" }
          },
          "source": {
            "type": "string",
            "enum": ["VIDEO", "KEY_FRAME", "BOTH"]
          }
        },
        "required": [
          "evidence_key", "status", "observation", "timestamps_sec", "source"
        ],
        "additionalProperties": false
      }
    },
    "temporal_relation": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["OBSERVED", "NOT_OBSERVED", "UNCERTAIN"]
        },
        "observation": { "type": "string" }
      },
      "required": ["status", "observation"],
      "additionalProperties": false
    },
    "blocking_uncertainties": {
      "type": "array",
      "items": { "type": "string" }
    },
    "final_status": {
      "type": "string",
      "enum": ["OBSERVED", "NOT_OBSERVED", "UNCERTAIN"]
    },
    "final_basis": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "required": [
    "candidate_id", "violation_type", "evidence", "temporal_relation",
    "blocking_uncertainties", "final_status", "final_basis"
  ],
  "additionalProperties": false
}
```

구현 시에는 위 universal envelope만 사용하지 않고 유형별 Pydantic schema를 만든다. 예를 들어
신호위반 schema는 `applicable_signal`, `signal_state_at_crossing`, `stop_line_crossing`,
`crossing_observation_mode`를 고정 required field로 강제한다. 자유로운 `evidence_key` 배열은
실험용 호환 envelope로만 사용한다.

---

## 7. 입력 및 sampling 계획

### Coarse

- 원본 업로드 파일을 재사용한다.
- static baseline부터 시작한다.
- 기본 1fps가 빠른 사건을 놓치는지 측정한다.
- 1fps와 더 높은 지원 FPS를 event recall·token·latency로 비교한다.
- resolution은 현재 baseline을 유지하고 상향 효과를 별도 실험한다.

### Fine

우선순위는 다음과 같다.

1. candidate video clip
2. candidate clip + critical time 주변 3~7개 key frame
3. dense timestamped frames only는 비교군

key frame에는 반드시 원본 영상 기준 timestamp를 제공한다.

```text
FRAME_1 original_time=00:07.25
FRAME_2 original_time=00:07.75
FRAME_3 original_time=00:08.00
```

custom FPS와 clip offset은 문서상 지원 여부뿐 아니라 실제 요청 payload와 token density로 적용을
검증한다. 2/4/8fps 같은 값은 지원 범위와 비용을 실측하기 전 운영값으로 고정하지 않는다.

---

## 8. Application-side Gate

Gemini의 `final_status`는 진단 정보이며 단독 source of truth가 아니다.

```text
1. 유형별 mandatory evidence key가 모두 존재하는가?
2. 필수 key 중 UNCERTAIN이 있는가?
3. evidence status와 temporal_relation이 서로 일관적인가?
4. observation/timestamp가 candidate span 안에 있는가?
5. 관할별 operational rule의 입력이 완전한가?
6. Gemini final_status와 evidence-derived status가 일치하는가?
```

불일치는 별도 metric과 failure record로 저장한다. 법규 정책이 없는 경우 결과는
`visual_operational_status`까지만 제공하고 법적 위반으로 승격하지 않는다.

---

## 9. 평가 계획

### 9.1 Smoke test 데이터

45개 event-centered clip으로 시작한다.

| 유형 | 수량 | 구성 |
| --- | ---: | --- |
| 신호위반 관련 | 15 | clear positive 5~6, hard negative 5~6, ambiguous 3~5 |
| 중앙선 관련 | 15 | clear positive 5~6, hard negative 5~6, ambiguous 3~5 |
| 차선변경 관련 | 15 | clear positive 5~6, hard negative 5~6, ambiguous 3~5 |

필수 hard negative:

- 적색 신호가 보이지만 다른 차로 신호인 장면
- 적색 전환 직전 정지선 통과
- 중앙선 접촉만 있고 반대편으로 넘어가지 않은 장면
- 곡선도로의 perspective 착시
- 선 종류가 차량에 부분적으로 가린 장면
- 차선변경은 있지만 금지 marking이 아닌 장면
- ego 방향지시등 상태를 볼 수 없는 장면

annotation에는 단순 violation/normal뿐 아니라 event type, critical timestamp, candidate span,
required evidence visibility, evidence별 status, 최종 operational status를 저장한다.

### 9.2 Coarse metric

- Event Recall 및 유형별 recall
- Temporal Recall@tIoU(구간 사건의 보조 지표)
- critical timestamp coverage `±0.5s`, `±1s`
- critical timestamp absolute error
- false candidates/video
- mean/median candidate span length
- candidates/positive event
- input/output/thought/total token per video
- p50/p95 latency

point-like crossing 사건은 span IoU만으로 평가하지 않는다. `representative_ms` 또는
`critical_time_sec`의 onset 오차를 주 지표로 사용한다.

### 9.3 Fine metric

- 유형별 precision, recall, F1, FPR, FNR
- `UNCERTAIN` rate
- `final_status != UNCERTAIN`인 사례의 conditional accuracy
- Unsupported Evidence Rate
- Gemini final label과 evidence-derived deterministic label의 불일치율

유형별 진단 지표:

| 유형 | 진단 지표 |
| --- | --- |
| 신호 | applicable-signal association accuracy, signal-state-at-crossing accuracy, crossing timestamp MAE |
| 중앙선 | centerline identity accuracy, contact-only/crossing confusion |
| 차선변경 | lane-change occurrence accuracy, solid/dashed accuracy, turn-indicator unsupported inference rate |

`Unsupported Evidence Rate`는 Gemini가 `OBSERVED`라고 했지만 human annotator가 영상에서
확인할 수 없는 evidence의 비율로 정의한다.

---

## 10. 비교 실험과 채택 게이트

### A. Minimal vs Evidence-first

가설: Evidence-first가 recall을 크게 해치지 않으면서 false positive와 unsupported inference를 줄인다.

채택 조건 중 하나 이상:

- recall 저하가 3 percentage points 이내이면서 FP 20~30% 이상 감소
- recall 저하가 3pp 이내이면서 precision 약 5pp 이상 증가
- recall 저하가 3pp 이내이면서 unsupported evidence 50% 이상 감소

### B. Single-pass vs Coarse→Fine

가설: 두 단계 구조가 hard case precision, temporal localization, failure attribution을 개선한다.

채택 조건 중 하나 이상:

- precision 5pp 이상 증가
- FP 25% 이상 감소
- median timestamp error 20~25% 이상 감소

동시에 end-to-end recall 저하는 3pp 이내여야 한다. 10~15초 영상에서 차이가 없다면
single-pass로 단순화한다.

### C. Fine 입력 A/B/C

```text
A: candidate video clip
B: timestamped dense frames
C: candidate video clip + 3~7 key frames
```

C가 evidence accuracy 또는 precision을 의미 있게 높이고 비용·지연 예산을 지키면 채택한다.
차이가 없으면 A로 돌아간다.

### D. 모델 및 processing 변경 순서

한 실험에서 한 축만 변경한다.

1. 현재 모델·static·현재 입력 설정에서 prompt만 비교
2. 선택 prompt를 고정하고 single-pass와 coarse→fine 비교
3. 구조를 고정하고 Fine 입력 A/B/C 비교
4. 그 뒤에만 모델(`3.7` vs `3.8`) 또는 processing/FPS를 비교

이 순서를 지키지 않으면 prompt, 모델, FPS, resolution 중 무엇이 품질·비용 변화를 만들었는지
분리할 수 없다.

---

## 11. 주요 failure mode와 대응

| failure | prompt로 완화 | 입력/시스템 변경 필요 |
| --- | --- | --- |
| 여러 신호 중 적용 신호 혼동 | signal association을 필수 evidence로 강제 | 넓은 context + key frame |
| 작은 신호·화살표 | 제한적 | high resolution/key frame |
| 신호 전환과 crossing이 1초 이내 | temporal uncertainty 표기 | 높은 FPS/critical frames |
| 중앙선과 동일 방향 divider 혼동 | road topology와 identity 확인 | 넓은 context |
| 곡선·perspective 착시 | x-coordinate 금지, local geometry 지시 | 더 긴 전후 구간 |
| 접촉과 실제 crossing 혼동 | crossing extent enum | 연속 프레임 |
| 실선/점선이 가림 | `UNCERTAIN` 강제 | 전후 고해상도 frame |
| ego 방향지시등 비가시 | 추론 금지 | 해당 센서가 없으면 복구 불가 |
| motion blur/압축 | `UNCERTAIN` 강제 | 원본·다중 시점·sampling 변경 |
| 영상에 없는 사실 생성 | evidence-first와 unsupported metric | application gate |

좋은 prompt의 목표는 없는 정보를 복원하는 것이 아니라, 없는 정보를 없다고 인정하게 만드는 것이다.

---

## 12. 구현 산출물과 완료 조건

### 구현 산출물

- versioned Coarse prompt
- 신호/중앙선/차선변경별 Fine prompt와 Pydantic schema
- original-video timestamp가 보존되는 candidate/key-frame 입력 builder
- required evidence와 관할 정책을 적용하는 deterministic gate
- usage/model/processing/FPS/resolution/prompt version 기록
- evidence-level annotation과 평가 runner

### 계획 완료 조건

- 45개 smoke set과 annotation이 준비됐다.
- Minimal/Evidence-first, Single-pass/Coarse→Fine, Fine A/B/C가 동일 입력으로 비교됐다.
- unsupported evidence와 `UNCERTAIN`을 포함한 지표가 계산됐다.
- 모델·SDK·FPS·offset 설정이 실제 request와 token density로 검증됐다.
- 현재 3.7 baseline을 교체할지 유지할지 별도 decision record가 작성됐다.
- 선택된 prompt/schema가 `prompt_version`과 `config_version`으로 식별된다.

---

## 13. 제안 결론

MVP는 “Gemini-only 법적 판정기”가 아니라 **Gemini-only visual evidence detector + operational
verifier**로 정의한다. Coarse는 원본 짧은 영상을 한 번에 탐색해 세 유형의 후보를 높은 recall로
찾고, Fine은 candidate clip과 필요 시 timestamped key frames를 사용해 유형별 증거와 시간 관계를
검증한다. 결과는 `OBSERVED / NOT_OBSERVED / UNCERTAIN`으로 표현하고, 최종 법규 적용은
애플리케이션의 deterministic gate가 담당한다.

이 안의 핵심 변경은 모델 이름 자체가 아니라 다음 네 가지다.

1. 법적 label보다 observable evidence를 먼저 추출한다.
2. Coarse localization과 Fine verification의 목적을 분리한다.
3. 보이지 않는 사실을 `UNCERTAIN`으로 보존한다.
4. prompt 개선 효과를 evidence 수준의 metric으로 검증한다.
