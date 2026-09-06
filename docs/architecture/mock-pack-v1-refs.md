# Mock Pack v1 — ref 규약

> ## ⚠ 이 문서는 계약이 아니다
>
> `recording` 자산 계층의 Data Contract 2건(`SourceAsset`·`MediaStream`·`FrameRef` / `AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset`)은 **정철원(`recording` Owner)이 작성 중**이다. 이 문서는 그 계약이 나오기 전에 **목데이터를 굴리기 위한 임시 규약**이며 다음을 지킨다.
>
> 1. **`contracts/` 안에 두지 않는다.** 계약의 canonical 위치는 `architecture/contracts/`이고, 그 폴더에는 계약만 있어야 한다.
> 2. **필드를 정의하지 않는다.** ref 문자열 형식만 다룬다. 어떤 타입에 어떤 필드가 있는지는 정철원 계약이 정한다.
> 3. **정철원 계약이 나오면 이 문서는 폐기한다.** 그때 이 파일을 지우고 v4 §5-3의 포인터를 계약으로 바꾼다.
>
> 목데이터를 만들다가 **ref가 아니라 필드가 필요해지면 채우지 말고 PM(김준영)에게 말한다.** 그건 계약이 필요하다는 신호다.

**Status:** 임시 · 2026-09-06
**Owner:** 김준영 (PM — 통합 보조 자료)
**폐기 조건:** `contracts/contract-source-asset-media-stream.md` · `contracts/contract-analysis-source-derived.md` 등재

---

## 1. 왜 이 문서로 충분한가

**다른 계약들은 recording 자산을 opaque `*_ref` 문자열로만 참조한다.** 필드를 파고드는 계약이 없다.

| ref | 참조하는 계약 |
| --- | --- |
| `source_asset_ref` | `contract-recording-timeline-asset-span.md` |
| `media_stream_ref` | `contract-plate-overlay-readout.md` · `contract-recording-timeline-asset-span.md` |
| `frame_ref` · `crop_ref` · `incident_clip_ref` · `span_ref` · `source_profile` | `contract-plate-overlay-readout.md` |
| `derived_asset_ref` | `contract-requirement-report-package.md` |

그리고 소비자가 실제로 읽는 recording 표면은 **이미 Final이다** — `contract-recording-timeline-asset-span.md`가 `RecordingTimeline` · `AssetSpan` · **`SpanResolution`**(`resolve_span` 응답) · `TimeSourceCandidate` · `MissingRange` · File Boundary/Overlap 규칙을 갖고 있다.

즉 목데이터에 필요한 것은 셋이고 셋 다 있다.

1. **ref 형식** → 이 문서 (형식 자체는 정철원 확정)
2. **`resolve_span` 응답** → `SpanResolution` (Final)
3. **timeline / span** → `RecordingTimeline` · `AssetSpan` (Final)

빠진 것은 `SourceAsset`/`MediaStream` 등의 **내부 필드**이고, 그건 `recording` 모듈이 자기 안에서 쓰는 값이라 목데이터 담당자가 손댈 일이 없다.

## 2. ref 형식 — 정철원 확정 (2026-09-06)

**형식 자체는 임시가 아니다.** `recording` Owner가 CALL-4 회신으로 확정했고, 계약이 나와도 이 형식은 그대로다(`contracts/adr/adr-consistency-2026-09.md` §6 R-5).

```
source_asset_ref    = "sa_<opaque-id>"
media_stream_ref    = "ms_<opaque-id>"
frame_ref           = "fr_<opaque-id>"
analysis_source_ref = "as_<opaque-id>"
remote_copy_ref     = "rc_<opaque-id>"
incident_clip_ref   = "clip_<opaque-id>"
derived_asset_ref   = "da_<opaque-id>"
```

**위치나 role을 ID에 인코딩하지 않는다.** 아래는 **쓰지 않는다** — PM이 잠정안으로 제안했다가 `recording` Owner가 기각한 형태다.

```
✗ ms_<source_asset_id>_<role>        Stream identity와 role을 결합한다
✗ fr_<media_stream_id>@<offset_ms>   위치를 ID에 넣는다
✗ "frame:a09@178.6"                  같은 이유
```

- `source_asset_ref`와 `role`은 `MediaStream`의 **별도 필드**로 보존한다
- frame 위치는 `FrameRef`의 **`media_stream_ref` + source offset**으로 추적한다
- video/audio stream 종류와 `FRONT`/`REAR`/`UNKNOWN` camera role은 **분리**한다

## 3. 목데이터용 id 생성 규칙 (이 부분이 임시다)

`<opaque-id>`는 계약상 **불투명**하므로 목에서는 아무 값이나 써도 된다. 다만 사람이 눈으로 추적할 수 있게 아래를 권장한다.

```
sa_0001, sa_0002 …        파일 순서
ms_0001f, ms_0001r        sa_0001의 전방/후방 — 접미어는 사람 눈용이고 의미 없음
fr_a1b2c3                 6자리 hex
clip_0001, da_0001
```

**접미어에 의미를 부여하지 않는다.** 목 코드가 `ms_` 뒤 문자열을 파싱하면 계약 위반이고, 정철원 계약이 들어오는 순간 깨진다. 파싱이 필요하면 그건 필드로 받아야 할 값이다(§ 상단 경고 3번).

## 4. 이 문서가 다루지 않는 것

- 각 타입의 필드 목록 — **정철원 계약**
- upload 방식 · proxy profile 값 · retention 일수 · provider별 `RemoteCopy` delete 방식 — v4에서도 **미결**이며 계약에서도 임의 확정하지 않기로 했다(v4 §5-3)
- `CaseView.candidates[].thumb_ref`가 어느 자산의 ref인지(`fr_` / `da_`) — 계약 2건이 나온 뒤 확정한다
