# Draft Data Contract — SourceAsset + MediaStream + FrameRef v0.2

**Status:** `Draft — Consumer Review 대기`

**Accepted:** 해당 없음 — Consumer Review 대기

**Architecture Contract:** v4 §5-1 ② — `SourceAsset` / `MediaStream` / `FrameRef`

**Contract:** `SourceAsset` / `MediaStream` / `FrameRef`

**Contract Version:** `source-asset-media-stream/v0.2`

**Related ADR:** `adr/adr-data-contract-call-closure-2026-09-07.md` §4.6(B07), §4.9(W07 잔여)

**Contract Lead / Owner:** 정철원 (`recording`)

**Runtime Producer:** `recording`

**Consumers:** 서어진 (`search`) · 신유민 (`readout`) · 유소연 (`case`) · 김준영 (`evidence`)

**관련 Architecture:** `../module-architecture.md` Core ②

> 이 문서는 CALL-11에서 합의된 의미와 경계를 정식 계약 초안으로 옮긴다. `AssetFacts`의 canonical 정의는 이 문서 한 곳이 소유한다. `Pending` 항목은 Consumer Review 전까지 확정하지 않는다.

---

## 1. 계약 목적

`recording`이 소유하는 물리 Source 파일, 그 안의 MediaStream, 특정 canonical frame을 서로 다른 identity로 표현한다. 다른 모듈은 opaque ref 문자열을 파싱하지 않고도 관계, 위치 및 필요한 자산 사실을 조회할 수 있어야 한다.

핵심 원칙:

1. `SourceAsset != MediaStream`이다.
2. 한 `SourceAsset`에는 여러 video/audio stream이 존재할 수 있다.
3. ref의 의미를 문자열 구조에서 추론하지 않는다.
4. `FrameRef`는 특정 canonical frame의 안정적인 identity다.
5. Timeline rebase는 기존 `FrameRef`의 의미를 바꾸지 않는다.
6. 사용자 외부 원본과 서비스 관리 사본·파생물의 삭제 권한을 섞지 않는다.

---

## 2. 공통 Ref

```
SourceAsset ref : sa_<opaque-id>
MediaStream ref : ms_<opaque-id>
FrameRef        : fr_<opaque-id>
```

prefix는 사람이 구분하기 위한 serialization convention이다. Consumer는 prefix나 나머지 문자열을 파싱해 asset 종류, stream role 또는 source 위치를 추론하지 않는다. 관계와 의미는 반드시 아래 계약 필드로 전달한다.

이 계약군에서 사용하는 `ContractRef`의 최소 형태는 다음과 같다.

```json
{
  "kind": "SOURCE_ASSET",
  "ref": "sa_01JREC000000000000000001"
}
```

`kind`는 이 문서에서 `SOURCE_ASSET`, `MEDIA_STREAM`, `FRAME`을 사용한다. 다른 계약이 소유하는 kind는 해당 계약을 따른다.

---

## 3. `SourceAsset`

### 3.1 의미

`SourceAsset`은 recording이 등록·probe하는 물리 파일 단위의 Source 사실이다. SourceAsset 하나를 video stream 하나와 동일하게 취급하지 않는다.

### 3.2 Schema

```json
{
  "contract": "SourceAsset",
  "contract_version": "0.2.0",
  "source_asset_ref": "sa_01JREC000000000000000001",
  "asset_kind": "SOURCE_ASSET",
  "external_source_ref": {
    "kind": "EXTERNAL_SOURCE",
    "ref": "ext_01JREC000000000000000001"
  },
  "media_stream_refs": [
    "ms_01JREC000000000000000001",
    "ms_01JREC000000000000000002"
  ],
  "byte_size": 734003200,
  "availability": "AVAILABLE",
  "duration_sec": 1200.25
}
```

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `contract` | Y | `SourceAsset` |
| `contract_version` | Y | 이 Draft는 `0.2.0` |
| `source_asset_ref` | Y | SourceAsset opaque identity |
| `asset_kind` | Y | 항상 `SOURCE_ASSET` |
| `external_source_ref` | N | 사용자 외부 원본 reference가 별도로 존재할 때의 관계 |
| `media_stream_refs[]` | Y | 이 물리 파일에서 식별된 MediaStream refs |
| `byte_size` | Y | 파일 크기, 0 이상의 정수 |
| `availability` | Y | `AVAILABLE`, `UNAVAILABLE`, `UNKNOWN` |
| `duration_sec` | N | 물리 media duration, 0 이상의 초 |

### 3.3 Invariants

1. `source_asset_ref`는 다른 SourceAsset에 재사용하지 않는다.
2. `media_stream_refs[]`의 각 MediaStream은 이 SourceAsset을 역참조해야 한다.
3. 사용자 외부 원본은 서비스가 임의 overwrite/delete하지 않는다.
4. 파일 하나의 probe 실패가 다른 SourceAsset의 가용성을 자동으로 무효화하지 않는다.
5. `asset_kind`는 ref prefix에서 계산하지 않고 recording이 명시적으로 제공한다.
6. `media_stream_refs=[]`의 허용 조건은 Consumer Review 대상이다.

---

## 4. `MediaStream`

### 4.1 의미

`MediaStream`은 하나의 `SourceAsset` 안에 존재하는 개별 video/audio stream identity다. media 종류와 camera role은 서로 다른 의미다.

### 4.2 Schema

```json
{
  "contract": "MediaStream",
  "contract_version": "0.2.0",
  "media_stream_ref": "ms_01JREC000000000000000001",
  "source_asset_ref": "sa_01JREC000000000000000001",
  "media_type": "VIDEO",
  "role": "FRONT",
  "availability": "AVAILABLE",
  "duration_sec": 1200.25
}
```

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `media_stream_ref` | Y | MediaStream opaque identity |
| `source_asset_ref` | Y | 소속 SourceAsset |
| `media_type` | Y | `VIDEO` 또는 `AUDIO` |
| `role` | 조건부 | video camera role. Draft 값은 `FRONT`, `REAR`, `UNKNOWN`; audio에는 사용하지 않음 |
| `availability` | Y | 해당 stream의 decode/조회 가용 상태 |
| `duration_sec` | N | stream별 duration, 0 이상의 초 |

### 4.3 Invariants

1. 같은 SourceAsset에 여러 MediaStream이 존재할 수 있다.
2. MediaStream identity를 camera role에서 파생하지 않는다.
3. camera role을 모르는 video도 identity를 유지하고 `role=UNKNOWN`으로 표현한다.
4. `AUDIO`는 camera role이 아니라 `media_type`이다.
5. 특정 stream decode 실패가 다른 stream 또는 SourceAsset 전체 실패를 의미하지 않는다.
6. codec/fps/resolution은 B07 evidence 최소 입력에 포함하지 않는다.

`media_type`, `role`의 최종 enum/nullability와 `stream_selector` 직렬화는 Pending이다.

---

## 5. `FrameRef`

### 5.1 의미 및 Schema

`FrameRef`는 하나의 canonical frame image를 안정적으로 재참조하는 opaque identity다.

```json
{
  "contract": "FrameRef",
  "contract_version": "0.2.0",
  "frame_ref": "fr_01JREC000000000000000001",
  "media_stream_ref": "ms_01JREC000000000000000001",
  "source_offset_sec": 312.48
}
```

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `frame_ref` | Y | canonical frame opaque identity |
| `media_stream_ref` | Y | frame이 속한 visual/video stream |
| `source_offset_sec` | Y | MediaStream local position, 0 이상의 초 |

### 5.2 확정 보장

1. `frame_ref`는 `fr_<opaque-id>`이며 Consumer는 문자열을 파싱하지 않는다.
2. 동일 MediaStream의 동일 canonical frame은 재조회 시 같은 FrameRef를 사용한다.
3. 서로 다른 MediaStream의 같은 시각 frame은 같은 FrameRef일 필요가 없다.
4. `read_frame(frame_ref)`로 실제 frame을 얻을 수 있다.
5. `media_stream_ref`와 source-relative offset을 계약 필드로 조회할 수 있다.
6. Timeline rebase 후에도 같은 FrameRef가 다른 frame을 가리키지 않는다.
7. `source_offset_sec`는 RecordingTimeline의 absolute/relative display time이 아니다.

canonical frame 선택·반올림 알고리즘은 recording Tech Spec이 소유하되, 동일성 보장을 깨뜨릴 수 없다.

### 5.3 Public capability

```
read_frame(frame_ref: string) -> readable frame image
```

bytes/streaming 등 runtime 반환 타입과 함수명은 구현에서 조정할 수 있다. 다만 FrameRef만으로 실제 frame을 획득할 수 있다는 capability 의미는 계약 보장이다.

---

## 6. Canonical `AssetFacts`

`AssetFacts`의 필드명과 의미는 이 절 한 곳이 소유한다. `contract-analysis-source-derived.md`를 포함한 다른 계약은 이 구조를 복제 정의하지 않고 이 절을 참조한다.

```json
{
  "contract": "AssetFacts",
  "contract_version": "0.2.0",
  "asset_ref": {
    "kind": "SOURCE_ASSET",
    "ref": "sa_01JREC000000000000000001"
  },
  "asset_kind": "SOURCE_ASSET",
  "derived_role": null,
  "byte_size": 734003200,
  "availability": "AVAILABLE",
  "checked_at": "2026-09-08T00:35:00+09:00",
  "lineage": [
    {
      "kind": "EXTERNAL_SOURCE",
      "ref": "ext_01JREC000000000000000001"
    }
  ],
  "duration_sec": 1200.25,
  "timeline_range": null
}
```

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `asset_ref` | Y | 종류와 opaque ref를 함께 전달하는 `ContractRef` |
| `asset_kind` | Y | ref를 파싱하지 않고 확인하는 자산 종류 |
| `derived_role` | Y | 파생 자산 역할. 해당 없거나 미확정이면 `null` |
| `byte_size` | Y | `AVAILABLE`이면 0 이상의 정수. 측정 불가 상태는 `null` |
| `availability` | Y | `AVAILABLE`, `UNAVAILABLE`, `UNKNOWN` |
| `checked_at` | Y | 존재·가용 여부를 판정한 offset-aware datetime |
| `lineage[]` | Y | source/derived-from provenance. 없으면 빈 배열 |
| `duration_sec` | Y | 알려졌으면 0 이상의 초, 아니면 `null` |
| `timeline_range` | Y | coverage 판정에 사용할 범위, 해당 없거나 미확정이면 `null` |

### 6.1 Invariants

1. `asset_ref.kind`, `asset_kind` 및 실제 참조 대상의 의미가 일치해야 한다.
2. `availability=AVAILABLE`이면 `byte_size`는 `null`일 수 없다.
3. `availability!=AVAILABLE`이면 측정하지 못한 `byte_size`를 0으로 꾸미지 않고 `null`을 허용한다.
4. `checked_at`은 모든 상태에서 필수이며 offset 없는 datetime을 금지한다.
5. `derived_role`과 lineage를 ref prefix에서 추론하지 않는다.
6. resolution/fps/codec/원본 무변형 checksum/번호판 가시성/화면 timestamp 표시 여부는 현재 evidence 최소 입력에서 제외한다.

### 6.2 Public capability와 호출 경계

```
lookup_asset_facts(asset_ref: ContractRef) -> AssetFacts
```

```
case / orchestration
        ↓
recording asset lookup
        ↓
AssetFacts
        ↓
case / orchestration
        ↓
evidence.check_requirements(..., assets)
```

- `evidence`와 `web`은 recording을 직접 호출하지 않는다.
- `sa_`, `da_` 등의 prefix를 파싱해 kind를 추론하지 않는다.

---

## 7. `CaseView.candidates[].thumb_ref`

`thumb_ref`의 자산 종류는 `FrameRef`다.

```
CaseView.candidates[].thumb_ref -> FrameRef -> fr_<opaque-id>
```

실제 이미지는 `case → recording read/lookup → projection → CaseView → web` 경계를 따른다. URL/ref/endpoint/stream 중 어떤 방식으로 이미지를 전달할지는 Pending이다.

---

## 8. 금지사항

- `asset_id == video stream id` 가정
- `AUDIO`를 camera role로 취급
- ref 문자열 parsing으로 자산 종류·role·position 추론
- `frame_ref`에 `media_stream_ref@offset` 같은 위치 의미 인코딩
- `web → recording`, `evidence → recording` 직접 호출
- 이 계약에서 `stream_selector` 또는 thumbnail 전달 방식을 임의 확정

---

## 9. Pending / Consumer Review

1. `MediaStream.media_type`, `role`의 최종 enum/nullability
2. `SourceAsset.media_stream_refs=[]` 허용 조건
3. `AssetFacts.asset_kind` 전체 vocabulary와 외부 계약 kind 매핑
4. lineage의 필수 최소 구성
5. 정확한 `stream_selector` serialization
6. thumbnail 이미지 전달 방식

---

## 10. Draft 한 줄 결정

> `recording`은 물리 파일 `SourceAsset`, 그 안의 `MediaStream`, canonical frame `FrameRef`를 서로 다른 opaque identity로 제공하고, 관계·source-relative 위치·판정 시점이 포함된 자산 사실을 정식 필드와 lookup으로 노출한다.
