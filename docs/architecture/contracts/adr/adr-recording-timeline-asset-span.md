# [ADR]RecordingTimeline · AssetSpan · TimeSourceCandidate

# ADR-[작성 필요]: `RecordingTimeline + AssetSpan + TimeSourceCandidate` Data Contract 확정

**Status:** Accepted

> **후속 변경 (2026-09-08):** 보조 구조 `SpanResolution`이 `span-resolution/v1.1` — top-level `failure: {kind, code} | null`(키 항상 존재) 추가 · `MissingRange.reason`에 `OUT_OF_TIMELINE_RANGE` 추가 · 위치 특정 불가 `FAILED`의 완전성 예외. Decider 정철원, 확인 김준영·서어진. 근거·기각안 `adr-data-contract-call-closure-2026-09-08.md` §4.3. 2026-09-07의 완전성 규칙(B06)은 `adr-data-contract-call-closure-2026-09-07.md` §4.5. 아래 본문은 당시 결정 기록이며 고치지 않았다.

**Contract:** `RecordingTimeline + AssetSpan + TimeSourceCandidate`

**Producer:** `recording`

**Consumer:** `search`, `evidence`

**Owner:** 정철원

**결정일:** `9/4`

**관련 Contract Version:** `[작성 필요 — 통합 Final Contract 단일 버전 미지정]`

**관련 Architecture Version:** 대신고 Module Architecture v4

> 이 ADR은 세 개의 recording Core Contract를 하나의 **통합 Final Data Contract**로 확정한 결정 기록이다. 새로운 설계를 제안하지 않고, 각 Draft의 A/B/C안과 Consumer Review를 거쳐 Final Contract에서 채택된 구조만 기록한다.
> 

## 관련 문서

- Product Spec
- 대신고 Module Architecture v4
- `RecordingTimeline` Data Contract Draft + Consumer Review
- `AssetSpan` Data Contract Draft + Consumer Review
- `TimeSourceCandidate` Data Contract Draft + Consumer Review
- Final Data Contract — `RecordingTimeline + AssetSpan + TimeSourceCandidate`
- recording / search / evidence Architecture Input Memo

---

# 1. 결정 배경(Context)

## Producer가 생성하는 것

`recording`은 블랙박스 Source/File/MediaStream을 조사해 다음 데이터를 생성한다.

- 여러 Source를 하나의 논리 시간축으로 정렬한 `RecordingTimeline`
- 논리 시간 범위를 실제 Source/MediaStream 구간으로 변환한 `AssetSpan`
- 파일명, file metadata, 제조사 metadata에서 관찰한 절대시간 후보인 `TimeSourceCandidate`

블랙박스는 여러 분할 파일로 구성될 수 있고, 한 물리 파일 안에도 front/rear/audio 등 복수 MediaStream이 있을 수 있다. 따라서 `file = video stream`으로 단순화할 수 없고, 파일 경계와 stream 선택을 Consumer마다 다시 계산하게 해서는 안 된다. `RecordingTimeline` Draft에서도 실제 AVI의 multi-stream 구조와 absolute timestamp가 없는 경우를 주요 제약으로 확인했다.

## Consumer가 필요로 하는 것

`search`는 실제 물리 파일의 개수나 경계를 몰라도 하나의 relative timeline에서 사건 범위를 찾을 수 있어야 한다. 실제 VLM 분석 단계에서는 해당 논리 구간을 실제 영상 source로 변환할 수 있어야 한다.

`evidence`는 파일 기반 Timestamp가 최종값이라고 가정하지 않고, `recording`의 후보와 `readout`의 Overlay Timestamp, 사용자 입력 등을 함께 비교해 최종 발생시각을 결정해야 한다.

또한 Evidence는 사건 구간 중 일부 Source가 빠진 경우 이를 완전한 Evidence로 오해하지 않도록 resolution completeness를 추적할 수 있어야 한다.

## 계약을 고정해야 했던 이유

계약을 고정하지 않으면 다음 문제가 발생한다.

- `recording`과 `evidence`가 각각 Timestamp를 판단해 책임이 중복될 수 있음
- Search가 파일명이나 metadata 정책에 직접 의존할 수 있음
- Consumer별로 파일 경계 및 overlap을 다시 계산할 수 있음
- `SourceAsset`과 `MediaStream`이 같은 개념처럼 사용될 수 있음
- partial success와 전체 실패를 빈 배열 하나로 구분하지 못할 수 있음
- Timeline rebase 후 과거 Search/Evidence의 provenance가 달라질 수 있음
- Timestamp 후보가 없는 이유와 parser 실패를 동일하게 취급할 수 있음

따라서 `recording`의 **관찰·시간축 구성·물리 구간 해석 책임**과 downstream의 **분석·확정 책임**을 Contract 수준에서 고정할 필요가 있었다.

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| Timestamp 수집과 최종 판정을 분리 | Module Architecture v4 | `recording`은 후보를 수집하고 `evidence`가 최종 `TimeResolution` 수행 |
| Search는 사건 구간을 찾고 실제 신고 영상을 만들지 않음 | Module Architecture v4 | 사건은 timeline range로 표현하고 실제 Source 경계 변환은 `recording.resolve_span()`이 담당 |
| 한 SourceAsset에 복수 MediaStream이 존재할 수 있음 | recording 실측 / Architecture | `AssetSpan`에 Source와 Stream reference를 분리 |
| `creation_time`이 없는 Source가 실제 존재 | recording 실측 | absolute anchor가 없어도 relative timeline을 유지 |
| Metadata/Filename은 확정 Timestamp가 아니라 후보 | evidence Memo / Architecture | 모든 공식 후보를 보존하고 우선순위 선택은 Evidence에 남김 |
| 파일 일부/stream 일부 실패가 전체 recording 실패는 아님 | Module Architecture v4 | `SpanResolution`의 PARTIAL + `missing_ranges` 채택 |
| Search는 실제 provider용 영상 입력을 필요로 함 | search Consumer Review | AssetSpan에는 storage URI를 넣지 않고 후속 `AnalysisSource`에서 보장 |
| Source 위치와 absolute timestamp의 대응 관계가 필요 | search/evidence Consumer Review | `TimeSourceCandidate`에 `source_asset_ref + source_offset_sec` 포함 |
| 정보 없음과 parser failure는 의미가 다름 | Observation 원칙 / evidence Review | Candidate 부재 이유를 `TimeSourceCheck`로 분리 |
| Timestamp source 간 공통 numeric confidence 근거가 없음 | evidence Review | `TimeSourceCandidate.confidence` 제거 |

---

# 3. 검토했던 주요 선택지

# 결정 1. RecordingTimeline의 absolute 기준시간 처리

### A안 — Authoritative Anchor

`recording`이 하나의 absolute timestamp를 선택하여 Timeline의 authoritative 기준시각으로 확정한다.

**장점**

- Search의 absolute time 계산이 단순함

**단점**

- `recording`이 사실상 Timestamp 판정 책임을 가지게 됨
- 잘못된 값이 모든 downstream 시간에 영향을 줌
- `evidence`의 최종 Timestamp Resolver와 책임 충돌

### B안 — Working Anchor + 전체 후보 보존

Timeline 계산을 위해 하나의 working 기준값은 사용할 수 있지만, 모든 `TimeSourceCandidate`를 함께 보존하고 최종 판정과 구분한다.

**장점**

- Search는 timeline 계산에 사용할 수 있음
- Evidence는 후보 전체를 다시 비교할 수 있음
- 관찰과 확정 책임을 분리할 수 있음

**단점**

- `anchor`라는 용어를 확정값으로 오해할 수 있음

---

# 결정 2. Timestamp 후보 보존 및 conflict 책임

### A안 — 하나의 후보만 Producer가 선택

**장점**

- 구조 단순

**단점**

- 후보 충돌 정보가 사라짐
- Producer가 Timestamp priority를 사실상 결정

### B안 — 모든 후보 보존 + recording이 비교값 제공

파일 기반 후보를 모두 보존하고 `max_delta_sec` 등의 객관적 비교값을 recording에서 미리 계산한다.

**장점**

- Consumer의 반복 계산 감소

**단점**

- Overlay/User Input까지 포함한 Evidence 최종 비교와 다른 의미의 delta가 생길 수 있음

### C안 — 모든 후보만 보존하고 비교는 Evidence에서 수행

**장점**

- 모든 시간 근거를 동일 단계에서 비교 가능
- Timestamp 판단 책임이 Evidence에 일원화

**단점**

- Evidence가 비교 계산을 직접 수행해야 함

---

# 결정 3. RecordingTimeline의 File/Stream 표현

### A안 — SourceAsset만 기준으로 Timeline 구성

**장점**

- 구조가 단순함

**단점**

- 하나의 Source에 여러 video/audio stream이 존재할 때 실제 pixel source가 불명확

### B안 — Stream별 별도 Timeline

**장점**

- Stream 시간축을 정확히 표현

**단점**

- 동일 recording에 여러 timeline이 생겨 복잡도가 큼

### C안 — 하나의 Source Timeline + MediaStream Reference

하나의 논리 RecordingTimeline을 유지하고 Source placement에 MediaStream refs를 연결한다.

**장점**

- 하나의 logical timeline 유지
- `SourceAsset != MediaStream` 원칙 보존
- 실제 stream 선택은 `resolve_span()`에서 집중 처리 가능

**단점**

- Source/Stream 관계 표현이 A안보다 복잡함

---

# 결정 4. Absolute Timestamp가 없는 Timeline 처리

### A안 — Absolute Anchor 없으면 Timeline 실패

**장점**

- 항상 wall-clock time을 갖는 단순 계약

**단점**

- 실제 정상 Source도 Search 불가능해짐
- `UNKNOWN != ERROR` 원칙과 맞지 않음

### B안 — Relative Timeline 유지

absolute anchor가 없어도 Source 순서와 duration을 이용해 relative timeline은 정상 제공한다.

**장점**

- Search를 계속 수행할 수 있음
- 이후 Overlay/User Input 등 다른 Timestamp 근거로 보완 가능

**단점**

- Consumer가 absolute와 relative 상태를 구분해야 함

---

# 결정 5. Timeline Rebase와 과거 결과

### A안 — 동일 객체를 in-place 수정

**장점**

- 최신 상태 하나만 관리

**단점**

- 과거 Search/Evidence가 어떤 기준을 사용했는지 재현하기 어려움

### B안 — 동일 Timeline ID + Revision 증가

**장점**

- logical recording identity 유지
- 과거 실행 provenance 보존
- Pixel Search 결과를 불필요하게 다시 실행하지 않아도 됨

**단점**

- Consumer가 revision reference를 보존해야 함

### C안 — Rebase마다 새 Timeline ID

**장점**

- 불변성이 명확함

**단점**

- 동일 recording이라는 관계를 추가로 관리해야 함

---

# 결정 6. AssetSpan과 resolve_span 결과 구조

### A안 — `AssetSpan = 단일 조각`, `AssetSpan[]` 직접 반환

**장점**

- 단순함
- 기존 Architecture의 `AssetSpan[]` 표현과 일치

**단점**

- PARTIAL/FAILED를 배열만으로 구분하기 어려움
- 누락 구간을 알 수 없음

### B안 — AssetSpan 자체가 전체 resolution을 소유

`segments[]`를 가진 하나의 큰 AssetSpan을 반환한다.

**장점**

- 요청 전체 상태 표현이 쉬움

**단점**

- `AssetSpan = 실제 물리 조각 하나`라는 의미가 사라짐

### C안 — Resolution Wrapper + `AssetSpan[]`

`SpanResolution`이 전체 요청 상태를 소유하고, `AssetSpan`은 실제 사용 가능한 물리 조각 하나의 의미를 유지한다.

**장점**

- complete/partial/failure 표현 가능
- 누락 구간 추적 가능
- AssetSpan의 단일 의미 유지

**단점**

- Wrapper 구조가 추가됨

---

# 결정 7. AssetSpan의 Stream 및 시간 좌표 표현

### A안 — SourceAsset + source-local range만 제공

**장점**

- 최소 구조

**단점**

- 실제 어떤 Stream의 pixel인지 불명확
- 원래 Timeline 위치 재구성이 필요

### B안 — SourceAsset + MediaStream + Timeline/Source 두 Range

**장점**

- 실제 pixel source 재현 가능
- logical → physical mapping 명확
- Search/Evidence provenance에 유리

**단점**

- 같은 시간 개념을 두 좌표계로 관리해야 함
- Producer가 두 범위의 정합성을 보장해야 함

---

# 결정 8. TimeSourceCandidate 표현

### A안 — 단순 datetime

**장점**

- 구조 단순

**단점**

- 그 시간이 Source의 어느 위치에 대응하는지 알 수 없음

### B안 — Source 위치 ↔ Absolute Time Mapping

`source_asset_ref + source_offset_sec + value`를 함께 보존한다.

**장점**

- 사건 시각 계산 provenance 재현 가능
- 파일 경계가 있어도 의미가 명확

**단점**

- 단순 datetime보다 구조가 커짐

---

# 결정 9. Candidate 미생성 및 Confidence 처리

### Candidate 미생성

#### A안 — 후보가 없으면 그냥 배열에 넣지 않음

단순하지만 `정보 없음 / 미지원 / parser 실패`를 구분할 수 없다.

#### B안 — `value=null` Candidate 생성

부재 이유 표현은 가능하지만 Candidate의 “실제 관찰값” 의미가 흐려진다.

#### C안 — Candidate와 Source Check 분리

실제 값이 있으면 Candidate를 생성하고, 미생성 이유는 별도 `TimeSourceCheck`로 남긴다.

### Confidence

#### A안 — numeric confidence 필수

객관적 source 간 공통 점수의 근거가 없음.

#### B안 — confidence 없음

명시적인 parse/status/provenance만 사용한다.

#### C안 — optional confidence

향후 확장은 가능하지만 현재 Consumer 사용처가 없고 오용 가능성이 있음.

---

# 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| Timeline absolute 기준 | B안 + `working_anchor` 명칭 | B안 | Evidence가 `anchor` 이름 수정 요청 | **수정** |
| Timestamp 후보 | 모든 후보 보존 | B안 | Search/Evidence 동의 | 유지 |
| Candidate 비교/delta | Evidence에서 계산 | recording raw delta 제공 추천 | Evidence가 제거 요청 | **변경** |
| Timeline File/Stream 모델 | C안 | C안 | Search 동의 | 유지 |
| Absolute anchor 없음 | B안 — relative 유지 | B안 | Search/Evidence 동의 | 유지 |
| Timeline rebase | B안 — same ID + revision | B안 | Search/Evidence 동의 | 유지 |
| AssetSpan 의미 | 단일 물리 조각 | A안 기본 | Search/Evidence 동의 | 유지 |
| resolve_span 반환 | C안 — `SpanResolution` | A안 기본, C안 검토 | Search/Evidence 모두 wrapper 요청 | **변경** |
| Partial failure | `PARTIAL + missing_ranges` | B안 선호 | Search/Evidence 명시적 요청 | **확정** |
| AssetSpan Stream | `media_stream_ref` 필수 | B안 | Search/Evidence 동의 | 유지 |
| AssetSpan 좌표 | timeline + source 둘 다 | B안 | Search 동의 | 유지 |
| File overlap | 내부 처리 + logical mapping 보장 | A안 | Search 조건부 승인 | **보장 강화** |
| Storage path/URL | AssetSpan에서 제외 | B안 | Search 조건부 승인 | 유지 |
| AssetSpan lifecycle | immutable snapshot | B안 | Search/Evidence 동의 | 유지 |
| TimeCandidate local validation | 포함 | B안 | Search/Evidence 동의 | 유지 |
| TimeCandidate source 표현 | `source_kind + source_detail` | B안 | Search/Evidence 동의 | 유지 |
| Candidate 기준 위치 | Source ref + offset | B안 | Search/Evidence 동의 | 유지 |
| Candidate 미생성 | C안 — `TimeSourceCheck` | A/C 검토 | Evidence가 C안 요청 | **변경** |
| Numeric confidence | 제거 | C안 optional | Evidence가 B안 요청 | **변경** |
| Candidate conflict | Evidence에서만 계산 | C안 일부 | Evidence가 Timeline delta까지 제거 요청 | **변경** |
| Search의 TimeCandidate 소비 | Direct Consumer 아님 | 확인 필요 | Search가 제거 요청 | **변경** |

---

## 결정 1. `working_anchor`와 Relative Timeline

**최종 선택:** Working Anchor + 모든 Timestamp 후보 보존, absolute 값이 없어도 relative timeline 유지.

**결정 내용:**

Timeline 계산에 사용할 absolute 기준값이 존재하면 `working_anchor`로 표현한다. 이는 확정 Timestamp가 아니며 가능하면 `TimeSourceCandidate`를 reference한다. 값이 없더라도 relative timeline이 유효하면 Timeline을 usable 상태로 유지한다.

**선택 이유:**

- `recording`이 최종 Timestamp를 확정하면 evidence ownership과 충돌한다.
- Search는 절대시각 없이 relative offset만으로 Coarse/Fine Search를 수행할 수 있다고 확인했다.
- Evidence 역시 anchor가 없어도 Overlay/User Input 등의 다른 근거를 사용해 resolution할 수 있다고 확인했다.
- Evidence가 `anchor`라는 명칭은 확정값으로 오해될 수 있다고 지적하여 Final에서는 `working_anchor`로 변경했다.

---

## 결정 2. Timestamp 후보 비교 책임은 Evidence로 일원화

**최종 선택:** `recording`은 모든 `TimeSourceCandidate`를 보존하지만 후보 간 delta/conflict를 계산하지 않는다.

**결정 내용:**

Final Contract에서 `candidate_comparison`, `source_conflict`, `max_delta_sec`, `conflict_severity`, `selected_source`를 제거한다.

**선택 이유:**

- Evidence는 파일 후보뿐 아니라 Overlay Timestamp와 사용자 입력까지 전체 시간 근거를 비교해야 한다.
- 파일 후보만으로 recording이 계산한 delta와 Evidence의 최종 delta가 서로 다른 의미가 될 수 있다.
- 어떤 후보를 비교 대상에 포함할지 자체가 Evidence 판단에 속한다.

Evidence Consumer는 이러한 이유로 RecordingTimeline의 raw delta 제공 추천을 명시적으로 거부했다.  TimeSourceCandidate Review에서도 같은 이유로 conflict/delta를 Evidence 책임으로 일원화해 달라고 요청했다.

---

## 결정 3. 동일 Timeline ID + Revision

**최종 선택:** B안.

**결정 내용:**

같은 logical recording의 rebase는 `timeline_id`를 유지하고 revision을 증가시킨다. 과거 결과가 사용한 revision은 변경하지 않는다.

**선택 이유:**

- Anchor 변경이 영상 pixel 자체를 바꾸는 것은 아니므로 Search 전체를 재실행할 필요가 없다.
- Search는 기존 Candidate가 사용한 revision을 provenance로 추적할 필요가 있다고 확인했다.
- Evidence도 최종 TimeResolution이 어떤 revision을 사용했는지 추적해야 한다고 확인했다.

---

## 결정 4. `AssetSpan`은 단일 조각, `SpanResolution`이 전체 결과를 소유

**최종 선택:** C안.

**결정 내용:**

```
resolve_span()
→ SpanResolution
   ├─ status
   ├─ requested_range
   ├─ AssetSpan[]
   └─ missing_ranges[]
```

`AssetSpan`은 실제 사용 가능한 Source/MediaStream의 물리 조각 하나를 계속 의미한다.

**선택 이유:**

- 배열만으로는 빈 결과가 gap인지 invalid range인지 failure인지 알 수 없다.
- 일부 Source만 실패한 경우 사용 가능한 Span은 유지해야 한다.
- Evidence는 사건 범위 전체가 실제 근거에 포함됐는지 확인해야 한다.
- Search와 Evidence 모두 resolution-level wrapper를 요청했다.

---

## 결정 5. AssetSpan은 MediaStream을 반드시 특정하고 두 좌표계를 보존

**최종 선택:** SourceAsset + MediaStream + `timeline_range` + `source_range`.

**결정 내용:**

각 AssetSpan은 실제 `source_asset_ref`와 `media_stream_ref`를 포함한다. 또한 논리 Timeline상의 범위와 실제 Source/Stream 내부 offset을 모두 갖는다.

**선택 이유:**

- 하나의 SourceAsset에 front/rear 등 여러 MediaStream이 존재할 수 있다.
- Source만으로는 실제 분석한 pixel을 재현할 수 없다.
- Search와 Evidence 모두 stream identity가 필요하다고 확인했다.
- Search는 logical 결과를 전체 Timeline으로 다시 mapping하기 위해 두 좌표 모두 필요하다고 확인했다.

---

## 결정 6. 파일 경계 알고리즘은 숨기되 결과 mapping은 recording이 보장

**최종 선택:** Draft A안 + Consumer 보장사항 추가.

**결정 내용:**

overlap detection, similarity threshold, ffmpeg 처리 방법은 Contract에 노출하지 않는다. 대신 반환된 `AssetSpan.timeline_range`는 recording의 gap/overlap/file-boundary 해석이 이미 반영된 logical mapping이어야 한다.

**선택 이유:**

- Search는 overlap 알고리즘을 알 필요가 없다고 확인했다.
- 대신 동일 logical 구간이 중복되거나 순서가 역전된 결과를 Consumer에 넘기면 안 된다고 요구했다.

---

## 결정 7. Storage와 Provider 입력은 AssetSpan에서 분리

**최종 선택:** opaque Source/Stream reference만 AssetSpan에 제공.

**결정 내용:**

AssetSpan에는 local path, Object Storage URL, Gemini File ID 등을 넣지 않는다. 실제 VLM에 사용할 수 있는 입력은 `recording.prepare_analysis_source()` → `AnalysisSource`를 통해 제공한다.

**선택 이유:**

- upload/storage 전략이 바뀌어도 AssetSpan 의미를 유지해야 한다.
- Search는 storage 구현에 결합할 필요가 없다는 데 동의했다.
- 다만 실제 Gemini 호출 가능한 입력이 반드시 필요하므로 이를 후속 `AnalysisSource`가 보장하도록 요구했다.

---

## 결정 8. TimeSourceCandidate는 Source 위치와 절대시각의 Mapping

**최종 선택:** B안.

**결정 내용:**

```
source_asset_ref + source_offset_sec
↔
absolute datetime
```

를 하나의 Candidate가 표현한다.

또 `source_kind + source_detail`로 정책 수준의 분류와 구체 provenance를 분리하며 Producer-local parsing 결과를 함께 보존할 수 있다.

**선택 이유:**

- 단순 datetime만으로는 어떤 Source 위치의 시간인지 알 수 없다.
- Evidence에서 사건 offset 계산 provenance를 재현해야 한다.
- Search와 Evidence 모두 이 구조를 승인했다.
- Producer-local parsing 결과도 Consumer 양쪽에서 유용하다고 승인했다.

---

## 결정 9. Candidate 부재는 `TimeSourceCheck`, numeric confidence는 제거

**최종 선택:** Candidate 미생성은 C안, confidence는 B안.

**결정 내용:**

Candidate는 실제 시간값이 관찰되었을 때만 생성한다. 값이 없는 이유는 별도 `TimeSourceCheck`의 `NOT_FOUND / UNSUPPORTED / PARSE_ERROR` 등으로 표현한다.

Numeric confidence 필드는 Final에서 제거한다.

**선택 이유:**

- Evidence는 “정상 조사했지만 정보 없음”과 “parser 실패”를 구분해야 한다고 요청했다.
- 동시에 `value=null` Candidate가 Candidate의 의미를 흐리는 것은 원하지 않았다.
- Filename/metadata 후보 사이에 공통적으로 비교 가능한 confidence를 정의할 객관적 근거가 없고 실제 Consumer 사용처도 없었다.
- Evidence는 optional confidence도 현재 Contract에서는 제거할 것을 요청했다.

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| Evidence: `anchor`는 확정시각처럼 보임 | 반영 | `anchor` → `working_anchor` | 계산용 기준과 최종 Timestamp 구분 |
| Evidence: Recording 후보만의 `max_delta_sec` 불필요 | 반영 | `candidate_comparison`, delta 제거 | 전체 Timestamp 근거 비교는 Evidence 책임 |
| Search: Absolute anchor 없이도 relative Search 가능 | 반영 | `USABLE_RELATIVE_ONLY` 허용 | Timestamp 실패가 Search 실패가 되지 않도록 함 |
| Search/Evidence: Timeline revision 추적 필요 | 반영 | 동일 `timeline_id` + `revision` | 재현성과 부분 재실행 보존 |
| Search/Evidence: `AssetSpan[]`만으로 partial 표현 부족 | 반영 | `SpanResolution` 추가 | completeness + missing range 보존 |
| Search/Evidence: 실제 MediaStream identity 필요 | 반영 | `media_stream_ref` 필수 | pixel provenance 재현 |
| Search: 두 시간 좌표 모두 필요 | 반영 | `timeline_range + source_range` 유지 | logical↔physical mapping 보존 |
| Search: overlap 알고리즘은 몰라도 되나 결과는 보정 완료여야 함 | 반영 | boundary interpretation invariant 강화 | Consumer 중복 correction 방지 |
| Search: AssetSpan에 path는 필요 없음, 실제 VLM 입력은 필요 | 반영 | path 제외, `AnalysisSource`에서 제공 | storage coupling 방지 |
| Evidence: Candidate 부재 이유 구분 필요 | 반영 | `TimeSourceCheck` 도입 | UNKNOWN/실패 구분 |
| Evidence: numeric confidence 불필요 | 반영 | confidence 제거 | 의미 없는 숫자 오용 방지 |
| Evidence: conflict/delta는 전체 근거 기준으로 계산 | 반영 | Candidate/Timeline conflict 제거 | Evidence ownership 유지 |
| Search: raw `TimeSourceCandidate` 직접 소비 불필요 | 반영 | Search를 Direct Consumer에서 제거 | Timestamp 내부 정책과 Search 결합 방지 |

---

# 6. 최종 Contract 핵심 요약

최종 통합 Contract의 구조적 특징은 다음과 같다.

- `RecordingTimeline`은 **revisioned logical timeline**이다.
- absolute 시간이 없어도 **relative timeline은 정상적으로 사용 가능**하다.
- absolute 기준은 `working_anchor`이며 최종 Timestamp가 아니다.
- 공식적인 파일 기반 시간 후보는 단일값으로 축소하지 않고 `TimeSourceCandidate`로 보존한다.
- Timestamp 후보 비교·conflict·최종 source 선택은 `evidence`가 수행한다.
- `AssetSpan`은 실제 **SourceAsset + MediaStream 하나의 구간 mapping**이다.
- `resolve_span()`의 전체 결과는 `SpanResolution`이 표현한다.
- 부분 성공은 `PARTIAL + missing_ranges`로 보존한다.
- AssetSpan은 실제 파일 path가 아니라 opaque reference를 사용한다.
- 실제 provider 입력은 후속 `AnalysisSource`가 책임진다.
- `TimeSourceCandidate`는 **Source 위치 ↔ absolute time** 관찰이다.
- Candidate가 없을 때 `null Candidate`를 만들지 않고 `TimeSourceCheck`로 원인을 표현한다.
- Numeric confidence를 사용하지 않는다.
- 발행된 Timeline revision / AssetSpan / TimeSourceCandidate는 provenance를 위해 의미가 조용히 변경되지 않는다.

전체 필드 정의는 **Final Data Contract — RecordingTimeline + AssetSpan + TimeSourceCandidate**를 따른다.

---

# 7. Invariants / 보장사항

## RecordingTimeline

1. 모든 Timeline은 `timeline_id`와 `revision`을 가진다.
2. 동일 logical recording의 rebase는 동일 `timeline_id`에서 revision을 증가시킨다.
3. 과거 revision의 의미를 새 revision으로 덮어쓰지 않는다.
4. `working_anchor`는 최종 `occurred_at`을 의미하지 않는다.
5. absolute working anchor가 없어도 relative timeline이 유효하면 Timeline은 usable할 수 있다.
6. `SourceAsset`과 `MediaStream`을 같은 identity로 취급하지 않는다.
7. RecordingTimeline은 Candidate 간 conflict/delta를 소유하지 않는다.

## AssetSpan / SpanResolution

1. `timeline_range.start < timeline_range.end`.
2. `source_range.start < source_range.end`.
3. `media_stream_ref`는 해당 `source_asset_ref`의 MediaStream이어야 한다.
4. 하나의 logical range가 복수 AssetSpan으로 변환될 수 있다.
5. Consumer는 파일 경계 및 overlap을 자체 재계산하지 않는다.
6. `COMPLETE`이면 missing range가 없어야 한다.
7. `PARTIAL`이면 usable span과 missing range가 모두 존재해야 한다.
8. `FAILED`이면 usable span을 제공하지 않는다.
9. 일부 Source 실패만으로 정상적으로 해석된 Span을 버리지 않는다.
10. 이미 발행된 AssetSpan mapping은 Timeline rebase 때문에 조용히 변경되지 않는다.

## TimeSourceCandidate / TimeSourceCheck

1. Candidate는 실제 absolute time value가 있을 때만 존재한다.
2. Candidate는 해당 값이 어느 Source 위치에 대응하는지 추적할 수 있어야 한다.
3. Candidate source는 우선순위를 의미하지 않는다.
4. Candidate에 numeric confidence를 두지 않는다.
5. Candidate에 `AGREED / VERIFIED / CONFLICT`를 두지 않는다.
6. `VIDEO_OVERLAY_OCR`은 recording의 TimeSourceCandidate가 아니다.
7. Candidate 부재를 `value=null` Candidate로 표현하지 않는다.
8. `NOT_FOUND`와 `PARSE_ERROR`는 같은 의미로 사용하지 않는다.
9. 후보 비교, delta, conflict, 최종 Timestamp source 선택은 `evidence` 책임이다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

- `recording / search / evidence`의 Timestamp 책임 경계가 명확해졌다.
- Search는 filename/metadata 규칙이나 실제 파일 경계를 알 필요가 없다.
- absolute Timestamp를 확보하지 못해도 사건 탐색을 계속할 수 있다.
- SourceAsset과 MediaStream을 분리해 실제 분석 pixel provenance를 재현할 수 있다.
- 파일 경계에 걸린 사건도 하나의 logical range로 다룰 수 있다.
- Source 일부 실패 시 전체 결과를 버리지 않고 partial success를 표현할 수 있다.
- Evidence가 사건 범위의 누락 여부를 확인할 수 있다.
- Timeline rebase 이후에도 과거 Search/Evidence 결과의 기준 revision을 재현할 수 있다.
- Timestamp 후보와 최종 Timestamp가 분리되어 Producer가 잘못된 값을 확정할 위험을 줄였다.
- storage/provider 변경이 AssetSpan 계약에 직접 영향을 주지 않는다.

## 감수하는 비용 / 단점

- 단순 `AssetSpan[]`보다 `SpanResolution + missing_ranges` 구조가 복잡하다.
- Consumer는 COMPLETE/PARTIAL/FAILED 분기를 처리해야 한다.
- Timeline revision을 downstream provenance에 보존해야 한다.
- `timeline_range`와 `source_range` 두 좌표계의 정합성을 recording이 보장해야 한다.
- AssetSpan에 직접 URI가 없기 때문에 Search는 `prepare_analysis_source()` 단계를 거쳐야 한다.
- Timestamp 수집 시 Candidate뿐 아니라 `TimeSourceCheck` 상태도 관리해야 한다.
- Candidate conflict 계산을 Evidence에서 수행하므로 Evidence 구현 책임이 증가한다.
- MediaStream identity가 필수이므로 recording의 probe/stream identification 구현 책임이 증가한다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| Recording이 authoritative Timestamp anchor 확정 | Evidence의 최종 Timestamp ownership 침범 |
| Absolute anchor 없으면 Timeline 실패 | Search는 relative timeline만으로 실행 가능하며 정상 Source를 불필요하게 막음 |
| Candidate 하나만 선택하여 전달 | 후보 충돌/provenance 손실 및 Producer의 우선순위 판정 발생 |
| RecordingTimeline에 `max_delta_sec` 저장 | Overlay/User Input까지 포함한 Evidence 전체 비교와 의미가 달라질 수 있음 |
| Stream별 RecordingTimeline 별도 생성 | 동일 recording을 여러 timeline으로 관리하는 복잡도가 증가 |
| `resolve_span() -> AssetSpan[]`만 사용 | PARTIAL/FAILED/missing range를 충분히 표현하지 못함 |
| Unavailable 구간을 AssetSpan element로 표현 | `AssetSpan = 실제 사용할 수 있는 물리 구간` 의미가 흐려짐 |
| AssetSpan에서 SourceAsset만 참조 | 같은 Source의 front/rear 중 실제 사용한 pixel source 재현 불가 |
| AssetSpan에 file path/URL 직접 저장 | storage/provider 전략에 Contract가 결합됨 |
| `value=null TimeSourceCandidate` | 실제 시간값 후보라는 Candidate 의미가 흐려짐 |
| TimeSourceCandidate에 optional numeric confidence 유지 | 현재 객관적인 정의와 Consumer 사용처가 없으며 오용 가능 |
| Search가 raw TimeSourceCandidate를 직접 소비 | Timestamp source 정책과 Search가 불필요하게 결합됨 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `SourceAsset` | RecordingTimeline/AssetSpan/TimeCandidate가 Source ref 사용 | Source identity 안정성 필요 |
| `MediaStream` | AssetSpan에 `media_stream_ref` 필수 | MediaStream identity와 Source 소속 관계 보장 필요 |
| `Observation<T>` | Producer-local 관찰과 Evidence 확정 분리 원칙 공유 | 의미 일관성 유지 필요 |
| `CandidateEvent` | Search 결과가 Timeline range 및 사용한 timeline revision을 추적해야 함 | Search Contract에서 provenance 보존 필요 |
| `AnalysisSource` | AssetSpan에는 URI를 넣지 않으므로 실제 VLM 사용 가능 입력 제공 | **Core 3 Contract에서 보장 필요** |
| `IncidentClip` | SpanResolution/AssetSpan의 Source/Stream provenance 기반 생성 | lineage 보존 필요 |
| `OverlayTimeReadout` | recording 파일 시간과 별도 Observation으로 유지 | 변경 없음 |
| `TimeResolution` | TimeSourceCandidate + Overlay/User observation 비교, revision provenance 추적 | Evidence Contract에서 반영 필요 |

특히 Search Consumer는 실제 Gemini/VLM 입력이 필요하므로 `AnalysisSource`에서 provider가 사용할 수 있는 입력이 보장돼야 한다고 명확히 요구했다.

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

최소한 다음 케이스가 필요하다.

- **정상 Timeline**
    - absolute working anchor 존재
    - 복수 Source/MediaStream
- **Relative-only Timeline**
    - `working_anchor=UNKNOWN`
    - Search는 계속 가능
- **Timeline rebase**
    - 동일 `timeline_id`
    - revision 1 → 2
- **파일 경계 span**
    - 하나의 requested range → 복수 AssetSpan
- **Partial SpanResolution**
    - usable span + `missing_ranges`
- **Failed SpanResolution**
    - usable span 없음 + 명확한 failure reason
- **여러 Timestamp 후보**
    - Filename + Metadata가 서로 다른 값
    - Recording에서는 conflict 판단하지 않음
- **Candidate 없음**
    - `NOT_FOUND`
    - `UNSUPPORTED`
    - `PARSE_ERROR`
- **Multi-stream Source**
    - 동일 SourceAsset에서 front/rear가 별도 MediaStream으로 식별

## 구현

### `recording`

반드시:

- Source와 MediaStream을 별도 identity로 관리
- relative Timeline을 absolute time과 분리
- rebase 시 revision 증가
- 공식 Timestamp 후보를 손실 없이 수집
- Candidate에 final Timestamp 의미를 부여하지 않음
- Source gap/overlap/file boundary를 `resolve_span()`에서 일관되게 처리
- partial resolution을 `SpanResolution`으로 반환
- AssetSpan에 실제 Stream identity 보존
- Candidate 부재와 parser 실패 구분

### `search`

반드시:

- relative Timeline을 기준으로 사건 범위를 표현
- raw TimeSourceCandidate에 직접 의존하지 않음
- 파일 경계를 자체 계산하지 않음
- PARTIAL SpanResolution을 받았을 때 분석 계속 여부를 자기 단계에서 판단
- 실제 Provider 입력은 AnalysisSource를 사용

### `evidence`

반드시:

- TimeSourceCandidate를 확정 Timestamp로 사용하지 않음
- Overlay/User observation까지 포함해 후보 비교
- delta/conflict/final source selection을 Evidence에서 수행
- resolution에 사용한 Timeline revision을 provenance로 추적
- Partial SpanResolution의 missing range를 고려

## Evaluation

이번 세 Contract의 Review에서 별도의 Eval 전용 필드를 추가하는 결정은 이루어지지 않았다.

다만 Final Contract가 이미 보존하도록 확정한 다음 정보는 재현/문제 추적 시 사용할 수 있다.

- `timeline_id + revision`
- COMPLETE / PARTIAL / FAILED
- missing range
- Source/MediaStream reference
- TimeSourceCandidate provenance
- Producer-local parse 결과

ADR에서 이를 넘는 새로운 평가 지표는 추가하지 않는다.

---

# 12. 변경 규칙

이 ADR이 Accepted된 이후 계약 의미를 변경해야 할 경우 다음 절차를 따른다.

```
문제 발견
→ Producer / Consumer 확인
→ Data Contract 변경안 작성
→ Architecture 영향 확인
→ Contract Version 증가
→ ADR Supersede 또는 변경 ADR
→ Mock Dataset 갱신
```

다음과 같은 변경은 ADR 갱신 대상으로 본다.

- `working_anchor`의 의미 변경
- Timeline revision 정책 변경
- `SourceAsset / MediaStream` ownership 변경
- AssetSpan 필수 reference 변경
- COMPLETE/PARTIAL/FAILED 의미 변경
- missing range 표현 방식 변경
- TimeSourceCandidate Source 범주 의미 변경
- Candidate 부재/실패 의미 변경
- Numeric confidence 재도입
- Timestamp conflict 판단 책임 이동
- Search를 TimeSourceCandidate Direct Consumer로 다시 추가
- immutable result의 lifecycle 변경

오탈자나 설명 문구 수정처럼 Contract 의미를 바꾸지 않는 변경은 새 ADR을 요구하지 않는다.

---

# 13. 미해결 사항

Final Contract 자체의 핵심 책임과 Consumer 합의는 완료됐지만, 다음 항목은 현재 자료에서 완전히 확정된 기록을 찾을 수 없다.

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| ADR 번호 | 제공되지 않음 | `[작성 필요]` | ADR 저장 전 |
| 결정일 | `9/4`로 확정 | PM | 완료 |
| 통합 Final Contract 단일 version | component 예시 version은 있으나 통합본 version이 명시적으로 정해지지 않음 | Contract Lead / PM | Contract 저장·배포 전 |
| `resolve_span`의 `stream_selector` 입력 schema | Final 결과의 `media_stream_ref` 필수 여부는 합의됐으나 selector 요청 형식 자체는 자료에서 최종 확정되지 않음 | recording + search | public API/Tech Spec 확정 전 |

특히 마지막 항목은 **새로운 설계를 ADR에서 결정하지 않는다.** 현재 Final Contract는 “반환 AssetSpan은 실제 MediaStream을 특정한다”까지만 확정하며, selector의 구체 입력 구조는 별도 확인 대상으로 남긴다.

---

# 14. 최종 한 줄 결정

> **우리는 `recording`이 여러 Source/MediaStream을 revisioned `RecordingTimeline`으로 구성하고, 논리 구간을 `SpanResolution + AssetSpan`으로 물리 Source 구간에 안전하게 매핑하며, 파일 기반 절대시각은 `TimeSourceCandidate`로 관찰값과 provenance만 제공하고, `search`는 이를 분석 범위에 사용하며 `evidence`는 모든 시간 근거를 모아 최종 Timestamp를 확정하도록 통합 Recording Data Contract를 확정한다.**
>