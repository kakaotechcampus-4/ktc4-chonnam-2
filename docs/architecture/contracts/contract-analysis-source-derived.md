# Final Data Contract — AnalysisSource + RemoteCopy + IncidentClip + DerivedAsset v1

**Status:** `Final — Accepted`

> **Consumer Review 종결 (2026-09-08).** Draft v0.2에 대해 `search`·`readout`·`case`·`evidence` 4 Consumer의 검토가 끝났고, 승인 전제로 제시된 필수 변경을 Owner(정철원)가 모두 수용해 이 개정본에 반영했다. 함께 ① 자산 ref `kind` 표기(소문자 snake_case) ② `AssetSpan` identity를 추가하지 않고 사건 구간 canonical ref를 `incident_clip`으로 단일화하는 결정이 확정됐다. 반영 내역·미반영 요청·조건 충족 근거는 짝 ADR `adr/adr-analysis-source-derived.md` §7, 결정 원장은 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.9·§4.10.

**Accepted:** `2026-09-08` (Consumer Review 4건 종결 + `kind` 표기·`AssetSpan` identity 결정 반영. Owner 정철원. 이견 시 되돌린다)

**Architecture Contract:** v4 §5-1 ③ — `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset`

**Contract:** `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset`

**Contract Version:** `analysis-source-derived/v1` (문서 헤더와 모든 JSON payload가 같은 문자열을 쓴다. `1.0.0` 형식과 혼용하지 않는다)

**Related ADR:** `adr/adr-analysis-source-derived.md` · `adr/adr-data-contract-call-closure-2026-09-07.md` §4.6(B07)·§4.9(W07 잔여) · `adr/adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.9·§4.10

**Contract Lead / Owner:** 정철원 (`recording`)

**Runtime Producer:** `recording`

**Consumers:** 서어진 (`search`) · 신유민 (`readout`) · 유소연 (`case`) · 김준영 (`evidence`)

**관련 Architecture:** `../module-architecture.md` Core ③

> 이 문서는 CALL-11에서 합의된 분석 입력, provenance 및 lifecycle 경계를 계약으로 옮기고 2026-09-08 Consumer Review 결과를 반영한 확정본이다. 공통 `AssetFacts`와 자산 계층 `ContractRef.kind` 값 공간은 `contract-source-asset-media-stream.md` §6·§2.1을 그대로 사용하며 여기서 재정의하지 않는다.

---

## 1. 계약 목적

`recording`이 Source/AssetSpan에서 만들어 관리하는 대상을 네 의미로 분리한다.

- `AnalysisSource`: search가 실제 분석에 사용할 수 있도록 준비된 media input
- `RemoteCopy`: 외부 provider copy/reference와 expiry를 추적하는 registry record
- `IncidentClip`: 사건 구간을 분석·검토하기 위해 materialize한 Source-derived clip
- `DerivedAsset`: Report Video, Plate Image 등 서비스가 생성한 재생성 가능한 파생 자산

provider upload 전략이나 storage 구현이 바뀌어도 이 public 의미와 provenance는 유지되어야 한다.

---

## 2. 공통 원칙과 Ref

```
AnalysisSource ref : as_<opaque-id>
RemoteCopy ref     : rc_<opaque-id>
IncidentClip ref   : clip_<opaque-id>
DerivedAsset ref   : da_<opaque-id>
```

1. 모든 ref는 opaque identity다.
2. prefix는 serialization convention일 뿐 종류·role·lineage를 소유하지 않는다.
3. Source와 Derived를 구분하고 lineage를 보존한다.
4. 서비스 관리 copy/derived asset과 사용자 외부 원본의 lifecycle을 분리한다.
5. recording은 provider-compatible AnalysisSource와 RemoteCopy registry를 소유한다.
6. 실제 provider upload/delete API 호출은 `search/providers` 경계다.
7. IncidentClip은 확정 Evidence 또는 Report Video가 아니다.
8. 파생물 생성 실패가 이미 생성된 Search/Evidence 결과를 자동으로 무효화하지 않는다.

`ContractRef.kind` 값은 `contract-source-asset-media-stream.md` §2.1이 소유한다 — 이 계약이 쓰는 값은 `source_asset` · `media_stream` · `analysis_source` · `remote_copy` · `incident_clip` · `derived_asset` · `external_source` · `frame`이며 모두 **소문자 snake_case**다. Consumer는 정확한 문자열로 비교하고 대소문자 보정·별칭·prefix 추론을 하지 않는다.

### 2.1 `_refs` 필드의 두 표기 (2026-09-08 확인)

한 객체 안에 `ContractRef[]`와 평문 string 배열이 함께 있는 것은 의도된 구분이다.

| 필드 | 타입 | 이유 |
| --- | --- | --- |
| `source_refs[]` | `ContractRef[]` | 서로 다른 자산 종류(`source_asset` · `incident_clip` · `analysis_source` …)를 담을 수 있어 `kind`가 필요하다 |
| `media_stream_refs[]` | string[] | `MediaStream`만 담는 동종 필드라 `kind`가 정보를 추가하지 않는다 |

Consumer는 **필드의 계약 타입**으로 종류를 판단하며 ref prefix를 파싱하지 않는다.

---

## 3. 공통 `AssetFacts` 사용

이 계약의 AnalysisSource, IncidentClip, DerivedAsset에 대한 자산 사실은 `contract-source-asset-media-stream.md` §6의 canonical `AssetFacts`와 `lookup_asset_facts(asset_ref)`를 사용한다.

- `AssetFacts`를 이 문서에 복제 정의하지 않는다.
- `asset_kind`, `derived_role`, `availability`, `checked_at`, `lineage`, `timeline_ref`/`timeline_range`는 canonical 정의를 따른다.
- 특히 **`lineage[]`의 평탄화 규칙**(파생 자산은 원본 `source_asset`/`external_source`까지 포함)은 짝 계약 §6.3이 소유한다. evidence는 recording을 직접 호출할 수 없으므로 clip → source_asset을 스스로 따라가지 않는다.
- `case/orchestration`이 recording에서 조회해 evidence 입력에 주입한다.
- evidence와 web은 recording을 직접 호출하지 않는다.

---

## 4. `AnalysisSource`

### 4.1 의미와 Schema

`AnalysisSource`는 recording이 해석한 Source 구간에서 준비한 실제 분석 가능한 media input이다. Search는 AssetSpan의 storage path/URL을 직접 사용하지 않고 AnalysisSource capability를 통해 입력을 얻는다.

```json
{
  "contract": "AnalysisSource",
  "contract_version": "analysis-source-derived/v1",
  "analysis_source_ref": "as_01JREC000000000000000001",
  "asset_kind": "ANALYSIS_SOURCE",
  "source_refs": [
    {
      "kind": "source_asset",
      "ref": "sa_01JREC000000000000000001"
    }
  ],
  "media_stream_refs": [
    "ms_01JREC000000000000000001"
  ],
  "byte_size": 104857600,
  "availability": "AVAILABLE",
  "duration_sec": 180.0,
  "timeline_ref": {
    "timeline_id": "tl_01JREC000000000000000001",
    "revision": 3
  },
  "timeline_range": {
    "start_sec": 300.0,
    "end_sec": 480.0
  },
  "profile_ref": "prof_01JREC000000000000000001"
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `analysis_source_ref` | Y | string | opaque identity |
| `asset_kind` | Y | enum | 항상 `ANALYSIS_SOURCE` |
| `source_refs[]` | Y | `ContractRef[]` | **직접 부모** Source provenance(원본까지의 전체 lineage는 `AssetFacts.lineage`) |
| `media_stream_refs[]` | Y | string[] | 실제 분석 pixel/audio가 유래한 streams |
| `byte_size` | Y(키 항상 존재) | integer ≥ 0 \| null | 짝 계약 §3.4 |
| `availability` | Y | enum | 짝 계약 §3.5 |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | 준비된 **전체** media 길이(§4.5) |
| `timeline_ref` | Y(키 항상 존재) | `{timeline_id, revision}` \| null | `timeline_range` 좌표의 기준(§4.3) |
| `timeline_range` | Y(키 항상 존재) | `{start_sec, end_sec}` \| null | 분석 입력이 포괄하는 RecordingTimeline 범위, 초(§4.3) |
| `profile_ref` | Y | string | 준비 profile의 opaque ref. **non-null**(§4.4) |

### 4.2 보장 및 capability

```
prepare_analysis_source(span, profile) -> AnalysisSource | failure
open_analysis_source(analysis_source_ref) -> { stream, content_type, byte_size } | failure
```

1. `open_analysis_source`는 public 경계에서 **로컬 파일 경로를 노출하지 않고** 읽을 수 있는 binary stream을 반환한다. provider 업로드에 필요한 `content_type`과 실제 `byte_size`를 함께 제공한다.
2. 같은 ref를 다시 열면 **처음부터 읽을 수 있는 새 stream**을 받는다(재시도 가능).
3. local path, S3/GCS URI, provider object ID, 인증 토큰은 public 계약에 노출하지 않는다. provider가 파일 경로를 요구하면 `search/providers` adapter가 내부 임시 파일로 변환하고 그 경로는 계약에 나타나지 않는다.
4. 반환 media의 Source/MediaStream lineage를 추적할 수 있어야 한다.
5. 원본·부분·proxy 중 어떤 전략을 쓸지는 profile이 정하며 「항상 proxy」를 강제하지 않는다.
6. `open_analysis_source` 최소 machine-readable failure `code`:

```
NOT_FOUND
UNAVAILABLE
UNSUPPORTED_MEDIA
TEMPORARY_FAILURE
```

failure의 공통 모양(`{kind, code}`)은 짝 계약 §6.6과 같다 — 구조만 같고 값 집합을 공유하지 않는다.

### 4.3 `timeline_ref` · `timeline_range` (2026-09-08 확정)

```
timeline_range != null  ⇔  timeline_ref != null
timeline_range == null  ⇔  timeline_ref == null
```

- `timeline_range`만으로는 부족하다 — 같은 `timeline_id`라도 revision이 바뀌면 같은 offset이 다른 영상을 가리킬 수 있다. 그래서 **revision을 함께 필수로** 준다.
- Timeline에 속하지 않는 AnalysisSource는 두 필드를 모두 `null`로 보낸다.
- 단위는 **초**다. `AnalysisScope`의 relative range(ms)와 다르며 변환은 recording 경계에서 명시적으로 한다.

### 4.4 `profile_ref`와 profile 값 공간 (2026-09-08 확정 · 값은 Pending)

- `prepare_analysis_source`는 항상 profile을 입력받으므로, 반환된 `AnalysisSource.profile_ref`도 **필수 non-null**이다. search가 재사용 가능 여부를 판단할 수 있어야 한다.
- profile은 `coarse`/`fine` 같은 **실행 단계가 아니라 media 특성**을 표현한다. 조건이 같으면 coarse와 fine이 같은 `AnalysisSource`·`RemoteCopy`를 재사용할 수 있다.
- 구분해야 하는 최소 두 종류는 「저해상도·무음 분석용」과 「원본 또는 판독 가능한 고화질용」이다.
- **canonical profile 값 공간의 소유는 `recording`이다.** search·readout은 자기 별칭표를 만들지 않는다.
- `profile_ref`는 **opaque**다. Consumer는 문자열을 파싱하지 않고 동등성 비교(재사용 판단)에만 쓴다. 따라서 값 목록이 확정되기 전에도 payload를 만들고 소비할 수 있다.
- **Pending:** 정확한 profile 값 목록과 각 값이 보장하는 media 속성 — recording·search·readout 3자 합의 항목이다(§11-1). 값 목록이 없다는 것이 이 계약의 필드 모양·필수성·소유를 막지 않는다.
- `PlateReadout.input_ref.source_profile`(readout의 판독 라벨)과 `profile_ref`(자산 식별자)는 **다른 개념**이다. 연결이 필요해지면 canonical space 소유자인 recording이 대응을 정한다.

### 4.5 `duration_sec`과 사용량의 관계 (2026-09-08 확인 · 계약 변경 없음)

`AnalysisSource.duration_sec`은 **준비된 전체 media 길이**이며 실제 처리량이 아니다.

- 실제 처리 시간의 authoritative 값은 호출별 `UsageRecord.processed_duration_sec`이다(`contract-usage-record.md`).
- `AnalysisRun.usage_summary.processed_duration_ms`는 그 원장을 합산한 실행 시점 snapshot이다.
- 전체 AnalysisSource를 실제로 처리했다는 보장이 있을 때만 두 값이 같을 수 있다.

---

## 5. `RemoteCopy`

### 5.1 의미와 Schema

`RemoteCopy`는 외부 AI provider 등에 올라간 AnalysisSource의 copy/reference를 재사용하기 위한 registry record다.

```json
{
  "contract": "RemoteCopy",
  "contract_version": "analysis-source-derived/v1",
  "remote_copy_ref": "rc_01JREC000000000000000001",
  "analysis_source_ref": "as_01JREC000000000000000001",
  "provider": "example-provider",
  "provider_object_ref": "provider-object-opaque-001",
  "availability": "AVAILABLE",
  "expires_at": "2026-09-09T00:35:00+09:00"
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `remote_copy_ref` | Y | string | registry record opaque identity |
| `analysis_source_ref` | Y | string | 어떤 분석 입력의 사본인가 |
| `provider` | Y | string | provider 식별 라벨. Search 외 Consumer가 provider API 의미로 해석하지 않는다 |
| `provider_object_ref` | Y | string | provider가 발급한 opaque object reference |
| `availability` | Y | enum | 짝 계약 §3.5와 같은 값 공간 |
| `expires_at` | Y(키 항상 존재) | offset-aware datetime \| null | provider 사본의 만료 시점. 만료가 없으면 `null` |

### 5.2 Invariants

1. `remote_copy_ref`와 `provider_object_ref`는 opaque다.
2. registry 조회 키의 의미는 `(analysis_source_ref, provider)`다.
3. 같은 AnalysisSource의 서로 다른 provider copy는 별도 RemoteCopy다.
4. 동일한 유효 RemoteCopy를 coarse/fine에서 재사용할 수 있다.
5. expiry 이후에도 기존 AnalysisRun의 의미는 바뀌지 않는다.
6. expiry/availability에 따라 새 RemoteCopy를 만들 수 있다.
7. provider별 upload/delete 구현은 `search/providers` 소관이다.
8. 즉시 delete 지원 여부와 retention 기간은 Pending이다(§11).
9. provider URL, 인증 토큰, local path를 저장하지 않는다.
10. `evidence`는 `RemoteCopy`를 소비하지 않는다(2026-09-08 evidence 확인).

### 5.3 Public capability

```
find_remote_copy(analysis_source_ref, provider) -> RemoteCopy | null
register_remote_copy(analysis_source_ref, provider, remote_info) -> RemoteCopy
```

**`find_remote_copy` (2026-09-08 확정).** 조회 시점에 `availability=AVAILABLE`이고 만료 전인 RemoteCopy만 반환한다.

- 만료·`UNAVAILABLE`·미등록은 모두 정상적인 cache miss와 동일하게 **`null`**이다.
- 만료 판단은 registry Owner인 **recording**이 `expires_at`과 `availability`를 기준으로 한다. search는 provider별 TTL 정책을 해석하지 않는다.

**`register_remote_copy`의 `remote_info` 최소 필드 (2026-09-08 확정).**

```
provider_object_ref
expires_at
```

- `analysis_source_ref`와 `provider`는 별도 인자다.
- `remote_copy_ref`와 초기 `availability`는 recording이 부여한다.

recording이 registry owner라는 경계가 계약이며 구체 함수명은 구현에서 조정할 수 있다.

---

## 6. `IncidentClip`

### 6.1 의미

`IncidentClip`은 Candidate/Timeline span을 recording이 실제 Source/MediaStream 경계로 해석해 만든 분석·검토용 Source-derived 사건 구간이다.

- `IncidentClip != AssetSpan`
- `IncidentClip != Report Video`
- `IncidentClip != confirmed Evidence`

**clip 생성 이후 사건 구간의 canonical reference는 `incident_clip` ref다** (2026-09-08 확정). canonical `AssetSpan`에는 독립 identity가 없고 앞으로도 추가하지 않으므로, 존재하지 않는 `source_span_ref`나 합성 span ref를 만들지 않는다. 재현에 필요한 timeline과 span 값은 `source_provenance`에 값으로 보존한다.

### 6.2 Schema

```json
{
  "contract": "IncidentClip",
  "contract_version": "analysis-source-derived/v1",
  "incident_clip_ref": "clip_01JREC000000000000000001",
  "asset_kind": "INCIDENT_CLIP",
  "source_provenance": {
    "timeline_ref": {
      "timeline_id": "tl_01JREC000000000000000001",
      "revision": 3
    },
    "requested_range": {
      "start_sec": 300.0,
      "end_sec": 420.0
    },
    "asset_spans": [
      {
        "sequence": 0,
        "timeline_range": {
          "start_sec": 300.0,
          "end_sec": 420.0
        },
        "source_asset_ref": "sa_01JREC000000000000000001",
        "media_stream_ref": "ms_01JREC000000000000000001",
        "source_range": {
          "start_sec": 300.0,
          "end_sec": 420.0
        }
      }
    ]
  },
  "media_stream_refs": [
    "ms_01JREC000000000000000001"
  ],
  "byte_size": 73400320,
  "availability": "AVAILABLE",
  "duration_sec": 120.0,
  "timeline_ref": {
    "timeline_id": "tl_01JREC000000000000000001",
    "revision": 3
  },
  "timeline_range": {
    "start_sec": 300.0,
    "end_sec": 420.0
  }
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `incident_clip_ref` | Y | string | clip opaque identity(§6.5) |
| `asset_kind` | Y | enum | 항상 `INCIDENT_CLIP` |
| `source_provenance` | Y | object | clip 생성 근거의 authoritative 기록(§6.3) |
| `source_provenance.timeline_ref` | Y | `{timeline_id, revision}` | **non-null.** 어느 timeline 해석에서 만들어졌는가 |
| `source_provenance.requested_range` | Y | `{start_sec, end_sec}` | 요청한 timeline 범위, **초** |
| `source_provenance.asset_spans[]` | Y | canonical `AssetSpan[]` | 실제로 사용한 span 값(§6.3) |
| `media_stream_refs[]` | Y | string[] | clip pixel/audio가 유래한 streams |
| `byte_size` | Y(키 항상 존재) | integer ≥ 0 \| null | 짝 계약 §3.4 |
| `availability` | Y | enum | 짝 계약 §3.5 |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | materialized clip 길이 |
| `timeline_ref` | Y(키 항상 존재) | `{timeline_id, revision}` \| null | `timeline_range` 좌표 기준 |
| `timeline_range` | Y(키 항상 존재) | `{start_sec, end_sec}` \| null | **실제 materialize된** 범위, 초(§6.4) |

### 6.3 `source_provenance.asset_spans[]`는 canonical `AssetSpan` 형태다 (2026-09-08 확정)

`asset_spans[]`의 각 원소는 `contract-recording-timeline-asset-span.md` §6.2가 정의한 canonical `AssetSpan`과 **같은 필드·같은 중첩 구조·같은 단위**를 쓴다.

```
sequence          : integer   — 같은 resolution 안에서의 순서. 필수
timeline_range    : {start_sec, end_sec}
source_asset_ref  : string
media_stream_ref  : string
source_range      : {start_sec, end_sec}
```

- `sequence`는 필수다. 여러 파일 경계를 넘는 clip은 span 순서 없이 구간을 복원할 수 없다.
- 평탄화된 `source_start_sec` · `source_end_sec` · `timeline_start_ms` · `timeline_end_ms` 같은 표기는 **쓰지 않는다.**
- `source_provenance.requested_range`도 `{start_sec, end_sec}`다 — `SpanResolution.requested_range`와 **같은 이름·같은 단위**다. recording 공개 경계의 구간 단위는 초다.
- clip 생성 후 evidence·readout이 원본 구간을 복원하는 유일한 근거가 이 값이므로, 같은 개념을 두 모양으로 두지 않는다.

### 6.4 Invariants

1. `incident_clip_ref`는 opaque identity다. timeline·sequence·offset 등 위치값을 인코딩하지 않는다.
2. `source_provenance.asset_spans[]`는 canonical `AssetSpan` 구조를 따른다(§6.3).
3. `AssetSpan`에는 identity가 없다. 합성 `source_span_ref`를 만들지 않고, Consumer가 canonical 필드값을 문자열로 결합하거나 해시해 임의 span ref를 발급하는 것도 금지한다.
4. `source_provenance.timeline_ref.revision`으로 provenance가 어느 timeline 해석에서 생성됐는지 고정한다. rebase가 기존 clip의 provenance를 바꾸지 않는다.
5. 복수 파일 경계를 넘는 materialization 책임은 recording에 있다.
6. clip 생성 실패가 Search Candidate 또는 Evidence observation을 자동 삭제하지 않는다.
7. clip 자체에 법적 위반 여부, 신고 유형 또는 final `occurred_at`을 넣지 않는다.
8. **`timeline_range`(실제 materialize된 범위)와 `source_provenance.requested_range`(요청 범위)는 다를 수 있다** — timeline 경계에서 잘리는 경우다. Consumer는 두 필드를 비교해 잘림을 알 수 있다. 허용 폭 판정은 `evidence` policy가 소유하며 이 계약에 고정하지 않는다.

### 6.5 `incident_clip_ref` identity와 재처리 (2026-09-08 확정)

`IncidentClip`은 저장·재참조할 수 있는 독립 자원이므로 opaque `incident_clip_ref`를 소유한다.

- 같은 ref는 항상 같은 clip과 같은 `source_provenance`를 가리킨다.
- rebase나 재처리로 기존 ref의 의미를 바꾸지 않는다. 기존 clip은 mutate하지 않는다.
- 기존 clip을 재사용하면 기존 ref를 유지할 수 있다.
- 새 profile·새 bytes·새 source provenance로 다시 materialize하면 **새 ref**를 발급한다.
- 같은 사건 구간인지는 ID 문자열이 아니라 `source_provenance`의 canonical 값으로 비교한다.
- 따라서 `incident_clip_ref`를 `(timeline_id, revision, sequence)`로 만들 필요가 없다. 재처리 동일성은 immutable provenance와 case의 `input_fingerprint`가 보장한다(§6.7).

### 6.6 Public capability

```
build_incident_clip(span, options) -> IncidentClip | failure
```

- `case`는 전후 여유 시간을 계산하지 않고 **이미 결정된 사건 interval을 전달**한다. materialization option은 recording이 소유한다. 사건 범위 정책이 필요하면 `evidence`가 결정하고 case가 전달한다.
- `options`의 exact schema는 Pending이다(§11-8).
- 생성 실패 최소 machine-readable failure `code`: `INCIDENT_CLIP_BUILD_FAILED`(§9).

### 6.7 사용자 수정(`SPAN_ADJUST`)과 재발주 (2026-09-08 확정)

`CorrectionRecord.kind=SPAN_ADJUST`로 구간이 바뀌면:

- **case**는 변경된 span을 반영해 `input_fingerprint`를 바꾸고 기존 캐시를 재사용하지 않는다(`contract-job-record-case-view.md` A절 §7).
- **recording**은 provenance가 달라지면 새 `IncidentClip`을 발급한다. 기존 clip을 mutate하지 않는다.

재발주·fingerprint는 case, clip 발급·불변성은 recording이 담당한다.

### 6.8 readout 입력 경계 (2026-09-08 확정)

```
PlateReadout.input_ref.incident_clip_ref         : 필수
OverlayTimeReadout.input_ref.incident_clip_ref   : 판독 실행 시 필수
```

- readout은 `IncidentClip` 또는 그 clip에서 발급된 Source-derived `FrameRef`/crop을 근거로 사용한다. **`AssetSpan`만 직접 전달받아 판독하는 public 경로는 없다.**
- frame 획득 경계는 다음과 같다 — 이 계약은 clip이 canonical `AssetSpan` provenance를 완전하게 제공한다는 것까지만 보장하고, `resolve_frame`은 짝 계약이 소유한다.

```
IncidentClip.source_provenance.asset_spans[]
  → resolve_frame({kind:"STREAM_POSITION", media_stream_ref, source_offset_sec})  (짝 계약 §5.3)
  → FrameRef
  → read_frame(frame_ref) → frame image
```

- `PlateReadout`/`OverlayTimeReadout`의 `span_ref` 필드는 삭제됐다(`contract-plate-overlay-readout.md` v1.2). `span_ref`라는 이름으로 `IncidentClip`이나 `SpanResolution`을 가리키는 의미 재정의도 하지 않는다.
- clip 준비가 job 조립 전에 실패하면 readout job을 dispatch하지 않는다(case 경계). dispatch 후 입력이 없어졌거나 열 수 없으면 `PLATE_ABSTAINED`와 구분되는 입력 계층 실패로 낸다 — `ReadoutRun.failure`에 `kind: INPUT` · `code: INPUT_UNAVAILABLE`.

### 6.9 clip 생성 전 사건 interval 참조 (2026-09-08 확정)

`EvidenceNeeds.context_refs`의 `evidence.interval`은 clip 생성 시점을 기준으로 참조 대상이 갈린다.

```
clip 생성 전  → { kind: "candidate_event", ref: ... }   (fallback)
clip 생성 후  → { kind: "incident_clip",   ref: ... }
```

- `candidate_event` fallback은 `CandidateEvent.span`이 `timeline_id` + `timeline_revision` + ms 범위를 갖기 때문에(B09 종결) 기준 revision과 사건 범위를 복원할 수 있다.
- candidate ref는 clip이 만들어진 뒤에도 `incident_clip` ref를 대신하는 **영구 별칭이 아니다.** case는 candidate ref를 받아 필요한 `IncidentClip`을 materialize한 뒤 readout에는 `incident_clip_ref`를 전달한다.
- 규칙 원문은 `contract-evidence-record-needs.md` §8.3이 소유한다.

---

## 7. `DerivedAsset`

### 7.1 의미와 Schema

`DerivedAsset`은 대신고가 생성하는 재생성 가능한 파생 자산의 공통 의미다.

```json
{
  "contract": "DerivedAsset",
  "contract_version": "analysis-source-derived/v1",
  "derived_asset_ref": "da_01JREC000000000000000001",
  "asset_kind": "DERIVED_ASSET",
  "derived_role": "REPORT_VIDEO",
  "source_refs": [
    {
      "kind": "incident_clip",
      "ref": "clip_01JREC000000000000000001"
    }
  ],
  "byte_size": 52428800,
  "availability": "AVAILABLE",
  "duration_sec": 120.0,
  "timeline_ref": {
    "timeline_id": "tl_01JREC000000000000000001",
    "revision": 3
  },
  "timeline_range": {
    "start_sec": 300.0,
    "end_sec": 420.0
  },
  "transform_ref": null
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `derived_asset_ref` | Y | string | opaque identity |
| `asset_kind` | Y | enum | 항상 `DERIVED_ASSET` |
| `derived_role` | Y | enum | §7.3 |
| `source_refs[]` | Y | `ContractRef[]` | **직접 부모.** 원본까지의 lineage는 `AssetFacts.lineage` |
| `byte_size` | Y(키 항상 존재) | integer ≥ 0 \| null | 짝 계약 §3.4 |
| `availability` | Y | enum | 짝 계약 §3.5 |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | 영상 파생물이 아니면 `null` |
| `timeline_ref` | Y(키 항상 존재) | `{timeline_id, revision}` \| null | §4.3과 같은 쌍 규칙 |
| `timeline_range` | Y(키 항상 존재) | `{start_sec, end_sec}` \| null | §4.3과 같은 쌍 규칙 |
| `transform_ref` | Y(키 항상 존재) | string \| null | 파생 과정 provenance(§7.4) |

### 7.2 Invariants

1. `derived_asset_ref`는 opaque identity다.
2. `derived_role`은 ref prefix에서 추론하지 않는다.
3. 사용자 외부 원본 Source와 DerivedAsset을 동일 asset으로 취급하지 않는다.
4. export 시점까지의 lineage를 추적할 수 있어야 한다.
5. `transform_ref`가 있으면 파생 과정 provenance를 가리킨다.
6. Report Video 생성 실패가 이미 확정된 Evidence를 무효화하지 않는다.
7. 사후 timestamp 각인은 Report Video에만 적용된다(v4 §3-2·§7-3). 각인 필요 여부 판단은 `evidence`, 발주는 `case`, 생성은 `recording`이다.

### 7.3 `derived_role` 등재 값 (2026-09-08 확정 · 최소 2건)

evidence가 `ReportPackage.assets.report_video_ref`(필수)와 `plate_image_ref`(optional)를 채우고 FINAL_PACKAGE에서 「Report Video 존재」를 판정하려면 두 role을 식별할 수 있어야 한다.

| 값 | 의미 |
| --- | --- |
| `REPORT_VIDEO` | 신고 제출용 영상 파생물 |
| `PLATE_IMAGE` | 번호판 이미지 파생물 |

- 이 둘은 **등재 확정**이다. 그 밖의 role은 필요해질 때 추가하며 Pending으로 남는다(§11-6).
- **어느 role이 필수인지와 부재 시 outcome은 `evidence` policy가 소유한다.** 이 계약은 role 값의 존재와 의미만 정하고 판정 매핑을 고정하지 않는다.

### 7.4 `transform_ref` (2026-09-08 부분 확정)

- `transform_ref`가 non-null이면 **적용된 transform 종류를 machine-readable하게 조회할 수 있다**는 것이 계약 보장이다. evidence는 이를 근거로 「사후 각인이 실제로 Report Video에 적용됐다」를 확인한다.
- 조회할 수 없으면 evidence는 해당 check를 `UNKNOWN`으로 낸다 — 그 판정은 evidence policy 소유다.
- **Pending:** transform payload의 exact schema(§11-7).

### 7.5 export 실패

Report Video 등 파생물 export 실패의 최소 machine-readable failure `code`는 `REPORT_VIDEO_EXPORT_FAILED`다(§9). `case`는 이를 기존 `CaseView.notices[].code`에 그대로 얹으며 새 `CaseView` 필드를 만들지 않는다.

---

## 8. Lifecycle 경계

```
External Source Reference        ← 사용자 원본, 서비스가 overwrite/delete하지 않음
        │
        ├─ Managed Source Copy    ← 서비스 관리 사본
        ├─ AnalysisSource         ← 분석용 입력
        ├─ RemoteCopy             ← 외부 provider copy/ref registry
        ├─ IncidentClip           ← Source-derived 분석/검토 clip
        └─ DerivedAsset           ← Report Video / Plate Image 등
```

- `purge_case()`는 서비스 관리 사본과 파생물을 정리할 수 있다.
- 사용자 외부 원본은 서비스 삭제 대상이 아니다.
- provider delete API 호출은 `search/providers` 경계다.
- 정확한 retention 기간은 Pending이다(§11-4).

### 8.1 `DeletionReport` 최소 구조 (2026-09-08 확정)

```
purge_case(case_id) -> DeletionReport
```

```json
{
  "contract": "DeletionReport",
  "contract_version": "analysis-source-derived/v1",
  "case_id": "case_001",
  "requested_at": "2026-09-08T00:35:00+09:00",
  "completed_at": "2026-09-08T00:35:04+09:00",
  "status": "PARTIAL",
  "items": [
    {
      "asset_ref": { "kind": "incident_clip", "ref": "clip_01JREC000000000000000001" },
      "result": "DELETED",
      "failure_code": null
    },
    {
      "asset_ref": { "kind": "remote_copy", "ref": "rc_01JREC000000000000000001" },
      "result": "PENDING_EXPIRY",
      "failure_code": null
    }
  ]
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `case_id` | Y | string | 대상 case |
| `requested_at` | Y | offset-aware datetime | 삭제 요청 시점 |
| `completed_at` | Y(키 항상 존재) | offset-aware datetime \| null | 완료 시점. 진행 중이면 `null` |
| `status` | Y | enum | `COMPLETE` \| `PARTIAL` \| `FAILED` |
| `items[]` | Y | object[] | 자산별 결과 |
| `items[].asset_ref` | Y | `ContractRef` | 삭제 대상 |
| `items[].result` | Y | enum | `DELETED` \| `NOT_FOUND` \| `PENDING_EXPIRY` \| `FAILED` |
| `items[].failure_code` | Y(키 항상 존재) | string \| null | `result=FAILED`면 non-null |

- `external_source`(사용자 외부 원본)는 삭제 대상이 아니므로 `items[]`에 넣지 않는다.
- provider delete를 지원하지 않는 `RemoteCopy`는 `PENDING_EXPIRY`다 — expiry까지 남는다는 사실을 기록한다(v4 §8-4 · 보안 검수 #15·#16).
- 일부만 실패하면 `status=PARTIAL`이다.
- `case`는 이 결과를 사용자에게 보여줄 수 있다. `UsageRecord`를 purge하는지는 이 계약 범위 밖이다(`contract-usage-record.md` §10).

---

## 9. 실패 경계

- AnalysisSource 준비 실패: 해당 분석 입력 unavailable, 과거 Candidate/Run은 유지
- RemoteCopy 만료: 필요 시 재준비, 기존 AnalysisRun은 유지
- IncidentClip 생성 실패: Search/Evidence 결과 유지
- DerivedAsset/Report Video export 실패: Evidence 결과 유지, Package 준비 상태는 별도 흐름에서 판단
- 일부 Source/Stream 실패: 정상 Source/Stream의 파생물은 유지 가능

**최소 machine-readable failure code (2026-09-08 확정).** `case`가 `CaseView.notices[].code`로, `readout`이 `ReadoutRun.failure`로 옮길 수 있어야 한다.

| capability | 최소 code |
| --- | --- |
| `open_analysis_source` | `NOT_FOUND` · `UNAVAILABLE` · `UNSUPPORTED_MEDIA` · `TEMPORARY_FAILURE` (§4.2) |
| `build_incident_clip` | `INCIDENT_CLIP_BUILD_FAILED` |
| Report Video export | `REPORT_VIDEO_EXPORT_FAILED` |

failure의 공통 모양은 `{kind, code}`다. recording의 `kind`/`code` 값 집합은 recording이 소유하며 다른 모듈의 taxonomy와 공통 enum처럼 비교하지 않는다.

---

## 10. 금지사항

- `AnalysisSource = 항상 proxy`로 고정
- proxy resolution/FPS/bitrate 임의 확정
- public AnalysisSource에 storage/provider locator·인증정보 노출
- provider별 upload/delete 방식을 recording 계약에 구현 세부로 고정
- retention days 임의 확정
- RemoteCopy provider ID를 Search 외 Consumer가 provider API 의미로 직접 해석
- IncidentClip을 Report Video 또는 confirmed Evidence와 동일시
- canonical identity가 없는 AssetSpan에 합성 ref 부여 · Consumer가 canonical 값을 결합·해시해 span ref 발급
- `timeline_range`만 주고 `timeline_ref`를 생략
- `profile_ref`를 `null`로 반환 · Consumer가 `profile_ref` 문자열을 파싱
- ref prefix parsing으로 asset kind 추론 · `kind`의 대소문자 무시 비교
- `web → recording`, `evidence → recording` 직접 호출
- evidence policy가 소유하는 판정 매핑(`derived_role` 필수성 · 경계 잘림 허용 폭 · `availability → BLOCK/UNKNOWN`)을 이 계약에 고정

---

## 11. Pending (Consumer Review 후에도 열려 있는 항목)

계약 확정을 막지 않는 것으로 확인된 미결이다. 완성도를 위해 채우지 않는다.

1. 정확한 profile 값 목록과 보장 속성 — recording·search·readout 3자 합의. `profile_ref`의 필수성·opaque성·소유는 §4.4에서 확정됐다
2. 정확한 `stream_selector` serialization과 기본 stream 선택 정책
3. thumbnail 이미지 전달 방식
4. provider별 upload/delete 구현·즉시 delete 지원 여부·retention 기간
5. proxy resolution/FPS/bitrate
6. `derived_role`의 추가 값(등재 2건은 §7.3에서 확정)
7. `transform_ref` payload exact schema(조회 가능성 보장은 §7.4에서 확정)
8. `build_incident_clip` options schema

새로운 cross-owner 결정이 필요한 항목은 임의 반영하지 않고 별도 결정 회차로 분리한다.

## 12. 버전과 호환성

- 문서 헤더와 모든 JSON payload는 `analysis-source-derived/v1` 한 문자열을 쓴다.
- Consumer는 알지 못하는 optional 필드를 무시한다. 기존 의미를 바꾸지 않는 optional 필드 추가는 minor 변경으로 충분하다.
- 필수 필드 추가, 기존 타입 변경, nullable 축소, enum 값 제거는 breaking change다. Final 이후에는 major version과 migration이 필요하다.
- Draft v0.2 → v1에서 바뀐 것: `IncidentClip.source_provenance`의 span 구조·단위(ms 평탄 → canonical `AssetSpan` 초 단위 중첩 + `sequence` 필수) · `timeline_range`의 단위(ms → 초)와 `timeline_ref` 동반 필수 · `profile_ref` non-null · `ContractRef.kind` 소문자 표기 · `RemoteCopy`·`IncidentClip` 필드표 신설 · `DeletionReport` 구조. **Draft 단계의 v0.x 변경은 호환성을 보장하지 않으며 구현 코드가 없어 migration 대상 payload도 없다.**

## 13. 한 줄 결정

> `recording`은 분석 입력, provider 원격 사본 registry, Source-derived 사건 clip 및 신고·보조 파생물을 서로 다른 opaque identity와 provenance/lifecycle로 관리하며, 사건 구간의 canonical reference를 `incident_clip` ref로 단일화하고, Search가 내부 저장소 구조를 몰라도 실제 분석 media를 열 수 있는 capability를 제공한다.
