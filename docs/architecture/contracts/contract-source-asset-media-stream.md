# Final Data Contract — SourceAsset + MediaStream + FrameRef v1

**Status:** `Final — Accepted`

> **Consumer Review 종결 (2026-09-08).** Draft v0.2에 대해 `search`·`readout`·`case`·`evidence` 4 Consumer의 검토가 끝났고, 네 Consumer가 승인 전제로 제시한 필수 변경을 Owner(정철원)가 모두 수용해 이 개정본에 반영했다. 함께 자산 ref `kind` 표기(소문자 snake_case)와 `AssetSpan` identity 결정이 확정되어 `CALL_REQUIRED` 표기가 사라졌다. 반영 내역·미반영 요청·조건 충족 근거는 짝 ADR `adr/adr-source-asset-media-stream.md` §7, 결정 원장은 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.10.

**Accepted:** `2026-09-08` (Consumer Review 4건 종결 + 자산 ref `kind`·`AssetSpan` identity 결정 반영. Owner 정철원. 이견 시 되돌린다)

**Architecture Contract:** v4 §5-1 ② — `SourceAsset` / `MediaStream` / `FrameRef`

**Contract:** `SourceAsset` / `MediaStream` / `FrameRef` / canonical `AssetFacts`

**Contract Version:** `source-asset-media-stream/v1` (문서 헤더와 모든 JSON payload가 같은 문자열을 쓴다. `1.0.0` 형식과 혼용하지 않는다)

**Related ADR:** `adr/adr-source-asset-media-stream.md` · `adr/adr-data-contract-call-closure-2026-09-07.md` §4.6(B07)·§4.9(W07) · `adr/adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.10

**Contract Lead / Owner:** 정철원 (`recording`)

**Runtime Producer:** `recording`

**Consumers:** 서어진 (`search`) · 신유민 (`readout`) · 유소연 (`case`) · 김준영 (`evidence`)

**관련 Architecture:** `../module-architecture.md` Core ②

> 이 문서는 CALL-11에서 합의된 의미와 경계를 계약으로 옮기고, 2026-09-08 Consumer Review 결과를 반영한 확정본이다. `AssetFacts`의 canonical 정의와 **자산 계층 `ContractRef.kind` 값 공간**은 이 문서 한 곳이 소유한다. `Pending`으로 남은 항목은 확정하지 않는다 — 완성도를 위해 채우지 않는다.

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

## 2. 공통 Ref와 자산 계층 `ContractRef.kind`

```
SourceAsset ref : sa_<opaque-id>
MediaStream ref : ms_<opaque-id>
FrameRef        : fr_<opaque-id>
```

prefix는 사람이 구분하기 위한 serialization convention이다. Consumer는 prefix나 나머지 문자열을 파싱해 asset 종류, stream role 또는 source 위치를 추론하지 않는다. 관계와 의미는 반드시 아래 계약 필드로 전달한다.

`ContractRef`의 최소 형태는 다음과 같다(모양의 정의처는 `contract-observation.md` §3).

```json
{
  "kind": "source_asset",
  "ref": "sa_01JREC000000000000000001"
}
```

### 2.1 값 공간과 소유

**자산 계층 `ContractRef.kind` 값 공간은 이 절 한 곳이 소유한다.** 다른 계약은 이 목록을 복제 정의하지 않고 이 절을 가리킨다. 자산 계층이 아닌 ref(`analysis_run`·`readout_run`·`evidence_record`·`analysis_scope` 등)는 각각의 소유 계약이 자기 값을 정한다.

| `kind` | 참조 대상 | 정의처 |
| --- | --- | --- |
| `external_source` | 사용자 외부 원본 reference | 이 계약 §3 |
| `source_asset` | 물리 파일 단위 Source | 이 계약 §3 |
| `media_stream` | SourceAsset 안의 개별 stream | 이 계약 §4 |
| `frame` | canonical frame | 이 계약 §5 |
| `analysis_source` | 준비된 분석 입력 | `contract-analysis-source-derived.md` §4 |
| `remote_copy` | provider 사본 registry record | `contract-analysis-source-derived.md` §5 |
| `incident_clip` | Source-derived 사건 구간 clip | `contract-analysis-source-derived.md` §6 |
| `derived_asset` | Report Video·Plate Image 등 파생 자산 | `contract-analysis-source-derived.md` §7 |

### 2.2 표기 규칙 (2026-09-08 확정 · Decider 정철원 · 확인 김준영·서어진·유소연)

1. 자산 계층 `kind`는 **소문자 snake_case**다. 이미 확정된 run ref(`analysis_run`·`readout_run`)와 `Observation`·`TimeResolution`·`RequirementReport`의 기존 예시가 쓰는 표기와 같다.
2. 같은 참조 대상에 두 표기를 공존시키지 않는다. 대문자 별칭을 만들지 않는다.
3. Consumer는 **정확한 문자열**로 비교한다. 대소문자 무시 비교, 대문자·소문자 별칭 허용, ref prefix를 통한 `kind` 추론, Consumer별 `kind` 변환표 운영을 모두 금지한다.
4. `AssetFacts.asset_kind`(§6)는 대문자 enum을 유지한다 — 판정용 enum과 라우팅용 `kind`는 역할이 다르므로 문자열 동일성을 요구하지 않고 §6.2 대응표로 연결한다.
5. `AnalysisRun.input_ref.kind = ANALYSIS_SCOPE`는 자산 계층 ref가 아니며 `contract-analysis-scope.md`·`contract-analysis-run-candidate-event.md`가 소유하는 별도 값이다. 이 결정의 변경 대상이 아니고, 이를 근거로 모든 `ContractRef.kind`에 전역 대문자 규칙을 적용하지 않는다.

---

## 3. `SourceAsset`

### 3.1 의미

`SourceAsset`은 recording이 등록·probe하는 물리 파일 단위의 Source 사실이다. SourceAsset 하나를 video stream 하나와 동일하게 취급하지 않는다.

### 3.2 Schema

```json
{
  "contract": "SourceAsset",
  "contract_version": "source-asset-media-stream/v1",
  "source_asset_ref": "sa_01JREC000000000000000001",
  "asset_kind": "SOURCE_ASSET",
  "external_source_ref": {
    "kind": "external_source",
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

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `contract` | Y | string | `SourceAsset` |
| `contract_version` | Y | string | `source-asset-media-stream/v1` |
| `source_asset_ref` | Y | string | SourceAsset opaque identity |
| `asset_kind` | Y | enum | 항상 `SOURCE_ASSET` |
| `external_source_ref` | Y(키 항상 존재) | `ContractRef{kind:"external_source"}` \| null | 사용자 외부 원본 reference. 없으면 `null` |
| `media_stream_refs[]` | Y | string[] | 이 물리 파일에서 식별된 MediaStream refs |
| `byte_size` | Y(키 항상 존재) | integer ≥ 0 \| null | §3.4 |
| `availability` | Y | enum | `AVAILABLE` \| `UNAVAILABLE` \| `UNKNOWN` (§3.5) |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | 물리 media duration. 모르면 `null`(§3.4) |

### 3.3 Invariants

1. `source_asset_ref`는 다른 SourceAsset에 재사용하지 않는다.
2. `media_stream_refs[]`의 각 MediaStream은 이 SourceAsset을 역참조해야 한다.
3. 사용자 외부 원본은 서비스가 임의 overwrite/delete하지 않는다.
4. 파일 하나의 probe 실패가 다른 SourceAsset의 가용성을 자동으로 무효화하지 않는다.
5. `asset_kind`는 ref prefix에서 계산하지 않고 recording이 명시적으로 제공한다.
6. `media_stream_refs=[]`의 허용 조건은 Pending이다(§9-2).

### 3.4 `byte_size` · `duration_sec`의 null 규칙 (2026-09-08 확정)

이 계약군의 `SourceAsset` · `MediaStream` · `AssetFacts`는 두 필드에 같은 규칙을 쓴다 — **키는 항상 존재하고 값이 `null`일 수 있다.** 「키 부재」와 「`null`」을 혼용하지 않는다.

```
byte_size    : integer >= 0 | null
duration_sec : number  >= 0 | null
```

- `availability=AVAILABLE`이면 `byte_size`는 non-null이다.
- `UNKNOWN`·`UNAVAILABLE`에서 측정하지 못한 크기는 `null`이다. **0으로 꾸미지 않는다.**
- `duration_sec`은 모든 상태에서 모르면 `null`이다.

### 3.5 `availability` 값 공간과 부여 조건 (2026-09-08 확정)

`SourceAsset` · `MediaStream` · `AssetFacts`는 **동일한 값 공간과 부여 조건**을 쓴다.

| 값 | 부여 조건 |
| --- | --- |
| `AVAILABLE` | 확인 시점에 대상이 존재하고 해당 계약 capability로 읽거나 decode할 수 있다 |
| `UNAVAILABLE` | 대상은 식별했지만 존재하지 않거나 접근·decode할 수 없다 |
| `UNKNOWN` | 아직 확인하지 않았거나, 확인 작업이 실패해 상태를 판정할 수 없다 |

- 한 MediaStream의 `UNAVAILABLE`이 SourceAsset 전체나 다른 stream의 상태를 자동으로 바꾸지 않는다.
- recording은 **상태 사실만** 제공한다. 이 값을 신고 규칙상 `BLOCK`/`UNKNOWN` 중 무엇으로 볼지는 `evidence` policy가 소유하며 이 계약에 고정하지 않는다.

---

## 4. `MediaStream`

### 4.1 의미

`MediaStream`은 하나의 `SourceAsset` 안에 존재하는 개별 video/audio stream identity다. media 종류와 camera role은 서로 다른 의미다.

### 4.2 Schema

```json
{
  "contract": "MediaStream",
  "contract_version": "source-asset-media-stream/v1",
  "media_stream_ref": "ms_01JREC000000000000000001",
  "source_asset_ref": "sa_01JREC000000000000000001",
  "media_type": "VIDEO",
  "role": "FRONT",
  "availability": "AVAILABLE",
  "duration_sec": 1200.25
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `media_stream_ref` | Y | string | MediaStream opaque identity |
| `source_asset_ref` | Y | string | 소속 SourceAsset |
| `media_type` | Y | enum | `VIDEO` 또는 `AUDIO` |
| `role` | 조건부 | enum \| null | video camera role. 값은 `FRONT` · `REAR` · `UNKNOWN`. audio에는 사용하지 않는다 |
| `availability` | Y | enum | §3.5와 같은 값 공간·부여 조건 |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | stream별 duration. §3.4 |

### 4.3 Invariants

1. 같은 SourceAsset에 여러 MediaStream이 존재할 수 있다.
2. MediaStream identity를 camera role에서 파생하지 않는다.
3. camera role을 모르는 video도 identity를 유지하고 `role=UNKNOWN`으로 표현한다.
4. `AUDIO`는 camera role이 아니라 `media_type`이다.
5. 특정 stream decode 실패가 다른 stream 또는 SourceAsset 전체 실패를 의미하지 않는다.
6. codec/fps/resolution은 B07 evidence 최소 입력에 포함하지 않는다.

### 4.4 `role=UNKNOWN`과 `AUDIO`의 의미 (2026-09-08 확정)

- **`role=UNKNOWN`은 정상적인 video stream 상태다.** 「사용할 수 없다」는 뜻이 아니라 「카메라 역할을 모른다」는 뜻이다. 알려진 role의 stream이 없으면 `UNKNOWN` video stream도 분석·판독 후보로 쓸 수 있다.
- 실제 stream 선택 우선순위는 이 계약이 정하지 않는다 — `search`의 `stream_selector` 정책(Pending §9-5)과 `readout`의 도메인 판단이 소유한다. 계약은 값의 의미만 보장한다.
- **`SourceAsset.media_stream_refs[]`에는 `AUDIO` stream도 그대로 기록한다.** 분석용 사본을 만들 때 profile에 따라 제외할 수는 있으나, 원본 자산 사실에서 지우지 않는다.
- 분석 입력에 audio를 포함할지는 `search`가 profile로 선택하고 `recording`이 그 profile대로 변환한다(`contract-analysis-source-derived.md` §4.4). 미래 사건 유형을 이유로 계약이 audio 사용을 일괄 금지하지 않는다.

`media_type`·`role`의 최종 enum/nullability와 `stream_selector` 직렬화는 Pending이다(§9).

---

## 5. `FrameRef`

### 5.1 의미 및 Schema

`FrameRef`는 하나의 canonical frame image를 안정적으로 재참조하는 opaque identity다.

```json
{
  "contract": "FrameRef",
  "contract_version": "source-asset-media-stream/v1",
  "frame_ref": "fr_01JREC000000000000000001",
  "media_stream_ref": "ms_01JREC000000000000000001",
  "source_offset_sec": 312.48
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `frame_ref` | Y | string | canonical frame opaque identity |
| `media_stream_ref` | Y | string | frame이 속한 visual/video stream |
| `source_offset_sec` | Y | number ≥ 0 | MediaStream local position, 초(§5.4) |

### 5.2 확정 보장

1. `frame_ref`는 `fr_<opaque-id>`이며 Consumer는 문자열을 파싱하지 않는다.
2. 동일 MediaStream의 동일 canonical frame은 재조회 시 같은 FrameRef를 사용한다.
3. 서로 다른 MediaStream의 같은 시각 frame은 같은 FrameRef일 필요가 없다.
4. `read_frame(frame_ref)`로 실제 frame을 얻을 수 있다.
5. `media_stream_ref`와 source-relative offset을 계약 필드로 조회할 수 있다.
6. Timeline rebase 후에도 같은 FrameRef가 다른 frame을 가리키지 않는다.
7. `source_offset_sec`는 RecordingTimeline의 absolute/relative display time이 아니다.

canonical frame 선택·반올림 알고리즘은 recording Tech Spec이 소유하되, 동일성 보장을 깨뜨릴 수 없다.

### 5.3 Public capability — `resolve_frame` / `read_frame` (2026-09-08 확정)

**FrameRef의 최초 발급과 이미 발급된 frame의 조회는 서로 다른 capability다.** `read_frame(frame_ref)`만으로는 최초 FrameRef를 얻을 수 없다는 Consumer 지적(search·readout)을 수용해 둘을 분리한다.

```
resolve_frame(locator) -> FrameRef | failure
read_frame(frame_ref)  -> readable frame image | failure
```

`resolve_frame`은 두 좌표계를 **명시적 discriminator**로 구분한다.

```json
{
  "kind": "TIMELINE_POSITION",
  "timeline_ref": {
    "timeline_id": "tl_01JREC000000000000000001",
    "revision": 3
  },
  "at_sec": 312.48,
  "stream_selector": null
}
```

```json
{
  "kind": "STREAM_POSITION",
  "media_stream_ref": "ms_01JREC000000000000000001",
  "source_offset_sec": 312.48
}
```

규칙:

1. `TIMELINE_POSITION` — `search`가 Candidate thumbnail용 FrameRef를 얻을 때 쓴다. `timeline_id`와 `revision`이 모두 필수다.
2. `STREAM_POSITION` — `readout`이 `IncidentClip`의 canonical `AssetSpan`(`media_stream_ref` + `source_range`)에서 특정 frame을 얻을 때 쓴다. `media_stream_ref`와 `source_offset_sec`가 모두 필수다.
3. 두 locator 형태의 필드를 한 요청에 섞지 않는다.
4. recording은 **원본 MediaStream 기준**으로 canonical frame을 선택하고 FrameRef를 발급한다. `AnalysisSource`나 proxy를 기준으로 canonical FrameRef를 발급하지 않는다.
5. 동일 MediaStream의 동일 canonical frame은 동일 FrameRef다.
6. Consumer는 frame ID에 좌표를 인코딩하지 않는다.
7. `stream_selector`의 정확한 직렬화와 selector가 없을 때의 기본 stream 선택 정책은 Pending이다(§9-5).

runtime 반환 타입과 함수명은 구현에서 조정할 수 있다. 다만 ① 좌표에서 FrameRef를 발급받을 수 있다 ② FrameRef만으로 실제 frame을 획득할 수 있다 — 두 capability 의미는 계약 보장이다.

### 5.4 frame 위치 정밀도 (2026-09-08 확정)

`source_offset_sec`와 `resolve_frame`의 `at_sec`은 **decimal seconds**이며 최소 millisecond 수준 또는 원본 stream time base보다 정밀한 값을 보존한다.

- 두 자리 소수 등으로 임의 반올림하지 않는다.
- canonical frame 선택 후 **실제 선택된 frame의 source offset**을 `FrameRef.source_offset_sec`에 기록한다.
- 요청한 offset과 실제 선택된 frame의 offset은 다를 수 있다.
- 같은 canonical frame으로 정규화되는 요청은 같은 FrameRef를 반환한다.
- 정확한 seek/rounding 알고리즘은 recording Tech Spec이 소유한다.

---

## 6. Canonical `AssetFacts`

`AssetFacts`의 필드명과 의미는 이 절 한 곳이 소유한다. `contract-analysis-source-derived.md`를 포함한 다른 계약은 이 구조를 복제 정의하지 않고 이 절을 참조한다.

```json
{
  "contract": "AssetFacts",
  "contract_version": "source-asset-media-stream/v1",
  "asset_ref": {
    "kind": "source_asset",
    "ref": "sa_01JREC000000000000000001"
  },
  "asset_kind": "SOURCE_ASSET",
  "derived_role": null,
  "byte_size": 734003200,
  "availability": "AVAILABLE",
  "checked_at": "2026-09-08T00:35:00+09:00",
  "lineage": [
    {
      "kind": "external_source",
      "ref": "ext_01JREC000000000000000001"
    }
  ],
  "duration_sec": 1200.25,
  "timeline_ref": null,
  "timeline_range": null
}
```

| 필드 | 필수 | 타입 | 의미 |
| --- | --- | --- | --- |
| `asset_ref` | Y | `ContractRef` | 종류와 opaque ref를 함께 전달한다. `kind`는 §2.1 값 |
| `asset_kind` | Y | enum | `SOURCE_ASSET` \| `ANALYSIS_SOURCE` \| `INCIDENT_CLIP` \| `DERIVED_ASSET` (닫힌 목록) |
| `derived_role` | Y(키 항상 존재) | enum \| null | 파생 자산 역할(`contract-analysis-source-derived.md` §7.3). 해당 없거나 미확정이면 `null` |
| `byte_size` | Y(키 항상 존재) | integer ≥ 0 \| null | §3.4 |
| `availability` | Y | enum | §3.5 |
| `checked_at` | Y | offset-aware datetime | 존재·가용 여부를 판정한 시점 |
| `lineage[]` | Y | `ContractRef[]` | 원본까지 평탄화된 provenance(§6.3) |
| `duration_sec` | Y(키 항상 존재) | number ≥ 0 \| null | §3.4 |
| `timeline_ref` | Y(키 항상 존재) | `{timeline_id, revision}` \| null | `timeline_range` 좌표의 기준 Timeline과 revision(§6.4) |
| `timeline_range` | Y(키 항상 존재) | `{start_sec, end_sec}` \| null | coverage 판정에 쓸 범위, 초 단위(§6.4) |

### 6.1 Invariants

1. `asset_ref.kind`, `asset_kind` 및 실제 참조 대상의 의미가 §6.2 대응표에 따라 일치해야 한다. **문자열 동일성은 요구하지 않는다.**
2. `availability=AVAILABLE`이면 `byte_size`는 `null`일 수 없다.
3. `availability!=AVAILABLE`이면 측정하지 못한 `byte_size`를 0으로 꾸미지 않고 `null`을 허용한다.
4. `checked_at`은 모든 상태에서 필수이며 offset 없는 datetime을 금지한다.
5. `derived_role`과 lineage를 ref prefix에서 추론하지 않는다.
6. resolution/fps/codec/원본 무변형 checksum/번호판 가시성/화면 timestamp 표시 여부는 현재 evidence 최소 입력에서 제외한다.
7. `timeline_ref == null ⇔ timeline_range == null`(§6.4).
8. `lineage`를 모르는 상태를 정상적인 빈 배열로 표현하지 않는다(§6.3).

### 6.2 `asset_kind` ↔ `asset_ref.kind` 대응표 (2026-09-08 확정)

| `AssetFacts.asset_kind` | `AssetFacts.asset_ref.kind` |
| --- | --- |
| `SOURCE_ASSET` | `source_asset` |
| `ANALYSIS_SOURCE` | `analysis_source` |
| `INCIDENT_CLIP` | `incident_clip` |
| `DERIVED_ASSET` | `derived_asset` |

- 두 필드는 문자열 동일성이 아니라 이 표에 따른 **의미적 일치**를 요구한다. Consumer는 대소문자 보정이나 별칭 변환을 하지 않는다.
- `external_source` · `media_stream` · `frame` · `remote_copy`처럼 현재 `asset_kind`의 직접 대상이 아닌 ref kind에는 임의의 asset kind를 만들지 않는다. 이런 ref로 `lookup_asset_facts`를 호출하면 `INVALID_REF_KIND` 실패다(§6.5).

### 6.3 `lineage[]` 최소 구성 (2026-09-08 확정)

evidence는 recording을 직접 호출할 수 없으므로(B07 경계) `lineage`만으로 Source-derived 여부를 증명할 수 있어야 한다.

- 파생 자산(`ANALYSIS_SOURCE` · `INCIDENT_CLIP` · `DERIVED_ASSET`)의 `lineage[]`는 **원본까지 평탄화(flattened)**되며 최소 하나의 `source_asset` 또는 `external_source` ref를 포함한다.
- 필요하면 중간 `incident_clip` · `analysis_source` ref도 함께 담을 수 있다.
- 객체 자신의 `source_refs[]`는 **직접 부모**를, `AssetFacts.lineage[]`는 **원본까지의 전체 provenance**를 뜻한다. 둘은 다른 필드다.
- **lineage를 모르는 상태를 정상적인 빈 배열로 표현하지 않는다.** 판정할 수 없으면 `availability=UNKNOWN` 또는 lookup failure(§6.5)로 불확실성을 표면화한다.
- `SOURCE_ASSET` 자신의 `lineage`는 외부 원본이 있으면 그 `external_source`, 없으면 빈 배열이다 — 이것은 「모른다」가 아니라 「위가 없다」는 사실이다.

### 6.4 `timeline_ref` · `timeline_range` (2026-09-08 확정)

```
timeline_ref   : { timeline_id: string, revision: integer } | null
timeline_range : { start_sec: number, end_sec: number }     | null
```

```
timeline_ref == null  ⇔  timeline_range == null
timeline_ref != null  ⇔  timeline_range != null
```

- timeline 범위를 제공하면 그 좌표의 timeline ID와 **revision**도 반드시 함께 제공한다. revision 없이는 rebase 이후 coverage 비교 대상이 사라진다(B09와 같은 이유).
- recording 자산 계약의 범위 단위는 **초**다. `AnalysisScope`의 relative range(ms)와 단위가 다르며, 변환은 recording 경계에서 명시적으로 한다.
- rebase가 일어나도 기존 `AssetFacts`가 가리키는 revision을 바꾸지 않는다.
- coverage 판정 규칙과 허용 오차는 `evidence` policy가 소유한다. 이 계약은 좌표와 revision만 제공한다.

### 6.5 Public capability와 호출 경계

```
lookup_asset_facts(asset_ref: ContractRef) -> AssetFacts | failure
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
- 매 lookup 결과는 자체 `checked_at`을 갖는다. 호출 시점·재조회 정책은 `case` orchestration이 소유하며 이 스키마에 고정하지 않는다. `checked_at`의 stale 기준은 `evidence` policy가 소유한다.

### 6.6 실패 표현 (2026-09-08 확정)

`resolve_frame` · `read_frame` · `lookup_asset_facts`의 실패는 정상적인 `null`이나 `availability=UNAVAILABLE` 객체와 **구분되는 machine-readable failure**로 제공한다.

최소 공통 모양은 `SpanResolution.failure`와 같다 — **구조만** 같고 값 집합을 공유한다는 뜻이 아니다.

```
failure: {
  kind: string
  code: string
}
```

frame capability 최소 `code`:

```
FRAME_NOT_FOUND
STREAM_UNAVAILABLE
OUT_OF_RANGE
UNKNOWN_REF
TEMPORARY_FAILURE
```

`lookup_asset_facts` 최소 `code`:

```
UNKNOWN_REF
INVALID_REF_KIND
TEMPORARY_FAILURE
```

의미 구분:

- `UNKNOWN_REF` — 등록된 적 없는 ref이거나 잘못된 identity다.
- `INVALID_REF_KIND` — ref 자체는 유효하지만 `AssetFacts`의 대상이 아닌 kind다(§6.2).
- `availability=UNAVAILABLE` — 유효한 ref의 대상이 있었지만 지금 사용할 수 없다.

세 가지를 혼용하지 않는다. 「있었는데 사라짐」과 「애초에 잘못된 ref」는 `case`가 사용자에게 다르게 보여줘야 하는 서로 다른 상황이다.

readout이 dispatch 이후 frame 입력을 읽지 못하면 `PLATE_ABSTAINED`(입력이 있는 상태의 도메인 결과)와 구분되는 입력 계층 실패로 매핑한다 — `contract-readout-run.md`의 `failure`에 `kind: INPUT` · `code: INPUT_UNAVAILABLE`.

---

## 7. `CaseView.candidates[].thumb_ref`

`thumb_ref`의 자산 종류는 `FrameRef`다.

```
CandidateEvent.thumbnail_ref      -> FrameRef -> fr_<opaque-id>
CaseView.candidates[].thumb_ref   -> FrameRef -> fr_<opaque-id>
```

`fr_`는 예시 convention이며 Consumer는 문자열을 파싱하지 않는다.

실제 이미지는 다음 경계를 따른다.

```
web → recording 직접 호출 금지
case → recording frame capability → projection → web
```

URL/ref/endpoint/stream 중 어떤 방식으로 이미지를 전달할지는 Pending이다(§9-6).

---

## 8. 금지사항

- `asset_id == video stream id` 가정
- `AUDIO`를 camera role로 취급
- ref 문자열 parsing으로 자산 종류·role·position 추론
- `ContractRef.kind`의 대소문자 무시 비교·별칭 변환·Consumer별 변환표
- `frame_ref`에 `media_stream_ref@offset` 같은 위치 의미 인코딩
- 측정하지 못한 `byte_size`를 0으로 표기
- lineage를 모르는 상태를 빈 배열로 표기
- `timeline_range`만 주고 `timeline_ref`를 생략
- `AnalysisSource`·proxy 기준으로 canonical `FrameRef` 발급
- `web → recording`, `evidence → recording` 직접 호출
- 이 계약에서 `stream_selector` 또는 thumbnail 전달 방식을 임의 확정
- evidence policy가 소유하는 `availability → BLOCK/UNKNOWN` 판정 매핑을 이 계약에 고정

---

## 9. Pending (Consumer Review 후에도 열려 있는 항목)

이 항목들은 Consumer Review에서 **계약 확정을 막지 않는 것으로 확인된** 미결이다. 완성도를 위해 채우지 않는다.

1. `MediaStream.media_type`·`role`의 최종 enum 확장과 nullability
2. `SourceAsset.media_stream_refs=[]` 허용 조건
3. `AnalysisSource` profile의 정확한 값 목록과 보장 속성 — canonical 값 공간의 **소유는 recording**으로 확정됐고(`contract-analysis-source-derived.md` §4.4) 값 자체는 recording·search·readout 3자 합의 대상이다
4. `stream_selector`가 없을 때의 기본 stream 선택 정책
5. `stream_selector`의 정확한 serialization
6. thumbnail 이미지 전달 방식
7. frame seek/rounding 내부 알고리즘(Tech Spec 소유)

## 10. 버전과 호환성

- 문서 헤더와 모든 JSON payload는 `source-asset-media-stream/v1` 한 문자열을 쓴다. `1.0.0` 형식과 혼용하지 않는다.
- **Consumer는 알지 못하는 optional 필드를 무시한다.** 기존 의미를 바꾸지 않는 optional 필드 추가는 minor 변경으로 충분하다.
- 필수 필드 추가, 기존 타입 변경, nullable 축소, enum 값 제거는 **breaking change**이며 minor로 처리하지 않는다. Final 이후의 breaking change는 major version과 migration이 필요하다.
- 예시 opaque ID는 의미를 갖지 않는다. fixture의 ID를 바꾸면 연결된 모든 ref를 함께 바꾼다.

## 11. 한 줄 결정

> `recording`은 물리 파일 `SourceAsset`, 그 안의 `MediaStream`, canonical frame `FrameRef`를 서로 다른 opaque identity로 제공하고, 좌표에서 FrameRef를 발급하는 `resolve_frame`과 판정 시점·revision·평탄화 lineage가 포함된 `AssetFacts` 한 정의로 자산 사실을 노출한다.
