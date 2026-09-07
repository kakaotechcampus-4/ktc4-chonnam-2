# Final Data Contract — RecordingTimeline · AssetSpan · TimeSourceCandidate

**Status:** `Final — Accepted`

> **B06~B09 Owner 결정 (2026-09-07, 정철원).** B06 `SpanResolution` 완전성 규칙(§9·§10·§23) · B07 최소 자산 사실과 lookup 경계(§12) · B08 relative-only timeline 불변조건(§4·`contract-analysis-scope.md`) · B09 사용 revision을 `CandidateEvent.span.timeline_revision`에 보존(§5). 스키마·버전은 바뀌지 않았다. 근거·기각안은 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.5~§4.9.

**Accepted:** `2026-09-04` (짝 ADR의 결정일 9/4; 2026-09-06 Owner 회신에서 기존 계약 수락 재확인)

**수락 근거:** §25 「Pair Review 반영 최종 결정표」 · §26 「Final Contract 한 문장 정의」. Status의 종결 근거와 날짜는 위 Pair Review·짝 ADR을 따른다. 과거에는 PM이 `Accepted`를 채웠다(`adr/adr-consistency-2026-09.md` C1-13). 정철원 이견 시 되돌린다

**Architecture Contract:** v4 §5-1 ② (부분 — `SourceAsset`/`MediaStream` 스키마와 ③ `AnalysisSource`/`RemoteCopy`/`IncidentClip`/`DerivedAsset`은 본 계약 범위 밖. 2026-09-08부터 `contract-source-asset-media-stream.md`·`contract-analysis-source-derived.md` Draft가 소유, Consumer Review 대기)

**Contract Version:** `recording-timeline/v1` · `asset-span/v1` · `time-source-candidate/v1` · 보조 구조 `span-resolution/v1.1`(2026-09-08, `failure` 필드·`OUT_OF_TIMELINE_RANGE` 추가)

**Related ADR:** `adr/adr-recording-timeline-asset-span.md`

**Contract Lead:** 정철원

**Runtime Producer:** `recording`

> **`SpanResolution` 실패 직렬화 확정 (2026-09-08 반영 · Decider 정철원 · 확인 김준영·서어진).** ① `MissingRange.reason`에 **`OUT_OF_TIMELINE_RANGE`** 추가(§10) ② top-level **`failure: {kind, code} | null`** 키 항상 존재 — `COMPLETE`/`PARTIAL`은 `null`, `FAILED`는 필수(§9) ③ 위치를 특정할 수 없는 `FAILED`는 `missing_ranges=[]`를 허용하고 `failure`가 원인을 제공한다(완전성 불변조건의 명시적 예외, §23 SpanResolution 10·11). 스키마 변경이므로 **`span-resolution/v1 → v1.1`**(PM bookkeeping, Owner 이견 시 조정). `recording-timeline/v1`·`asset-span/v1`·`time-source-candidate/v1`은 그대로다. **`CALL_REQUIRED`로 남은 것:** `MissingRange.source_ref`의 타입과 `OUT_OF_TIMELINE_RANGE`·`TIMELINE_GAP`에서의 nullable/부재 규칙(§10). `failure.kind` 값 집합을 담을 recording 소유 문서는 작성 대기다. Asset Facts 필드는 자산 계약 2건(Draft, Consumer Review 대기)이 소유한다. 근거·기각안 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.3.

## 포함 Contract

| # | Contract | Producer | 주요 Consumer | 역할 |
| --- | --- | --- | --- | --- |
| 1 | `RecordingTimeline` | `recording` | `search`, `case`, `readout`, 논리적으로 `evidence` | 여러 Source를 하나의 논리 시간축으로 표현 |
| 2 | `AssetSpan` | `recording` | `search`, `readout`, `case`, 논리적으로 `evidence` | 논리 시간구간을 실제 Source/Stream 구간으로 변환 |
| 3 | `TimeSourceCandidate` | `recording` | `evidence` | Source에서 관찰된 절대시각 후보와 provenance 보존 |

이번 Pair Review를 거치며 세 Contract의 핵심 방향은 모두 합의되었다.

- `RecordingTimeline`: `working_anchor`, 모든 시간 후보 보존, relative timeline 유지, revision 사용
- `AssetSpan`: Source + MediaStream을 특정하고 timeline/source 두 좌표를 모두 보존
- `TimeSourceCandidate`: Source 위치 ↔ 절대시각의 raw observation이며 최종 판정은 하지 않음

또한 Consumer 피드백에 따라 `SpanResolution`과 `TimeSourceCheck`를 보조 구조로 함께 사용한다.

---

# 1. 공통 책임 경계

## `recording`이 소유하는 것

`recording`은 다음을 소유한다.

- Source 파일 사실
- `SourceAsset`
- `MediaStream`
- logical Recording 시간축
- Source 배치 및 gap
- 파일 기반 Timestamp 후보
- 파일/stream 경계 해석
- timeline → 실제 Source/Stream 구간 변환
- 분석 가능한 Source를 만들기 위한 provenance

## `recording`이 소유하지 않는 것

다음은 `recording`에서 결정하지 않는다.

- 교통위반 여부
- 사건 종류
- 신고 가능 여부
- 최종 `occurred_at`
- Timestamp Source 우선순위
- Overlay Timestamp OCR
- 번호판 판독
- Evidence 최종 확정
- AI 모델 결과
- 신고 규칙

공통 흐름은 다음과 같다.

```
SourceAsset / MediaStream
        ↓
recording
        ↓
RecordingTimeline
        ↓
TimelineRange
        ↓
resolve_span()
        ↓
SpanResolution
        ├─ AssetSpan[]
        └─ MissingRange[]
```

Timestamp 쪽은 별도로:

```
SourceAsset
    ↓
recording
    ↓
TimeSourceCandidate[]

                   readout
                      ↓
              OverlayTimeReadout

TimeSourceCandidate + Overlay + User Observation
                      ↓
                    case
                      ↓
                  evidence
                      ↓
                TimeResolution
```

---

# 2. `RecordingTimeline`

## 2.1 정의

> **여러 `SourceAsset`을 하나의 논리적인 recording 시간축에 배치한 immutable revisioned contract**
> 

Search는 이 시간축을 이용해 물리 파일 개수와 경계를 알지 않고도 사건 위치를 표현한다.

Absolute Timestamp가 없어도 relative timeline은 유효할 수 있다.

Search와 Evidence 모두 absolute anchor가 없어도 relative timeline을 계속 사용할 수 있다는 점에 동의했다.

---

## 2.2 Final Schema

```
{
  "contract":"RecordingTimeline",
  "contract_version":"recording-timeline/v1",

  "timeline_id":"tl_01",
  "revision":1,

  "time_basis": {
    "mode":"ABSOLUTE_AND_RELATIVE",

    "working_anchor": {
      "value":"2026-08-23T20:51:17+09:00",
      "source_candidate_ref":"tsc_filename_01",
      "status":"OK"
    }
  },

  "time_source_candidates": ["tsc_filename_01","tsc_metadata_01"
  ],

  "source_placements": [
    {
      "source_asset_ref":"asset_001",
      "timeline_start_sec":0.0,
      "timeline_end_sec":60.03,
      "media_stream_refs": ["stream_front_001","stream_rear_001","stream_audio_001"
      ]
    }
  ],

  "gaps": [],

  "timeline_status":"USABLE",

  "produced_by":"recording"
}
```

---

## 2.3 필드 정의

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `contract_version` | string | O | Contract schema/meaning version |
| `timeline_id` | ID | O | logical RecordingTimeline identity |
| `revision` | integer | O | Timeline 변경 revision |
| `time_basis` | object | O | absolute/relative 시간축 상태 |
| `working_anchor` | object | O | 계산용 absolute 기준 관찰값 |
| `time_source_candidates` | Ref[] | O | recording이 관찰한 시간 후보 |
| `source_placements` | array | O | Source의 logical timeline 배치 |
| `gaps` | array | O | 사용할 수 없는 timeline 구간 |
| `timeline_status` | enum | O | Timeline 사용 가능 상태 |
| `produced_by` | string | O | `recording` |

---

# 3. `working_anchor`

`anchor`라는 이름은 확정 시각으로 오해될 수 있다는 Evidence 리뷰를 반영해 최종 명칭을 `working_anchor`로 한다.

```
working_anchor
= Timeline 계산을 위한 현재 기준값
≠ 최종 occurred_at
```

```
{
  "working_anchor": {
    "value":"2026-08-23T20:51:17+09:00",
    "source_candidate_ref":"tsc_filename_01",
    "status":"OK"
  }
}
```

가능하면 직접 Source 문자열을 복제하기보다 `TimeSourceCandidate`를 reference한다.

---

# 4. RecordingTimeline 상태

| 값 | 의미 |
| --- | --- |
| `USABLE` | absolute + relative timeline 사용 가능 |
| `USABLE_RELATIVE_ONLY` | absolute 기준은 없지만 relative timeline 사용 가능 |
| `PARTIAL` | 일부 Source/gap 문제가 있지만 usable range 존재 |
| `UNUSABLE` | usable timeline을 구성할 수 없음 |

중요한 규칙:

```
working_anchor.status = UNKNOWN
≠
timeline_status = UNUSABLE
```

---

# 5. Timeline Revision

같은 logical recording의 rebase는:

```
timeline_id = tl_01
revision = 1

↓ rebase

timeline_id = tl_01
revision = 2
```

로 표현한다.

새 revision이 이전 revision을 덮어쓰지 않는다.

Search와 Evidence 모두 과거 결과의 provenance를 위해 `timeline_id + revision` 추적에 동의했다.

**사용 revision의 보존 위치 (2026-09-07 확정 · B09).** Search 결과는 `CandidateEvent.span`에 `timeline_id`와 함께 **`timeline_revision`**을 보존한다(`contract-analysis-run-candidate-event.md` §4-1). 과거 Candidate는 rebase 후 최신 revision 기준으로 mutate하지 않는다.

```
Candidate provenance   = 생성 당시 timeline_id + timeline_revision
현재 화면 표시 시각     = 현재 RecordingTimeline revision으로 projection
```

둘이 다르면 `case`가 비교해 `CaseView`에 「과거 timeline revision 기준」임을 표시한다. `recording`은 revision을 올리기만 하고 stale 판정·표시는 하지 않는다. `evidence`도 같은 `{timeline_id, revision}` 형태를 `TimeResolution` provenance에 맞춘다(`contract-time-resolution.md` §16).

---

# 6. `AssetSpan`

## 6.1 정의

> **특정 RecordingTimeline revision의 logical time range를 실제 `SourceAsset + MediaStream + source-local range`로 변환한 하나의 immutable mapping**
> 

`AssetSpan`은 파일이 아니다.

```
AssetSpan
≠ SourceAsset
≠ IncidentClip
```

---

## 6.2 Final Schema

```
{
  "sequence":0,

  "timeline_range": {
    "start_sec":55.0,
    "end_sec":60.0
  },

  "source_asset_ref":"sa_0001",
  "media_stream_ref":"ms_0001",

  "source_range": {
    "start_sec":55.0,
    "end_sec":60.0
  }
}
```

---

## 6.3 필드 정의

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `sequence` | integer | O | 동일 resolution에서 논리 순서 |
| `timeline_range` | interval | O | 전체 RecordingTimeline에서 담당하는 범위 |
| `source_asset_ref` | Ref | O | 실제 SourceAsset |
| `media_stream_ref` | Ref | O | 실제 사용된 MediaStream |
| `source_range` | interval | O | 해당 Stream의 local offset |

`media_stream_ref`는 Final에서 필수다.

한 SourceAsset 안에 front/rear/audio가 동시에 존재할 수 있으므로 Source만으로는 실제 어떤 pixel을 사용했는지 재현할 수 없다는 데 Search와 Evidence가 모두 동의했다.

---

# 7. AssetSpan의 두 시간 좌표

다음 두 좌표를 반드시 함께 보존한다.

### `timeline_range`

```
RecordingTimeline 기준 60 ~ 65초
```

### `source_range`

```
Source B / Stream Front 기준 0 ~ 5초
```

즉:

```
Timeline 60~65
       ↓
Source B / Front 0~5
```

라는 변환 관계 자체가 `AssetSpan`의 핵심이다.

Search도 실제 영상 접근과 timeline 결과 mapping을 위해 두 좌표 모두 필요하다고 승인했다.

---

# 8. `SpanResolution`

Consumer Review 결과, 단순:

```
resolve_span()
→ AssetSpan[]
```

만으로는 부분 실패를 표현할 수 없다는 데 Search와 Evidence가 모두 동의했다.

따라서 Final public capability는:

```
resolve_span()
→ SpanResolution
```

로 한다.

---

## 8.1 Schema

```
{
  "contract":"SpanResolution",
  "contract_version":"span-resolution/v1.1",

  "timeline_ref": {
    "timeline_id":"tl_01",
    "revision":1
  },

  "requested_range": {
    "start_sec":50.0,
    "end_sec":120.0
  },

  "status":"PARTIAL",

  "spans": [
    {
      "sequence":0,
      "timeline_range": {
        "start_sec":50.0,
        "end_sec":60.0
      },
      "source_asset_ref":"sa_0001",
      "media_stream_ref":"ms_0001",
      "source_range": {
        "start_sec":50.0,
        "end_sec":60.0
      }
    }
  ],

  "missing_ranges": [
    {
      "timeline_range": {
        "start_sec":60.0,
        "end_sec":120.0
      },
      "reason":"SOURCE_UNAVAILABLE",
      "source_ref":"sa_0002"
    }
  ],

  "failure": null
}
```

| 최상위 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `timeline_ref` | `{timeline_id, revision}` | O | 해석 기준 Timeline revision |
| `requested_range` | interval(초) | O | 호출자가 요청한 timeline 범위 |
| `status` | `COMPLETE \| PARTIAL \| FAILED` | O | §9 |
| `spans[]` | `AssetSpan[]` | O(빈 배열 허용) | usable 구간 |
| `missing_ranges[]` | `MissingRange[]` | O(빈 배열 허용) | 해소하지 못한 구간과 이유(§10) |
| `failure` | `{kind: string, code: string} \| null` | **O(키 항상 존재)** | (v1.1) `SpanResolution` 전체가 왜 `FAILED`인가. `status=FAILED`이면 non-null이고 `kind`·`code` 둘 다 필수. `COMPLETE`/`PARTIAL`이면 `null`. `kind`는 recording이 소유하는 상위 실패 분류, `code`는 stable machine-readable 코드. `ReadoutRun.failure`와 **구조만** 같다 — recording과 readout이 taxonomy나 코드 값을 공유한다는 뜻이 아니며, Consumer는 서로 다른 모듈의 `kind`/`code`를 공통 enum처럼 직접 비교하지 않는다. 값 집합은 recording 소유 문서 한 곳에서 관리하고 evidence/search 계약에 복제하지 않는다(문서 작성 대기) |

> **예시 수정 (2026-09-07).** 이전 예시는 `requested_range`가 `[50,130)`인데 `spans`·`missing_ranges`가 `[50,120)`까지만 설명해 10초가 비어 있었다. Owner(정철원)가 「별도 의미가 없는 예시 오류」로 확인했다. 새 reason 값을 만들지 않는 최소 수정으로 요청 범위를 `[50,120)`으로 맞췄다. 완전성 규칙은 §23.

| 값 | 의미 |
| --- | --- |
| `COMPLETE` | 요청 범위 전체 resolve 성공 |
| `PARTIAL` | 일부 범위만 resolve 성공 |
| `FAILED` | usable span을 만들 수 없음 |

### COMPLETE

```
spans != []
missing_ranges = []
failure = null
```

### PARTIAL

```
spans != []
missing_ranges != []
failure = null          ← 원인은 각 missing_ranges[].reason이 설명한다
```

usable span이 존재하므로 전체 실패를 뜻하는 top-level `failure`를 두지 않는다.

### FAILED

```
spans = []
failure != null         ← 필수. spans=[]만 보고 Consumer가 원인을 추측하게 하지 않는다
```

`FAILED`에서 `missing_ranges`와 `failure`의 책임은 다르다 — `missing_ranges` = 요청 범위 중 **어디를** 해소하지 못했는가, `failure` = `SpanResolution` 전체가 **왜** `FAILED`인가.

**위치를 특정할 수 있는 전체 실패** — `missing_ranges`가 `requested_range` 전체를 설명하면서 `failure`도 제공한다.

```
{
  "contract":"SpanResolution",
  "contract_version":"span-resolution/v1.1",
  "timeline_ref": { "timeline_id":"tl_01", "revision":1 },
  "requested_range": { "start_sec":200.0, "end_sec":260.0 },
  "status":"FAILED",
  "spans": [],
  "missing_ranges": [
    { "timeline_range": { "start_sec":200.0, "end_sec":260.0 }, "reason":"SOURCE_UNAVAILABLE", "source_ref":"sa_0007" }
  ],
  "failure": { "kind":"EXAMPLE_KIND", "code":"EXAMPLE_CODE" }
}
```

**위치를 신뢰성 있게 특정할 수 없는 전체 실패**(Timeline 자체를 읽거나 해석하지 못함) — `missing_ranges=[]`를 허용하고 `failure`가 원인을 제공한다. 존재 여부를 확인할 수 없는 구간을 임의의 `MissingRange`로 만들지 않는다.

```
{
  "contract":"SpanResolution",
  "contract_version":"span-resolution/v1.1",
  "timeline_ref": { "timeline_id":"tl_01", "revision":1 },
  "requested_range": { "start_sec":200.0, "end_sec":260.0 },
  "status":"FAILED",
  "spans": [],
  "missing_ranges": [],
  "failure": { "kind":"EXAMPLE_KIND", "code":"EXAMPLE_CODE" }
}
```

> 위 두 예시의 `failure.kind`/`code` 값(`EXAMPLE_*`)은 모양을 보이기 위한 자리표시자다. 실제 값 집합은 recording 소유 문서가 정하며 이 계약은 값을 만들지 않는다.

**범위·실패의 의미 (2026-09-07 확정 · B06 · Decider 정철원, 확인 김준영·서어진)**

- `spans + missing_ranges`는 `requested_range` 전체를 **빠짐없이** 설명한다(§23 SpanResolution 6).
- timeline 범위를 **일부** 벗어나는 정상 요청은 usable 구간이 있으면 `PARTIAL`이고, 범위 밖 부분은 `missing_ranges`로 명시한다. 요청 **전체**가 resolve 불가능하면 `FAILED`.
- `start >= end`, 음수 범위, 잘못된 timeline reference 같은 **입력 오류는 `SpanResolution`을 만들지 않는다.** 입력 검증 실패로 처리한다. `FAILED`는 「정상 입력인데 usable span을 만들 수 없다」는 뜻이다.
- `FAILED`의 원인 표면화: 위치를 특정할 수 있는 전체 실패는 요청 범위 전체를 `missing_ranges`로 설명하면서 `failure`도 제공한다. 위치를 특정할 수 없는 실패는 `missing_ranges=[]` + **top-level `failure`**다(위 예시). `recording`은 실패 사실과 원인만 제공하고, 그것을 신고 규칙상 `BLOCK`/`UNKNOWN` 중 무엇으로 볼지는 `evidence`가 판단한다 — 그 판정 매핑은 evidence policy가 소유하며 이 계약에 고정하지 않는다.
- 범위 밖 구간의 `MissingRange.reason`은 **`OUT_OF_TIMELINE_RANGE`**(§10). `TIMELINE_GAP`(Timeline 내부 결손)과 합치지 않는다.
- 입력 오류(`start >= end` · 음수 · 존재하지 않거나 잘못된 형식의 timeline reference)는 `FAILED`가 아니라 입력 검증 실패다. **유효한** Timeline reference를 받았지만 저장소·인덱스·해석 결과를 사용할 수 없어 resolution을 만들 수 없는 경우가 `status=FAILED + failure`다.
- (2026-09-08 확정 · Decider 정철원 · 확인 김준영·서어진 · `adr/adr-data-contract-call-closure-2026-09-08.md` §4.3)

---

# 10. `MissingRange`

```
{
  "timeline_range": {
    "start_sec":60.0,
    "end_sec":120.0
  },
  "reason":"SOURCE_UNAVAILABLE",
  "source_ref":"sa_0002"
}
```

최소 reason:

| 값 | 의미 |
| --- | --- |
| `TIMELINE_GAP` | `RecordingTimeline` 내부에서 존재해야 할 구간에 생긴 결손 |
| `SOURCE_UNAVAILABLE` | Source 사용 불가 |
| `STREAM_UNAVAILABLE` | Stream 사용 불가 |
| `OUT_OF_TIMELINE_RANGE` | (v1.1, 2026-09-08) 정상적인 요청 구간의 일부 또는 전체가 해당 Timeline의 **경계 밖**에 있음. `TIMELINE_GAP`과 구분한다 — recording이 관찰한 사실과 Consumer의 대응 의미가 다르다 |

Evidence가 원래 사건 구간에서 일부 Source가 누락됐다는 사실을 반드시 알아야 한다고 요청했기 때문에 `missing_ranges`를 Final 구조에 포함한다.

요청이 timeline 범위를 벗어난 부분도 `missing_ranges`로 명시한다(§9) — reason은 `OUT_OF_TIMELINE_RANGE`다.

**`source_ref` — `CALL_REQUIRED`.** 위 예시의 `source_ref`는 Source가 원인인 reason(`SOURCE_UNAVAILABLE`)에서만 자연스럽다. `source_ref`의 타입(평문 opaque string인가 `ContractRef {kind, ref}`인가)과, `OUT_OF_TIMELINE_RANGE`·`TIMELINE_GAP`처럼 특정 Source가 원인이 아닌 reason에서 `null`인가 부재인가는 **Owner 결정 대기**다(`adr/adr-data-contract-call-closure-2026-09-08.md` §4.6). 확정 전에는 규칙을 만들지 않으며, fixture의 `OUT_OF_TIMELINE_RANGE` 항목은 `source_ref` 키를 넣지 않았다.

---

# 11. File Boundary / Overlap

Overlap 계산 알고리즘 자체는 Contract에 노출하지 않는다.

Consumer는:

- frame similarity 방식
- overlap 초수 계산
- ffmpeg 처리 방식

등을 알 필요가 없다.

대신 `recording`은 다음을 보장한다.

> 반환된 `AssetSpan.timeline_range`는 recording의 gap/overlap/file-boundary 해석이 이미 적용된 logical mapping이며 Consumer가 추가 보정을 수행하지 않는다.
> 

Search도 알고리즘은 숨기되 결과의 logical correctness는 Contract가 보장해야 한다는 조건으로 승인했다.

---

# 12. Storage / AnalysisSource 경계

`AssetSpan`에는 다음을 넣지 않는다.

```
local path
S3 URL
GCS URI
Gemini File ID
RemoteCopy ID
```

Search가 실제 AI 호출을 위해 필요한 입력은:

```
AssetSpan
    ↓
recording.prepare_analysis_source()
    ↓
AnalysisSource
    ↓
Gemini / VLM
```

로 얻는다.

Search도 AssetSpan에 path를 넣지 않는 대신 `AnalysisSource`가 실제 Provider 입력을 보장해야 한다고 확인했다.

## 12.1 자산 사실 lookup과 `FrameRef` 의미 (2026-09-07 확정 · B07 · Decider 정철원, 확인 김준영·유소연·신유민·서어진)

opaque ref 규칙은 유지한다. 다만 `RequirementReport`의 ASSET 판정은 ref만으로 계산할 수 없으므로 `recording`은 **최소 자산 사실(Asset Facts)을 돌려주는 lookup capability**를 소유한다. 전달 경계는 다음과 같다.

```
case / orchestration
        ↓
recording asset lookup
        ↓
Asset Facts
        ↓
case / orchestration
        ↓
evidence.check_requirements(..., assets)
```

- `case`가 lookup을 호출해 수집하고 `evidence` 입력에 주입한다. **`evidence`가 `recording`을 직접 호출하지 않는다.** web도 직접 호출하지 않는다(thumbnail 이미지도 같은 경계 — `contract-job-record-case-view.md` B절 §5).
- 이번 통합의 최소 사실은 `asset_ref` · asset kind / derived role · byte size · 판정 시점의 존재·가용 여부 · derived-from / lineage(조건부로 `duration + timeline_range`)다. 목록과 제외 항목의 원문은 `contract-requirement-report-package.md` §4.6이 소유한다. `sa_`/`da_` 접두어를 파싱해 kind를 추론하지 않고 정식 필드로 준다.
- **`FrameRef`가 보장하는 의미:** ① `fr_<opaque-id>` 형태의 opaque identity ② 동일 `MediaStream`의 동일 canonical frame은 같은 `FrameRef`(서로 다른 stream의 같은 시각 frame까지 같아야 한다는 뜻은 아님) ③ ref 문자열 내부를 파싱하지 않음 ④ `read_frame(frame_ref)`로 실제 frame 획득 가능 ⑤ `media_stream_ref`와 source-relative offset을 계약 필드로 조회 가능 ⑥ Timeline rebase가 일어나도 같은 `FrameRef`가 다른 frame을 가리키지 않음.
- `AnalysisSource`는 search가 실제 Provider 분석 입력으로 사용할 수 있는 형태를 보장한다. **정확한 `stream_selector` 직렬화는 확정하지 않았다.**

**필드 계약은 여기 없다.** Asset Facts·`FrameRef`·lookup 서명·thumbnail 이미지 전달 형태의 정확한 필드는 자산 계약 2건 `contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`(작성 대기, 정철원)가 소유한다. 이 절은 경계와 보장 의미만 고정한다.

---

# 13. `TimeSourceCandidate`

## 13.1 정의

> **`recording`이 Source 계층에서 실제로 관찰한 `Source 위치 ↔ 절대시각` 대응 관계와 provenance를 나타내는 immutable observation**
> 

예:

```
sa_0001 offset 0초
↔
2026-08-23 20:51:17+09:00
```

이다.

---

## 13.2 Final Schema

```
{
  "candidate_id":"tsc_filename_01",

  "source_kind":"FILENAME",
  "source_detail":"MDR_YYMMDD_HHMMSS.AVI",

  "value":"2026-08-23T20:51:17+09:00",

  "applies_to": {
    "source_asset_ref":"asset_205117",
    "source_offset_sec":0.0
  },

  "observation_status":"OK",

  "producer_checks": {
    "parse_valid":true
  },

  "provenance": {
    "producer":"recording",
    "observed_from":"MDR_260823_205117.AVI"
  }
}
```

---

# 14. TimeSourceCandidate 필드

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `candidate_id` | ID | O | Candidate identity |
| `source_kind` | enum | O | 큰 Timestamp Source 분류 |
| `source_detail` | string/controlled value | O | 실제 parser/field provenance |
| `value` | offset-aware datetime | O | 관찰된 absolute time |
| `applies_to.source_asset_ref` | Ref | O | 해당 시간이 연결된 Source |
| `applies_to.source_offset_sec` | number | O | 해당 Source의 기준 위치 |
| `observation_status` | enum | O | Producer-local 관찰 상태 |
| `producer_checks` | object | optional | parsing/format 검증 결과 |
| `provenance` | object | O | 관찰 lineage |

Search와 Evidence 모두 Candidate를 단순 datetime이 아니라 Source 위치와 absolute time의 mapping으로 정의하는 방향을 승인했다.

---

# 15. `source_kind`

Final 최소 enum:

| 값 | 의미 |
| --- | --- |
| `FILENAME` | 파일명에서 Timestamp 파싱 |
| `FILE_METADATA` | file/container metadata |
| `VENDOR_METADATA` | 제조사 metadata/sidecar |

포함하지 않는다.

```
VIDEO_OVERLAY_OCR → readout
USER_INPUT        → case/user
RESOLVED          → evidence
```

`source_kind + source_detail` 분리는 Search와 Evidence 모두 승인했다.

---

# 16. Producer-local Validation

```
{
  "observation_status":"OK",
  "producer_checks": {
    "parse_valid":true
  }
}
```

는:

> recording parser가 정상적으로 해당 값을 읽고 해석했다.
> 

라는 의미다.

다음을 의미하지 않는다.

```
이 Timestamp가 실제 촬영시각으로 검증됐다.
```

따라서:

```
parse_valid
≠ VERIFIED
≠ AGREED
```

이다.

두 Consumer 모두 Producer-local validation 보존을 승인했다.

---

# 17. Candidate가 없는 경우 — `TimeSourceCheck`

Candidate는 **실제 시간값이 있을 때만 생성한다.**

다음처럼 만들지 않는다.

```
{
  "source_kind":"FILE_METADATA",
  "value":null,
  "status":"UNKNOWN"
}
```

대신 후보가 생성되지 않은 이유는 `TimeSourceCheck`로 분리한다.

Evidence가 `metadata 없음`과 `parser 실패`를 구별해야 한다고 수정 요청한 결과다.

---

## 17.1 Schema

```
{
  "source_asset_ref":"asset_01",
  "source_kind":"FILE_METADATA",
  "source_detail":"container.creation_time",
  "status":"NOT_FOUND"
}
```

---

## 17.2 Status

| 값 | 의미 |
| --- | --- |
| `FOUND` | Candidate 생성 성공 |
| `NOT_FOUND` | 정상 조사했으나 값 없음 |
| `UNSUPPORTED` | 현재 parser가 지원하지 않음 |
| `PARSE_ERROR` | 값 또는 입력이 있었으나 파싱 실패 |

예:

```
creation_time field 없음
→ NOT_FOUND

creation_time="invalid"
→ PARSE_ERROR
```

---

# 18. Numeric Confidence

Final `TimeSourceCandidate`에는 `confidence`를 두지 않는다.

```
FILENAME = 0.8
FILE_METADATA = 0.7
```

같은 숫자에 객관적인 공통 의미가 없기 때문이다.

Evidence도 실제 정의와 Consumer 요구가 없는 optional confidence는 현재 Contract에서 제거하고 필요 시 향후 version 확장하는 것을 요청했다.

---

# 19. Candidate Conflict

`TimeSourceCandidate` 및 `RecordingTimeline`에 다음을 넣지 않는다.

```
conflict
AGREED
max_delta_sec
conflict_severity
selected_source
```

예를 들어:

```
Filename = 20:51:17
Metadata = 20:51:19
Overlay  = 20:51:18
User     = 20:51:20
```

인 경우 최종 비교는:

```
evidence / TimeResolution
```

에서 한다.

Evidence는 파일 기반 후보만의 delta를 미리 계산하면 전체 시간 근거를 비교하는 최종 resolution과 서로 다른 의미의 delta가 생길 수 있다고 지적했다.

---

# 20. Search Direct Dependency

`search`는 Final에서 `TimeSourceCandidate`의 direct Consumer가 아니다.

```
TimeSourceCandidate
        ↓
RecordingTimeline
        ↓
      Search
```

형태의 간접 관계만 갖는다.

Search가 실제 필요로 하는 것은:

- relative timeline
- timeline revision
- coverage/gap
- AnalysisSource

이며 FILENAME/FILE_METADATA 자체가 아니다.

---

# 21. 세 Contract의 Reference 관계

```
SourceAsset
  │
  ├─ MediaStream[]
  │
  └─ TimeSourceCandidate[]
          │
          ▼ ref
 RecordingTimeline.working_anchor

SourceAsset[]
      ↓
RecordingTimeline
      │
      │ TimelineRange
      ▼
SpanResolution
      │
      ├─ AssetSpan[]
      │    ├─ source_asset_ref
      │    └─ media_stream_ref
      │
      └─ missing_ranges[]
```

---

# 22. 전체 Lifecycle

```
1. Source 등록
      ↓
2. Source probe
      ├─ MediaStream 식별
      ├─ TimeSourceCandidate 생성
      └─ TimeSourceCheck 생성
      ↓
3. RecordingTimeline 구성
      ├─ source placement
      ├─ gap
      ├─ working_anchor
      └─ revision
      ↓
4. Search
      └─ logical TimelineRange 생성
      ↓
5. recording.resolve_span()
      ↓
6. SpanResolution
      ├─ AssetSpan[]
      └─ MissingRange[]
      ↓
7. AnalysisSource / IncidentClip / FrameRef
      ↓
8. readout
      └─ Overlay Time / Plate Observation
      ↓
9. case
      ↓
10. evidence
      └─ TimeResolution / EvidenceRecord
```

---

# 23. 공통 Invariants

## RecordingTimeline

1. `timeline_id`는 항상 존재한다.
2. `revision >= 1`.
3. 동일 logical recording rebase 시 ID는 유지하고 revision만 증가한다.
4. 이전 revision을 새 revision으로 덮어쓰지 않는다.
5. absolute anchor가 없어도 relative timeline이 유효하면 usable하다.
6. `working_anchor`는 final `occurred_at`이 아니다.
7. SourceAsset과 MediaStream을 같은 identity로 가정하지 않는다.
8. Candidate 간 conflict/delta를 저장하지 않는다.

## AssetSpan

1. `timeline_range.start_sec < timeline_range.end_sec`.
2. `source_range.start_sec < source_range.end_sec`.
3. `media_stream_ref`는 해당 SourceAsset 소속이어야 한다.
4. 하나의 logical range는 여러 AssetSpan으로 분해될 수 있다.
5. AssetSpan은 immutable mapping이다.
6. 기존 AssetSpan은 Timeline rebase 때문에 변경되지 않는다.
7. storage path/URL을 포함하지 않는다.
8. Consumer는 파일 경계나 overlap을 다시 계산하지 않는다.

## SpanResolution

1. 모든 Span/MissingRange는 `requested_range` 안에 있어야 한다.
2. `COMPLETE`이면 `missing_ranges=[]`.
3. `PARTIAL`이면 usable span과 missing range가 모두 존재한다.
4. `FAILED`이면 usable span이 존재하지 않는다.
5. 일부 Source 실패만으로 정상 Span을 제거하지 않는다.
6. (2026-09-07 · B06) `spans[].timeline_range`와 `missing_ranges[].timeline_range`의 합집합은 `requested_range`와 정확히 같다 — 설명되지 않는 구간이 없다. **예외(2026-09-08):** 11번의 위치 특정 불가 `FAILED`에는 적용하지 않는다.
7. (2026-09-07 · B06) 같은 `media_stream_ref`를 가진 `spans`끼리 `timeline_range`가 겹치지 않는다. 서로 다른 `media_stream_ref`가 같은 시간대를 가리키는 것은 허용한다.
8. (2026-09-07 · B06) 입력 오류(`start >= end` · 음수 · 잘못된 timeline reference)는 `SpanResolution`으로 표현하지 않는다. 입력 검증 실패다.
9. (2026-09-07 · B06 → 2026-09-08 모양 확정) `FAILED`는 원인을 machine-readable하게 표면화한다 — top-level `failure: {kind, code}`가 **필수**이고, 위치를 특정할 수 있으면 요청 범위 전체를 `missing_ranges`로도 설명한다.
10. (2026-09-08 · v1.1) `failure` 키는 항상 존재한다. `status ∈ {COMPLETE, PARTIAL}`이면 `failure = null`, `status = FAILED`이면 `failure != null`이며 `kind`·`code`가 비어 있지 않은 문자열이다.
11. (2026-09-08 · v1.1) 위치를 신뢰성 있게 특정할 수 없는 `FAILED`는 `spans = []` · `missing_ranges = []` · `failure != null`이다. 확인할 수 없는 구간을 임의의 `MissingRange`로 만들지 않는다.
12. (2026-09-08 · v1.1) `missing_ranges[].reason ∈ {TIMELINE_GAP, SOURCE_UNAVAILABLE, STREAM_UNAVAILABLE, OUT_OF_TIMELINE_RANGE}`. 요청이 Timeline 경계를 벗어난 구간은 `OUT_OF_TIMELINE_RANGE`다.

## TimeSourceCandidate

1. Candidate에는 반드시 실제 시간값이 존재한다.
2. Source 위치와 absolute time의 대응 관계를 추적 가능해야 한다.
3. Candidate는 final Timestamp가 아니다.
4. Source kind는 priority가 아니다.
5. numeric confidence를 갖지 않는다.
6. `AGREED / VERIFIED / CONFLICT`를 갖지 않는다.
7. Candidate는 immutable하다.
8. Overlay OCR을 recording Candidate로 만들지 않는다.
9. User Input을 recording Candidate로 만들지 않는다.

## TimeSourceCheck

1. `NOT_FOUND != PARSE_ERROR`.
2. `UNSUPPORTED`는 Source 정보 자체가 존재하지 않는다는 뜻이 아니다.
3. Candidate 부재를 `value=null Candidate`로 표현하지 않는다.

---

# 24. 통합 정상 예시

```
{
  "timeline": {
    "contract":"RecordingTimeline",
    "contract_version":"recording-timeline/v1",

    "timeline_id":"tl_case01",
    "revision":1,

    "time_basis": {
      "mode":"ABSOLUTE_AND_RELATIVE",
      "working_anchor": {
        "value":"2026-08-23T20:51:17+09:00",
        "source_candidate_ref":"tsc_filename_01",
        "status":"OK"
      }
    },

    "time_source_candidates": ["tsc_filename_01"
    ],

    "source_placements": [
      {
        "source_asset_ref":"sa_0001",
        "timeline_start_sec":0.0,
        "timeline_end_sec":60.0,
        "media_stream_refs": ["ms_0001","ms_0002"
        ]
      },
      {
        "source_asset_ref":"sa_0002",
        "timeline_start_sec":60.0,
        "timeline_end_sec":120.0,
        "media_stream_refs": ["ms_0003","ms_0004"
        ]
      }
    ],

    "gaps": [],
    "timeline_status":"USABLE"
  },

  "time_source_candidates": [
    {
      "candidate_id":"tsc_filename_01",
      "source_kind":"FILENAME",
      "source_detail":"MDR_YYMMDD_HHMMSS.AVI",
      "value":"2026-08-23T20:51:17+09:00",

      "applies_to": {
        "source_asset_ref":"sa_0001",
        "source_offset_sec":0.0
      },

      "observation_status":"OK",

      "producer_checks": {
        "parse_valid":true
      },

      "provenance": {
        "producer":"recording",
        "observed_from":"MDR_260823_205117.AVI"
      }
    }
  ],

  "time_source_checks": [
    {
      "source_asset_ref":"sa_0001",
      "source_kind":"FILE_METADATA",
      "source_detail":"container.creation_time",
      "status":"NOT_FOUND"
    }
  ],

  "span_resolution": {
    "contract":"SpanResolution",
    "contract_version":"span-resolution/v1.1",

    "timeline_ref": {
      "timeline_id":"tl_case01",
      "revision":1
    },

    "requested_range": {
      "start_sec":55.0,
      "end_sec":65.0
    },

    "status":"COMPLETE",

    "spans": [
      {
        "sequence":0,
        "timeline_range": {
          "start_sec":55.0,
          "end_sec":60.0
        },
        "source_asset_ref":"sa_0001",
        "media_stream_ref":"ms_0001",
        "source_range": {
          "start_sec":55.0,
          "end_sec":60.0
        }
      },
      {
        "sequence":1,
        "timeline_range": {
          "start_sec":60.0,
          "end_sec":65.0
        },
        "source_asset_ref":"sa_0002",
        "media_stream_ref":"ms_0003",
        "source_range": {
          "start_sec":0.0,
          "end_sec":5.0
        }
      }
    ],

    "missing_ranges": [],

    "failure": null
  }
}
```

중요하게도 이 JSON은 **하나의 API 응답으로 반드시 이렇게 내려야 한다는 뜻은 아니야.**

각 Contract의 관계를 한 번에 보여주기 위한 **통합 예시**야. 실제 API에서는 각각 별도로 생성·저장·reference할 수 있어.

---

# 25. Pair Review 반영 최종 결정표

| 항목 | Final 결정 |
| --- | --- |
| `anchor` 명칭 | `working_anchor` |
| absolute anchor 없음 | relative timeline 계속 사용 |
| Timeline rebase | 동일 `timeline_id` + `revision++` |
| 시간 후보 | 지원되는 후보 모두 보존 |
| Candidate delta | Recording에서 계산하지 않음 |
| Candidate conflict | Evidence에서 판단 |
| `SourceAsset = MediaStream` | 금지 |
| AssetSpan Stream ref | 필수 |
| AssetSpan 좌표 | timeline + source 둘 다 |
| `resolve_span()` 반환 | `SpanResolution` |
| Partial 실패 | `PARTIAL + missing_ranges` |
| overlap 알고리즘 | recording 내부 |
| overlap 보정 결과 | AssetSpan logical mapping에서 보장 |
| path/URL | AssetSpan에서 제외 |
| 실제 AI 입력 | `AnalysisSource`에서 제공 |
| AssetSpan lifecycle | immutable |
| TimeSourceCandidate | 실제 값이 있을 때만 생성 |
| Candidate 부재 이유 | `TimeSourceCheck` |
| numeric confidence | 제거 |
| Search → TimeSourceCandidate | direct dependency 제거 |

---

# 26. Final Contract 한 문장 정의

세 Contract를 합쳐서 정의하면:

> **Recording Core Time & Span Contract는 `recording`이 여러 블랙박스 Source/MediaStream을 하나의 revisioned 논리 시간축으로 구성하고, Source에서 관찰한 절대시각 후보를 provenance와 함께 보존하며, 논리 시간구간을 실제 Source/MediaStream 구간으로 안전하게 변환해 downstream에 제공하기 위한 계약이다.**
> 

더 짧게 구조만 보면:

```
TimeSourceCandidate
        ↓
RecordingTimeline
        ↓
  TimelineRange
        ↓
   resolve_span
        ↓
  SpanResolution
        ↓
    AssetSpan
```
