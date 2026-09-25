# Gemini Coarse→Fine p4 구현 계획

작성일: 2026-09-22  
범위: `src/daesingo/search/**`, `tests/search/**`, `docs/modules/search/**`  
상태: 구현 전 계획

## 0. 기준과 범위

이 문서는 Gemini 기반 Coarse→Fine 교통 사건 탐지를 개선하기 위한 Search 내부 구현 계획이다.
법적 위반을 Gemini가 확정하지 않고, Gemini는 시각적으로 관찰되는 사실과 시간 관계만 반환한다.

변경하지 않는 공개 구조는 다음과 같다.

- `CandidateEvent`
- `VisualEvidence`
- `Primitive`
- `TemporalFact`
- `AnalysisScope`
- `VisualEventType`
- 모듈 간 계약 버전과 다른 모듈 import

### 현재 기준의 불일치

- 현재 checkout은 `fix/search-fine-padded-window`이다. 기준으로 제시된 `develop`에는 아직 `src/daesingo/search`가 없다.
- 요청에 언급된 `fine-p2*` resource는 현재 tree에 없고, runtime은 `coarse-p3`와 `fine-p3*`를 사용한다.
- 따라서 이 계획의 실제 code baseline은 현재 worktree의 Search runtime이며, 병합 대상은 `develop`이다.

## A. 현재 구조

```text
AnalysisScope
  → coarse.search_coarse()
  → GeminiProvider.search_coarse()
  → CoarseResponse / CoarseCandidate              (Search-private wire schema)
  → coarse._candidate()
  → CandidateEvent                                (공개 계약)

선택 CandidateEvent
  → fine.verify_fine()
  → candidate core span ± fine_padding_sec
  → MediaPreparer.prepare_fine()
  → PreparedMedia
  → GeminiProvider.verify_fine()
  → FineResponse                                  (Search-private wire schema)
  → _clip_relative_temporal_facts()
  → VisualEvidence                                (공개 계약)
```

현재 구현의 핵심 위치는 다음과 같다.

| 파일 | 현재 책임 |
| --- | --- |
| `schemas.py` | `CoarseResponse`와 범용 `FineResponse` wire schema |
| `provider.py` | Gemini structured-output 호출; Fine은 항상 `FineResponse` 사용 |
| `coarse.py::_candidate()` | `score`를 `ranking_score`로 전달, `at_sec`를 representative 시각으로 사용 |
| `fine.py::verify_fine()` | candidate padded clip 준비 후 public evidence 생성 |
| `fine.py::_clip_relative_temporal_facts()` | clip-relative offset 범위 검증 후 그대로 public TemporalFact에 전달 |
| `media.py::MediaPreparer.prepare_fine()` | prepared clip의 원본 시작/끝을 `PreparedMedia`에 보존 |

현재 wire schema와 public 계약 사이에는 직접 변환 경로가 있다. `fine.py`는 model dump를 `Target`, `Primitive`, `Uncertainty`에 거의 그대로 넣으므로 Gemini의 자유 문자열과 reference가 public model로 흐른다.

## B. 발견된 문제와 해결 방향

| 문제 | 근거 | 실패 가능성 | Search 내부 해결 | 외부 영향 |
| --- | --- | --- | --- | --- |
| Fine schema가 사건 비특화 | `schemas.py::FineResponse` | 필수 시각 predicate 없이 `OBSERVED` 가능 | 유형별 detailed Fine response 도입 | adapter만 public evidence 생성 |
| 세 verification 상태의 의미 검증 부재 | `FineResponse.check_event_type()` | 가림을 `NOT_OBSERVED`, blocker 없는 `UNCERTAIN`으로 반환 | 상태별 semantic validator | `Verification` enum 유지 |
| 직접 public model 변환 | `fine.py::verify_fine()` | 임의 `kind`, `fact`, `evidence_refs` 유입 | canonical adapter 사용 | public field 미변경 |
| 요청/응답 사건 유형 결속 없음 | `provider.py::verify_fine()` | SIGNAL 요청에 다른 유형 응답 수용 | event-type-specific response model 및 discriminator 검사 | 외부 API 미변경 |
| evidence ref가 실제 입력과 연결되지 않음 | `FineTarget`, `FinePrimitive`, `FineTemporalFact` | Gemini가 임의 `fr_*` ID 생성 | request allowlist와 membership validator | `evidence_refs` 타입 유지 |
| Coarse score 의미 과부하 | `CoarseCandidate.score`, `coarse._candidate()` | 확률 또는 법 위반 confidence로 오해 | candidate strength enum과 결정적 score adapter | `ranking_score` 유지 |
| critical timestamp가 필수 | `CoarseCandidate.at_sec` | 모르는 시각을 억지로 생성 | nullable critical timestamp와 midpoint fallback | `representative_ms` 유지 |
| 중복 coarse candidate 제어 없음 | `coarse.py` 정렬 | 같은 연속 사건의 Fine 반복 비용 | prompt 규칙 + 보수적 exact duplicate coalescing | 다른 event type은 병합 금지 |
| Fine prompt에 core/padding 구분 부족 | `provider.py`, `fine-p3.txt` | context와 critical fact 혼합 | 두 구간과 clock을 모두 render | public model 미변경 |

## C. p4 설계 결정

### C.1 유형별 Fine wire schema

`schemas.py`에 아래 Search-private 모델을 둔다.

```text
FineResponseEnvelope
├─ SignalFineResponse
├─ CenterLineCrossingFineResponse
├─ SolidLineLaneChangeFineResponse
└─ MotorcycleHelmetNonUseFineResponse
```

공통 envelope는 다음을 갖는다.

```text
event_type
verification
target
temporal_relation
blocking_uncertainties
context_facts
critical_event_offsets_ms
```

각 predicate는 고정 field이며 내부 `PredicateState`를 사용한다.

```text
OBSERVED | NOT_OBSERVED | UNCERTAIN
```

필수 field는 다음과 같다.

| 유형 | fixed predicate |
| --- | --- |
| SIGNAL | `subject_vehicle`, `subject_role`, `movement_direction`, `applicable_signal`, `signal_state_before_crossing`, `signal_state_at_crossing`, `stop_line_or_intersection_boundary`, `crossing_event`, `crossing_observation_mode`, `temporal_relation` |
| CENTER_LINE_CROSSING | `road_direction_structure`, `centerline_identity`, `centerline_marking_type`, `vehicle_side_before`, `contact_state`, `crossing_extent`, `vehicle_side_after`, `persistence`, `local_road_geometry` |
| SOLID_LINE_LANE_CHANGE | `stable_in_origin_lane`, `lateral_transition`, `divider_overlap`, `divider_crossing`, `stable_in_target_lane`, `divider_identity`, `marking_at_crossing`, `crossing_time` |
| MOTORCYCLE_HELMET_NON_USE | `motorcycle_present`, `rider_association`, `rider_role`, `head_region_visibility`, `helmet_like_object`, `visibility_sufficient_for_absence` |

`CENTER_LINE_CROSSING.crossing_extent`는 다음 enum을 사용한다.

```text
NONE | CONTACT_ONLY | PARTIAL_CROSSING | SUBSTANTIAL_CROSSING | FULL_CROSSING | UNCERTAIN
```

### C.2 상태 semantic validator

- `OBSERVED`: 모든 mandatory predicate가 observed이고 temporal relation도 일관되어야 하며 blocker가 없어야 한다.
- `NOT_OBSERVED`: 충분한 관찰 가능성, 명시적으로 반박된 mandatory predicate, 해당 predicate와 일치하는 `contradicted_predicates`가 있어야 한다.
- `UNCERTAIN`: unreliable predicate와 적어도 하나의 blocking uncertainty가 있어야 한다.

`NOT_OBSERVED`는 가림·화질·sampling 간격·원근·대상 혼동만으로 만들 수 없다. 보이지 않음은 `UNCERTAIN`이다.

고정 uncertainty code는 예를 들어 다음과 같다.

```text
OCCLUSION
OUT_OF_FRAME
INSUFFICIENT_RESOLUTION
SAMPLING_GAP
PERSPECTIVE_AMBIGUITY
TARGET_AMBIGUITY
SIGNAL_ASSOCIATION_AMBIGUITY
ROAD_MARKING_IDENTITY_AMBIGUITY
```

### C.3 Provider response model 선택

`provider.py`에 `fine_response_model_for(event_type)` mapping을 둔다.

```text
SIGNAL → SignalFineResponse
CENTER_LINE_CROSSING → CenterLineCrossingFineResponse
SOLID_LINE_LANE_CHANGE → SolidLineLaneChangeFineResponse
MOTORCYCLE_HELMET_NON_USE → MotorcycleHelmetNonUseFineResponse
```

Gemini SDK에는 mapping에서 나온 concrete Pydantic model을 `response_format`으로 전달한다. parsed response의 event type literal도 `FineRequest.event_type`과 다시 비교한다.

### C.4 Public VisualEvidence adapter

`fine.py::_adapt_fine_response()`가 상세 wire response를 다음 순서로 변환한다.

```text
detailed wire response
  → semantic validation
  → canonical internal evidence record
  → Target
  → Primitive(kind=고정 canonical key)
  → TemporalFact
  → Uncertainty(kind=고정 canonical code)
  → VisualEvidence
```

Gemini는 public `Primitive.kind`, `TemporalFact.fact`, `Uncertainty.kind`를 직접 정하지 않는다. adapter가 `signal.applicable_signal`, `centerline.crossing_extent`, `lane_change.marking_at_crossing` 같은 canonical string을 생성한다.

`VisualEvidence.visual_event_type`은 observed일 때에만 요청한 event type으로 설정하고, 다른 상태에서는 `None`으로 둔다. `legal_status=None`도 유지한다.

### C.5 Evidence reference 통제

`FineRequest`에 `allowed_evidence_refs: frozenset[str]`를 추가한다. 현재 video-only Fine 입력에는 addressable frame inventory가 없으므로 빈 집합이다.

- wire response의 ref는 frame-ref 형식과 request allowlist membership을 모두 통과해야 한다.
- allowlist가 비어 있으면 response ref도 빈 tuple만 허용한다.
- 추후 실제 keyframe을 Fine 입력으로 전달할 경우에만 그 frame ID를 allowlist에 넣는다.
- clip-relative offset은 frame ID의 대체가 아닌 temporal anchor다.

### C.6 Coarse candidate strength

`score` 대신 `CandidateStrength`를 wire schema로 사용한다.

```text
STRONG    → 1.0
PLAUSIBLE → 0.6
AMBIGUOUS → 0.3
```

`CandidateEvent.ranking_score`에는 위 adapter 값만 넣는다. 이는 발생확률 또는 법 위반 확률이 아니다. 동점은 허용한다.

정렬 순서는 다음과 같이 고정한다.

```text
candidate_strength 내림차순
→ span.start_sec 오름차순
→ critical_at_sec 또는 span midpoint 오름차순
→ event_type
→ provider response 원래 순서
```

`critical_at_sec`은 nullable로 만들고, 없으면 public `representative_ms`는 span midpoint로 생성한다. 이 경우 `CandidateEvent.uncertainties`에 `CRITICAL_TIMESTAMP_UNCERTAIN`을 기록한다.

동일 차량의 동일 연속 물리 사건은 prompt에서 한 candidate로 반환하게 하고, application은 같은 event type·정규화된 subject description·거의 같은 span인 exact duplicate만 보수적으로 coalesce한다. 서로 다른 event type은 시간이 겹쳐도 분리한다.

### C.7 Prompt version

기존 p3는 불변으로 둔다.

```text
coarse-p3 → coarse-p4
fine-p3 → fine-p4
fine-p3-signal → fine-p4-signal
fine-p3-center-line-crossing → fine-p4-center-line-crossing
fine-p3-solid-line-lane-change → fine-p4-solid-line-lane-change
fine-p3-motorcycle-helmet-non-use → fine-p4-motorcycle-helmet-non-use
```

`prompts.py`는 p4를 선택한다. Fine fingerprint는 common prompt와 type delta를 결합한 텍스트에서 계속 계산하며, ledger에는 version 및 type-specific fingerprint를 기록한다. rollback은 p3 resource와 p3 parser adapter를 유지한 상태에서 prompt selection을 되돌리는 방식으로 한다.

## D. 시간 좌표: 구현 계획과 blocker

### D.1 내부 모델

```text
FineRequest
  candidate_core_start_sec
  candidate_core_end_sec
  prepared_clip_start_sec
  prepared_clip_end_sec
  allowed_evidence_refs

Fine response
  context_facts[].clip_offset_ms
  critical_event_offsets_ms
  predicate별 observation offsets

fine.py::_rebase_temporal_facts()
  clip_offset_ms + prepared.origin_start_sec = internal original_timeline_ms
```

검증 규칙:

- 모든 model offset은 prepared clip 전체 범위 안이어야 한다.
- rebased original timestamp는 source duration을 넘으면 안 된다.
- context fact는 leading/trailing padding 모두 허용한다.
- critical event timestamp만 candidate core와의 관계를 따로 검증한다.
- core 바깥 critical timestamp는 context로 자동 승격하지 않고 semantic inconsistency로 처리한다.
- prompt는 critical과 context의 구분을 요구하지만, 모델이 알 수 없는 내부 계약 불변조건을 강요하지 않는다.

### D.2 공개 시간 좌표 blocker

현재 runtime과 `fine-temporal-offset-base-2026-09-22.md`의 확정 의미는 다음과 같다.

| 항목 | 현재 의미 |
| --- | --- |
| Gemini `at_offset_ms` | prepared clip 시작점 기준 |
| `VisualEvidence.temporal_facts[].at_offset_ms` | clip-relative 값을 그대로 방출 |
| 기존 tests | clip-relative offset이 유지됨을 검증 |

따라서 original-timeline millisecond를 existing `TemporalFact.at_offset_ms`에 넣으면 public field 의미가 바뀐다. `VisualEvidence`에는 clip origin을 함께 전달할 public field도 없다.

Search 내부만으로 가능한 안전한 동작은 internal original timestamp를 계산·검증하되, 외부 `TemporalFact`에는 현 clip-relative contract를 유지하는 것이다.

다음 중 하나를 계약 소유자가 결정하기 전에는 “외부 original-timeline timestamp”와 “외부 시간 의미 변경 없음”을 동시에 달성할 수 없다.

1. `TemporalFact.at_offset_ms`를 original timeline 기준으로 재정의한다.
2. 공개 계약에 original timestamp field를 추가한다.
3. consumer가 prepared clip origin metadata를 별도 계약으로 받는다.

이 문서의 Search-only 계획은 public 계약을 우회하거나 `case`, `evidence`, `eval`, `readout`, `contracts`를 수정하지 않는다.

## E. 파일별 수정 계획

| 파일 | 클래스·함수 | 변경 | 이유 | 호환성 | 테스트 |
| --- | --- | --- | --- | --- | --- |
| `src/daesingo/search/schemas.py` | `CoarseCandidate`, `FineResponse` | strength, nullable critical timestamp, detailed Fine union, enums, validators | wire 의미 고정 | public model 미변경 | `test_gemini_components.py`, `test_fine_media_flow.py` |
| `src/daesingo/search/provider.py` | `FineRequest`, `SearchProvider`, `GeminiProvider.verify_fine()` | core/padded window, refs, response model dispatch | request-response 결속 | internal protocol만 변경 | `test_provider_bounds.py`, `test_smoke_provider.py` |
| `src/daesingo/search/fine.py` | `_clip_relative_temporal_facts()`, `verify_fine()`, `_adapt_fine_response()` | anchor validation, internal rebase, semantic gate, public adapter | 상태·시간·문자열 통제 | public structure 유지 | `test_fine_media_flow.py`, `test_fine_candidate.py` |
| `src/daesingo/search/coarse.py` | `_candidate()`, `_rank_candidates()`, `_coalesce_exact_duplicates()` | strength mapping, fallback, deterministic ranking | score 의미 개선 | CandidateEvent 유지 | `test_coarse_boundaries.py` |
| `src/daesingo/search/prompts.py` | prompt constants, `fine_prompt_for()` | p4 선택과 placeholder union | render/fingerprint 정확성 | public API 유지 | `test_gemini_components.py` |
| `src/daesingo/search/prompt_resources/coarse-p4.txt` | 신규 | recall-first operational definition, nullable critical time, duplicate rule | legal conclusion 방지 | 없음 | prompt tests |
| `src/daesingo/search/prompt_resources/fine-p4.txt` | 신규 | 3-value rule, core/padding/clock, refs, critical/context | validator와 동일 의미 | 없음 | prompt tests |
| `src/daesingo/search/prompt_resources/fine-p4-signal.txt` | 신규 | signal association과 temporal order | 다른 방향 신호 오판 방지 | 없음 | type tests |
| `src/daesingo/search/prompt_resources/fine-p4-center-line-crossing.txt` | 신규 | centerline identity, geometry, extent | x좌표/색상 추론 방지 | 없음 | type tests |
| `src/daesingo/search/prompt_resources/fine-p4-solid-line-lane-change.txt` | 신규 | transition과 solid crossing 독립 검증 | 점선/접촉 사례 구분 | 없음 | type tests |
| `src/daesingo/search/prompt_resources/fine-p4-motorcycle-helmet-non-use.txt` | 신규 | rider/head visibility/absence sufficiency | head 미가시 오판 방지 | 없음 | type tests |
| `src/daesingo/search/smoke_fixture.py` | fixture response typing | detailed response parser 지원 | smoke regression | external fixture 미변경 | `test_smoke_provider.py` |
| `tests/search/fixtures/smoke_provider.json` | Fine mock payload | complete p4 detailed response | strict parser regression | Search fixture만 변경 | `test_smoke_provider.py` |

`media.py`, `visual.py`, `runs.py`, `scope.py`는 공개 계약을 유지하기 위해 수정하지 않는다.

## F. 단계별 구현 순서

1. **Characterization test 고정**: 현재 p3 clip-relative behavior, padding 허용, public dump shape, ledger metadata를 고정한다.  
   완료 조건: 기존 public payload와 p3 회귀 test가 통과한다.

2. **내부 schema와 enum 추가**: detailed Fine response, fixed evidence key, uncertainty code, candidate strength를 추가한다.  
   완료 조건: 4개 유형의 valid/invalid schema test가 통과한다.

3. **Fine 시간 모델 정리**: FineRequest window metadata와 internal anchor/rebase validator를 구현한다.  
   완료 조건: context padding 허용, clip/source 범위 거부, critical/core 관계 test가 통과한다.

4. **Fine adapter 구현**: detailed response를 기존 public evidence로 변환한다.  
   완료 조건: 모든 verification 상태가 기존 public schema로 변환된다.

5. **Fine p4 prompt 추가**: common prompt와 event-specific delta를 추가한다.  
   완료 조건: placeholder, fingerprint, core/padding clock test가 통과한다.

6. **Coarse p4/ranking 개선**: strength mapping, nullable critical timestamp, fallback, duplicate suppression을 구현한다.  
   완료 조건: tie/fallback/out-of-range test가 통과한다.

7. **Provider 연결 변경**: event-specific `response_format`과 discriminator 검증을 연결한다.  
   완료 조건: request type마다 정확한 Pydantic model이 SDK에 전달된다.

8. **전체 Search 회귀 검증**: `tests/search` 전체, smoke, media flow, public API를 실행한다.  
   완료 조건: public fixture와 downstream loading이 type 변경 없이 통과한다.

9. **문서 갱신**: p3/p4 차이, 평가 조건, time-coordinate blocker를 기록한다.  
   완료 조건: proposal/runtime/contract 차이와 rollback 방법이 명시된다.

## G. 테스트 계획과 수용 기준

### Prompt

- 모든 placeholder가 채워진다.
- type-specific Fine common block과 delta가 결합된다.
- prompt version과 fingerprint가 ledger에 기록된다.
- clip-relative clock, candidate core, padded clip 범위가 prompt에 포함된다.

### Schema

- 4개 유형의 정상 응답이 통과한다.
- required evidence 없는 `OBSERVED`가 거부된다.
- blocker 없는 `UNCERTAIN`이 거부된다.
- 관찰 불충분 `NOT_OBSERVED`가 거부된다.
- 요청/응답 event type mismatch가 거부된다.
- extra field가 계속 거부된다.

### 시간

- leading/trailing padding context fact가 허용된다.
- prepared clip 또는 source 범위 밖 offset이 거부된다.
- critical과 context timestamp가 구분된다.
- public original-timeline 방출은 blocker가 해소될 때까지 활성화하지 않는다.

### 변환 및 Coarse

- 유형별 detailed response가 기존 `VisualEvidence`로 변환된다.
- `CandidateEvent`와 `VisualEvidence` type 및 payload shape는 변경되지 않는다.
- strength 동점이 허용된다.
- critical timestamp 미상 후보는 deterministic midpoint fallback과 uncertainty를 가진다.
- source duration 밖 span/timestamp는 계속 거부된다.

## Search 내부에서 변경되는 항목

- Gemini Coarse/Fine p4 prompt와 type delta
- Search-private Pydantic wire schema 및 enum
- Fine semantic validator와 public-contract adapter
- FineRequest core/padded clip metadata
- provider response model dispatch
- evidence reference allowlist
- Coarse strength, ranking, fallback, duplicate suppression
- Search tests, smoke fixture, Search decision documents

## Search 외부에서 변경되지 않는 항목

- `src/daesingo/case/**`
- `src/daesingo/evidence/**`
- `src/daesingo/eval/**`
- `src/daesingo/readout/**`
- `frontend/**`
- `contracts/**`
- `CandidateEvent`, `VisualEvidence`, `Primitive`, `TemporalFact`, `AnalysisScope`, `VisualEventType`
- 계약 버전, 다른 모듈 import, 다른 모듈 fixture
