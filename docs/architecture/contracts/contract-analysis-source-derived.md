# Draft Data Contract — AnalysisSource + RemoteCopy + IncidentClip + DerivedAsset v0.2

**Status:** `Draft — Consumer Review 대기`

**Accepted:** 해당 없음 — Consumer Review 대기

**Architecture Contract:** v4 §5-1 ③ — `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset`

**Contract:** `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset`

**Contract Version:** `analysis-source-derived/v0.2`

**Related ADR:** `adr/adr-data-contract-call-closure-2026-09-07.md` §4.6(B07), §4.9(W07 잔여)

**Contract Lead / Owner:** 정철원 (`recording`)

**Runtime Producer:** `recording`

**Consumers:** 서어진 (`search`) · 신유민 (`readout`) · 유소연 (`case`) · 김준영 (`evidence`)

**관련 Architecture:** `../module-architecture.md` Core ③

> 이 문서는 CALL-11에서 합의된 분석 입력, provenance 및 lifecycle 경계를 계약 초안으로 옮긴다. 공통 `AssetFacts`는 `contract-source-asset-media-stream.md` §6을 그대로 사용하며 여기서 재정의하지 않는다.

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

---

## 3. 공통 `AssetFacts` 사용

이 계약의 AnalysisSource, IncidentClip, DerivedAsset에 대한 자산 사실은 `contract-source-asset-media-stream.md` §6의 canonical `AssetFacts`와 `lookup_asset_facts(asset_ref)`를 사용한다.

- `AssetFacts`를 이 문서에 복제 정의하지 않는다.
- `asset_kind`, `derived_role`, `availability`, `checked_at`, `lineage`, 조건부 duration/timeline 정보는 canonical 정의를 따른다.
- `case/orchestration`이 recording에서 조회해 evidence 입력에 주입한다.
- evidence와 web은 recording을 직접 호출하지 않는다.

---

## 4. `AnalysisSource`

### 4.1 의미와 Schema

`AnalysisSource`는 recording이 해석한 Source 구간에서 준비한 실제 분석 가능한 media input이다. Search는 AssetSpan의 storage path/URL을 직접 사용하지 않고 AnalysisSource capability를 통해 입력을 얻는다.

```json
{
  "contract": "AnalysisSource",
  "contract_version": "0.2.0",
  "analysis_source_ref": "as_01JREC000000000000000001",
  "asset_kind": "ANALYSIS_SOURCE",
  "source_refs": [
    {
      "kind": "SOURCE_ASSET",
      "ref": "sa_01JREC000000000000000001"
    }
  ],
  "media_stream_refs": [
    "ms_01JREC000000000000000001"
  ],
  "byte_size": 104857600,
  "availability": "AVAILABLE",
  "duration_sec": 180.0,
  "timeline_range": {
    "start_ms": 300000,
    "end_ms": 480000
  },
  "profile_ref": null
}
```

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `analysis_source_ref` | Y | opaque identity |
| `asset_kind` | Y | 항상 `ANALYSIS_SOURCE` |
| `source_refs[]` | Y | 원본 Source provenance |
| `media_stream_refs[]` | Y | 실제 분석 pixel/audio가 유래한 streams |
| `byte_size` | Y | materialized media 크기 |
| `availability` | Y | 현재 입력 가용 상태 |
| `duration_sec` | N | 분석 media duration |
| `timeline_range` | N | 분석 입력이 포괄하는 RecordingTimeline 범위 |
| `profile_ref` | N | 준비 profile의 opaque ref. 값과 필수성은 Pending |

### 4.2 보장 및 capability

```
prepare_analysis_source(span, profile) -> AnalysisSource
open_analysis_source(analysis_source_ref) -> readable media stream
```

1. Search는 `open_analysis_source` capability를 통해 실제 Provider 분석에 전달할 bytes/stream을 얻을 수 있다.
2. public 계약에 local path, S3/GCS URI 또는 provider object ID를 노출할 필요는 없다.
3. 원본·부분·proxy 중 어떤 전략을 사용할지는 profile 합의 대상이며 “항상 proxy”를 강제하지 않는다.
4. 반환 media의 Source/MediaStream lineage를 추적할 수 있어야 한다.
5. runtime stream 타입, provider adapter 연결 및 저장소 locator는 내부 Tech Spec이 소유한다.
6. profile 값과 `stream_selector` 직렬화는 Pending이다.

---

## 5. `RemoteCopy`

### 5.1 의미와 Schema

`RemoteCopy`는 외부 AI provider 등에 올라간 AnalysisSource의 copy/reference를 재사용하기 위한 registry record다.

```json
{
  "contract": "RemoteCopy",
  "contract_version": "0.2.0",
  "remote_copy_ref": "rc_01JREC000000000000000001",
  "analysis_source_ref": "as_01JREC000000000000000001",
  "provider": "example-provider",
  "provider_object_ref": "provider-object-opaque-001",
  "availability": "AVAILABLE",
  "expires_at": "2026-09-09T00:35:00+09:00"
}
```

### 5.2 Invariants

1. `remote_copy_ref`와 `provider_object_ref`는 opaque다.
2. registry 조회 키의 의미는 `(analysis_source_ref, provider)`다.
3. 같은 AnalysisSource의 서로 다른 provider copy는 별도 RemoteCopy다.
4. 동일한 유효 RemoteCopy를 coarse/fine에서 재사용할 수 있다.
5. expiry 이후에도 기존 AnalysisRun의 의미는 바뀌지 않는다.
6. expiry/availability에 따라 새 RemoteCopy를 만들 수 있다.
7. provider별 upload/delete 구현은 `search/providers` 소관이다.
8. 즉시 delete 지원 여부와 retention 기간은 Pending이다.

### 5.3 Public capability

```
find_remote_copy(analysis_source_ref, provider) -> RemoteCopy?
register_remote_copy(analysis_source_ref, provider, remote_info) -> RemoteCopy
```

recording이 registry owner라는 경계가 계약이며 구체 함수명은 구현에서 조정할 수 있다.

---

## 6. `IncidentClip`

### 6.1 의미

`IncidentClip`은 Candidate/Timeline span을 recording이 실제 Source/MediaStream 경계로 해석해 만든 분석·검토용 Source-derived 사건 구간이다.

- `IncidentClip != AssetSpan`
- `IncidentClip != Report Video`
- `IncidentClip != confirmed Evidence`

### 6.2 Schema

canonical `AssetSpan`은 독립 ID를 보장하지 않으므로 존재하지 않는 `source_span_ref`를 만들지 않는다. 재현에 필요한 timeline과 span 값을 provenance에 직접 보존한다.

```json
{
  "contract": "IncidentClip",
  "contract_version": "0.2.0",
  "incident_clip_ref": "clip_01JREC000000000000000001",
  "asset_kind": "INCIDENT_CLIP",
  "source_provenance": {
    "timeline_ref": {
      "timeline_id": "tl_01JREC000000000000000001",
      "revision": 3
    },
    "requested_range": {
      "start_ms": 300000,
      "end_ms": 420000
    },
    "asset_spans": [
      {
        "source_asset_ref": "sa_01JREC000000000000000001",
        "media_stream_ref": "ms_01JREC000000000000000001",
        "source_start_sec": 300.0,
        "source_end_sec": 420.0,
        "timeline_start_ms": 300000,
        "timeline_end_ms": 420000
      }
    ]
  },
  "media_stream_refs": [
    "ms_01JREC000000000000000001"
  ],
  "byte_size": 73400320,
  "availability": "AVAILABLE",
  "duration_sec": 120.0,
  "timeline_range": {
    "start_ms": 300000,
    "end_ms": 420000
  }
}
```

### 6.3 Invariants

1. `incident_clip_ref`는 opaque identity다.
2. `source_provenance.asset_spans[]`는 `contract-recording-timeline-asset-span.md`가 정의한 canonical AssetSpan 필드 형태를 따른다.
3. AssetSpan에 canonical identity가 추가되기 전에는 합성 `source_span_ref`를 만들지 않는다.
4. `timeline_ref.revision`으로 provenance가 어느 timeline 해석에서 생성됐는지 고정한다.
5. 복수 파일 경계를 넘는 materialization 책임은 recording에 있다.
6. clip 생성 실패가 Search Candidate 또는 Evidence observation을 자동 삭제하지 않는다.
7. clip 자체에 법적 위반 여부, 신고 유형 또는 final `occurred_at`을 넣지 않는다.

### 6.4 Public capability

```
build_incident_clip(span, options) -> IncidentClip
```

`options`의 exact schema는 Pending이다.

---

## 7. `DerivedAsset`

### 7.1 의미와 Schema

`DerivedAsset`은 대신고가 생성하는 재생성 가능한 파생 자산의 공통 의미다.

```json
{
  "contract": "DerivedAsset",
  "contract_version": "0.2.0",
  "derived_asset_ref": "da_01JREC000000000000000001",
  "asset_kind": "DERIVED_ASSET",
  "derived_role": "REPORT_VIDEO",
  "source_refs": [
    {
      "kind": "INCIDENT_CLIP",
      "ref": "clip_01JREC000000000000000001"
    }
  ],
  "byte_size": 52428800,
  "availability": "AVAILABLE",
  "duration_sec": 120.0,
  "timeline_range": {
    "start_ms": 300000,
    "end_ms": 420000
  },
  "transform_ref": null
}
```

### 7.2 Invariants

1. `derived_asset_ref`는 opaque identity다.
2. `derived_role`은 ref prefix에서 추론하지 않는다.
3. 사용자 외부 원본 Source와 DerivedAsset을 동일 asset으로 취급하지 않는다.
4. export 시점까지의 lineage를 추적할 수 있어야 한다.
5. `transform_ref`가 있으면 파생 과정 provenance를 가리킨다.
6. exact `derived_role`, transform schema 및 retention 기간은 Pending이다.
7. Report Video 생성 실패가 이미 확정된 Evidence를 무효화하지 않는다.

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
- 정확한 retention 기간은 Pending이다.

---

## 9. 실패 경계

- AnalysisSource 준비 실패: 해당 분석 입력 unavailable, 과거 Candidate/Run은 유지
- RemoteCopy 만료: 필요 시 재준비, 기존 AnalysisRun은 유지
- IncidentClip 생성 실패: Search/Evidence 결과 유지
- DerivedAsset/Report Video export 실패: Evidence 결과 유지, Package 준비 상태는 별도 흐름에서 판단
- 일부 Source/Stream 실패: 정상 Source/Stream의 파생물은 유지 가능

---

## 10. 금지사항

- `AnalysisSource = 항상 proxy`로 고정
- proxy resolution/FPS/bitrate 임의 확정
- public AnalysisSource에 storage/provider locator 노출을 필수화
- provider별 upload/delete 방식을 recording 계약에 구현 세부로 고정
- retention days 임의 확정
- RemoteCopy provider ID를 Search 외 Consumer가 provider API 의미로 직접 해석
- IncidentClip을 Report Video 또는 confirmed Evidence와 동일시
- canonical ID가 없는 AssetSpan에 합성 ref 부여
- ref prefix parsing으로 asset kind 추론
- `web → recording`, `evidence → recording` 직접 호출

---

## 11. Pending / Consumer Review

1. `AnalysisSource.profile_ref` 필수성과 profile 값
2. 정확한 `stream_selector` serialization
3. thumbnail 전달 방식
4. provider별 upload/delete 구현과 즉시 delete 지원 여부
5. retention 기간
6. proxy profile 값
7. `DerivedAsset.derived_role` 최종 enum
8. `transform_ref` exact shape
9. `IncidentClip.build` options schema

새로운 cross-owner 결정이 필요한 항목은 임의 반영하지 않고 별도 CALL로 분리한다.

---

## 12. Draft 한 줄 결정

> `recording`은 분석 입력, provider 원격 사본 registry, Source-derived 사건 clip 및 신고·보조 파생물을 서로 다른 opaque identity와 provenance/lifecycle로 관리하며, Search가 내부 저장소 구조를 몰라도 실제 분석 media를 열 수 있는 capability를 제공한다.
