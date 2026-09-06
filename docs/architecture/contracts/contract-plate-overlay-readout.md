# Final Data Contract — PlateReadout / OverlayTimeReadout v1

**Status:** `Final — Accepted`

**Accepted:** `2026-09-06`

**수락 근거:** 전환 조건이 둘 다 해소됐다. ① `frame_ref` 형식 확정 — 정철원(`recording` Owner) CALL-4 회신으로 `fr_<opaque-id>` opaque 형식이 확정됐고 아래 §「`frame_ref` 형식」에 반영했다. ② Owner 수락 — 신유민 「`contract-plate-overlay-readout.md`의 기존 내용은 Canonical Contract v1 승격에 동의합니다」(CALL-6 회신, 2026-09-06). 근거는 `adr/adr-consistency-2026-09.md` §6 R-4·R-5

**Architecture Contract:** v4 §5-1 ⑦

**Contract:** `PlateReadout` / `OverlayTimeReadout`

**Contract Version:** `plate-readout/v1` · `overlay-time-readout/v1`

**Related ADR:** `adr/adr-plate-overlay-readout.md`

**Contract Lead:** 신유민

**Runtime Producer:** `readout`

**Consumer:** `case` — 유소연 (Direct) → `evidence` — 김준영 (projection) · `eval` — 김대원

> Direct Consumer는 `case`다(v4 §5-1 ⑦ `case → evidence`). `evidence`는 다른 모듈을 직접 호출하지 않고 입력 JSON으로 받는다 — `contract-evidence-record-needs.md` §「책임 경계」와 v4 §2 원칙 6.

**기준 문서:** Module Architecture v4, Readout/Web Architecture Input Memo, Consumer Review 반영본

---

# 1. 목적과 범위

이 Contract는 `readout` 모듈이 생산하는 번호판 판독 결과와 화면 Timestamp 판독 결과의 의미를 정의한다.

`readout`은 **관찰값**을 생산한다. 번호판이 최종적으로 맞는지, 발생 시각이 최종적으로 무엇인지는 `evidence`가 확정한다.

## 포함하는 것

- `PlateReadout`
- `OverlayTimeReadout`
- `best_frame`
- `frame_results`
- `frame_ref`
- `crop_ref`
- `target_association`
- `consensus`
- `abstain`
- overlay timestamp OCR sample
- overlay timestamp 검증 결과

## 포함하지 않는 것

- 최종 번호판 확정
- 최종 발생 시각 확정
- 신고 가능 여부 판단
- 신고문 / 신고 Package 생성
- web UI 문구 / 레이아웃
- OCR detector / tracker / threshold 세부 구현
- 신고 Evidence로 번호판이 충분히 보이는지에 대한 최종 판정

---

# 2. Contract Inventory

| # | Contract | Producer | Consumer | 역할 | 이번 문서에서 작성 여부 |
| --- | --- | --- | --- | --- | --- |
| ⑥-A | `PlateReadout` | `readout` | `evidence`, `eval` | 번호판 관찰값, 대상 차량 association 근거, 프레임별 OCR, consensus, abstain 근거 전달 | 작성 |
| ⑥-B | `OverlayTimeReadout` | `readout` | `evidence`, `eval` | 화면 Timestamp OCR 관찰값과 검증 결과 전달 | 작성 |

---

# 3. 공통 원칙

1. `readout`은 관찰하고, `evidence`가 확정한다.
2. OCR 근거는 항상 Source-derived `Incident Clip` 또는 그에 대응하는 Source-derived frame/crop이어야 한다.
3. 사후 Timestamp가 삽입된 `Report Video`를 다시 OCR 근거로 사용하지 않는다.
4. `PlateReadout.abstained = true`는 Case/Search 전체 실패가 아니라 번호판 확정 보류 상태다.
5. 번호판 OCR confidence는 보조 신호이며 단독 확정 기준이 아니다.
6. `target_hint`는 optional이다. 단, 최종 `PlateReadout`에는 readout이 실제로 어떤 대상 차량을 association했는지와 그 근거가 남아야 한다.
7. 초기 v1에서는 `evidence`와 `eval` 모두 충분한 관찰 정보를 받을 수 있게 한다. 이후 payload/storage/운영 비용을 측정한 뒤 consumer별 projection 또는 요약 범위를 조정할 수 있다.

## `frame_ref` 형식 (2026-09-06 확정)

`frame_ref`는 **`fr_<opaque-id>`** 형태의 opaque identifier다. 형식과 발급은 `recording`이 소유한다(정철원, CALL-4 회신).

**위치 정보를 ID에 인코딩하지 않는다.** `fr_<media_stream_id>@<offset_ms>` 같은 형태는 정식 형식으로 쓰지 않으며, `media_stream_ref`와 source offset은 `recording`의 `FrameRef` 계약 필드로 별도 추적한다. `readout`은 ref를 만들지 않고 받은 것을 그대로 보존한다.

같은 규칙이 `crop_ref`·`incident_clip_ref`·`span_ref`에도 적용된다 — 전부 opaque이며 `recording` 계약(`contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`, 정철원 작성 예정)이 형식을 소유한다.

## `ReadoutRun`과의 연결

`PlateReadout`·`OverlayTimeReadout`은 **자신을 생성한 실행의 `run_id`를 보존한다.**

v4 §4-모듈3 ③이 `read_plate -> ReadoutRun, PlateReadout`으로 반환값을 둘로 명시한다. 이 계약은 **관찰 결과**를 담고, 실행의 성공/부분성공/실패와 실패 단계는 `contract-readout-run.md`가 담는다. 실행이 완전히 실패하면 이 계약의 결과는 생성되지 않고 `ReadoutRun`만 남는다.

결과 → run 역추적은 보장하고, 그 반대는 보장하지 않는다.

---

# 4. PlateReadout 의미 정의

`PlateReadout`은 선택된 사건 구간의 `Incident Clip` 또는 그에 대응하는 frame access에서 번호판을 관찰한 결과다.

핵심 원칙:

- single-frame confidence만으로 자동 확정하지 않는다.
- 여러 프레임의 OCR 결과와 근거 프레임을 보존한다.
- 애매하면 `abstain`한다.
- 사용자가 수정하기 전 AI 관찰값은 prior/provenance로 보존 가능해야 한다.
- OCR 문자열뿐 아니라 대상 차량 association 결과도 함께 전달한다.

## 필수 의미

| 항목 | 의미 |
| --- | --- |
| `readout_id` | readout 결과 식별자 |
| `case_id` | 연결된 case |
| `candidate_id` | 사용자가 선택했거나 case가 지정한 사건 후보 |
| `input_ref` | OCR 근거가 된 `incident_clip_ref`, `span_ref` |
| `target_association` | 실제로 어떤 차량/영역을 대상으로 번호판을 읽었는지와 근거 |
| `observation` | 번호판 관찰값. 확정값이 아님 |
| `consensus` | 여러 프레임 OCR을 종합한 결과 |
| `abstained` | 번호판 확정을 보류했는지 |
| `abstain_reason` | 보류 사유 |
| `best_frame` | 대표 근거 프레임/crop |
| `frame_results` | 프레임별 OCR 관찰 결과 |

## 예시 JSON

```json
{
  "readout_id": "readout_plate_001",
  "case_id": "case_001",
  "candidate_id": "candidate_001",
  "input_ref": {
    "incident_clip_ref": "incident_clip_001",
    "span_ref": "span_001",
    "source_profile": "readout-native"
  },
  "target_association": {
    "status": "ASSOCIATED",
    "target_hint_used": true,
    "track_ref": "track_007",
    "association_method": "TARGET_HINT_WITH_FALLBACK",
    "associated_region": {
      "frame_ref": "fr_9a1c0e",
      "bbox_xywh": [812, 420, 184, 72]
    },
    "evidence": [
      {
        "kind": "SPATIAL_PROXIMITY",
        "detail": "candidate target region overlaps selected track"
      },
      {
        "kind": "MULTI_FRAME_CONTINUITY",
        "detail": "similar plate crop appears across sampled frames"
      }
    ]
  },
  "observation": {
    "kind": "PLATE",
    "status": "NEEDS_REVIEW",
    "value": "12가34?6",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "consensus": {
    "text": "12가34?6",
    "disagree_positions": [5],
    "method": "MULTI_FRAME"
  },
  "abstained": true,
  "abstain_reason": "FRAME_DISAGREEMENT",
  "best_frame": {
    "frame_ref": "fr_9a1c0e",
    "crop_ref": "crop_001",
    "quality": {
      "plate_px_height": 42,
      "sharpness": 0.81
    }
  },
  "frame_results": [
    {
      "frame_ref": "fr_9a1c0e",
      "crop_ref": "crop_001",
      "text": "12가3456",
      "confidence": 0.72
    },
    {
      "frame_ref": "fr_9a1c11",
      "crop_ref": "crop_004",
      "text": "12가3466",
      "confidence": 0.69
    }
  ]
}
```

---

# 5. PlateReadout 상태와 실패 처리

## `observation.status`

`PlateReadout.observation.status`는 공용 `Observation<T> v1`의 status 의미를 그대로 따른다. 이 Contract에서 주로 사용하는 값은 `OK / NEEDS_REVIEW / UNKNOWN / ERROR`이며, `NOT_APPLICABLE`은 공용 계약의 의미가 적용되는 경우 사용할 수 있다. `OBSERVED / FAILED / VERIFIED` 같은 readout 전용 값을 공용 `Observation.status`에 새로 추가하지 않는다.

| 상태 | 의미 |
| --- | --- |
| `OK` | 번호판 관찰값이 있고 readout 기준으로 일관성이 충분함. 최종 확정은 아님 |
| `NEEDS_REVIEW` | 관찰값은 있으나 사용자 또는 evidence 검토가 필요함 |
| `UNKNOWN` | 번호판 값을 알 수 없음 |
| `ERROR` | readout 관찰 작업 자체의 처리가 실패함 |

## `abstained`

`abstained = true`는 `Observation.status = NEEDS_REVIEW`와 함께 사용한다. 별도 `ABSTAIN` status는 신설하지 않는다.

이유:

- 공용 `Observation<T>` enum 확장을 최소화한다.
- 번호판 판독 특유의 보류 상태를 명시적으로 표현할 수 있다.
- `evidence`는 이를 번호판 확인/보정이 필요한 `EvidenceNeeds`로 연결할 수 있다.

## `target_association.status`

| 상태 | 의미 |
| --- | --- |
| `ASSOCIATED` | 대상 차량/영역을 association했고 그 근거가 있음 |
| `LOW_CONFIDENCE` | association은 했지만 근거가 약함 |
| `AMBIGUOUS` | 여러 대상 후보가 있어 하나로 고르기 어려움 |
| `FAILED` | 대상 association 실패 |
| `NOT_PROVIDED` | target hint가 없었고 fallback association 근거도 부족함 |

OCR 문자열이 정확해 보여도 `target_association`이 `LOW_CONFIDENCE`, `AMBIGUOUS`, `FAILED`이면 `evidence`는 최종 번호판 확정을 보류할 수 있다.

---

# 6. OverlayTimeReadout 의미 정의

`OverlayTimeReadout`은 선택된 사건의 Source-derived `Incident Clip`에서 화면에 찍힌 Timestamp를 OCR하고 검증한 결과다.

핵심 원칙:

- v4 정책은 Verified Overlay Timestamp를 우선한다.
- 초기 v1에서는 **선택된 사건마다 Overlay OCR을 실행하는 A안**으로 시작한다.
- Overlay 존재 탐지 후 조건부 OCR(C안)은 cost/latency 측정 후 적용할 수 있는 최적화안으로 남긴다.
- C안으로 전환하려면 presence detection의 recall / false negative를 별도 benchmark해야 한다.
- 최종 occurred_at 선택은 `evidence` / `TimeResolution` 책임이다.

## 필수 의미

| 항목 | 의미 |
| --- | --- |
| `readout_id` | overlay readout 결과 식별자 |
| `case_id` | 연결된 case |
| `candidate_id` | 사용자가 선택했거나 case가 지정한 사건 후보 |
| `input_ref` | OCR 근거가 된 Source-derived input |
| `observation` | 화면 timestamp 관찰값. 최종 발생 시각 확정값이 아님 |
| `validation` | readout이 수행한 형식/시간흐름/구간 정합성 검증 |
| `samples` | 검증에 사용한 sample별 OCR 결과 |

## 예시 JSON

```json
{
  "readout_id": "readout_time_001",
  "case_id": "case_001",
  "candidate_id": "candidate_001",
  "input_ref": {
    "incident_clip_ref": "incident_clip_001",
    "span_ref": "span_001",
    "source_profile": "readout-native"
  },
  "observation": {
    "kind": "OVERLAY_TIMESTAMP",
    "status": "OK",
    "value": "2026-09-02T18:31:12+09:00",
    "source": "VIDEO_OVERLAY_OCR",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "validation": {
    "format_ok": true,
    "monotonic_ok": true,
    "duration_match_ok": true,
    "sample_count": 5
  },
  "samples": [
    {
      "frame_ref": "fr_3b77d2",
      "offset_sec": 2.0,
      "raw_text": "2026-09-02 18:31:12",
      "parsed_at": "2026-09-02T18:31:12+09:00"
    },
    {
      "frame_ref": "fr_3b77f0",
      "offset_sec": 3.0,
      "raw_text": "2026-09-02 18:31:13",
      "parsed_at": "2026-09-02T18:31:13+09:00"
    }
  ]
}
```

---

# 7. OverlayTimeReadout Validation 필드 정의

| 필드 | 의미 | Consumer 해석 |
| --- | --- | --- |
| `format_ok` | OCR 결과가 프로젝트가 지원하는 날짜/시간 형식으로 parse 가능한지 | false이면 `evidence`는 verified overlay로 쓰지 않거나 review/conflict 후보로 둔다 |
| `monotonic_ok` | sample들의 시간이 frame offset 증가에 따라 역행하지 않는지 | false이면 overlay OCR 오인식 또는 영상/시각 불일치 가능성이 있음 |
| `duration_match_ok` | sample 간 timestamp 차이가 sample 간 `offset_sec` 차이와 허용 오차 내에서 맞는지 | false이면 overlay timestamp를 강한 근거로 쓰기 어렵다 |
| `sample_count` | 검증에 사용한 OCR sample 수 | 너무 적으면 검증 신뢰도가 낮을 수 있다 |

`samples[]`는 sample별 OCR 원문과 parse 결과를 보존한다. eval은 이를 통해 overlay OCR 실패 원인이 형식 문제인지, 특정 sample 오인식인지, 시간 흐름 불일치인지 진단할 수 있다.

---

# 8. 접합부 / Data Contract 영향

| 검토자 | 방향 | 제공하는 정보 | 제약 | Final 반영 |
| --- | --- | --- | --- | --- |
| 김준영 / `evidence` | `readout` → `evidence` | `PlateReadout`, `OverlayTimeReadout`, observation status, target association, abstain 근거, overlay 검증 결과, frame_results | `readout`은 번호판과 발생 시각을 최종 확정하지 않음 | 초기 v1에서는 충분한 관찰 정보를 제공하고, evidence가 확정/보류/needs 판단 |
| 김대원 / `eval` | `readout` → `eval` | consensus, best_frame, abstain 여부, target association, overlay validation, 필요 시 frame_results/samples | eval은 최종값 하나보다 실패/불확실성 진단 정보가 필요할 수 있음 | 기본 평가는 consensus + best_frame 중심, 상세 진단은 frame_results/samples 사용 |

---

# 9. Consumer별 제공 범위

초기 v1에서는 Producer가 충분한 관찰 정보를 생산하고 보존한다. Consumer별 projection은 이후 비용 측정 후 조정한다.

| Consumer | 기본 소비 | 상세/진단용 |
| --- | --- | --- |
| `evidence` | `observation`, `target_association`, `consensus`, `abstained`, `abstain_reason`, `best_frame`, `validation` | `frame_results`, `samples` |
| `eval` | `consensus`, `best_frame`, `abstained`, `target_association`, `validation` | `frame_results`, `samples` |

`eval`의 번호판 평가는 우선 `best_frame`, `consensus`, `abstained`를 중심으로 수행할 수 있다. `frame_results[]` 전체는 OCR 실패 원인 분석, CER 진단, frame-level debugging이 필요할 때 사용한다.

---

# 10. 실패 / UNKNOWN / ABSTAIN 처리

readout 실패는 하나로 뭉치지 않는다. 실패 종류에 따라 재실행 범위와 사용자 표현이 달라지기 때문이다.

## 구분해야 하는 상태

- 대상 차량 association 실패
- 대상 차량 association ambiguous / low confidence
- 번호판 detection 실패
- OCR recognition 실패
- frame 간 consensus 불일치
- `abstain`
- overlay timestamp 없음
- overlay OCR 불확실
- overlay validation 실패
- frame access 실패

## 원칙

- Plate `abstain`은 Case 전체 실패가 아니다.
- Plate `abstain` 때문에 긴 `search`를 다시 실행하지 않는다.
- Overlay OCR 불확실은 기존 file time candidate를 버리는 이유가 아니다.
- Overlay의 `NOT_PRESENT`, `OCR_FAILED`, `VALIDATION_FAILED`는 공용 `Observation.status` enum이 아니라 readout 도메인의 reason/validation 결과다. 관찰 자체의 공용 상태는 `OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE`를 따른다.
- 여러 시간 source 간 timestamp conflict 및 최종 source 선택은 `evidence / TimeResolution`에서 별도로 처리한다.
- frame access 실패가 `recording` 문제인지 `readout` 내부 처리 문제인지 구분 가능한 상태가 필요하다.
- 사용자가 번호판을 직접 수정하더라도 AI 관찰값은 prior/provenance로 보존한다.

---

# 11. 확정된 A/B/C 결정

## 11-1. `abstain` 표현 방식

**선택:** A. `Observation.status = NEEDS_REVIEW` + `abstained = true`

**이유:** 공용 Observation enum 확장을 최소화하면서 번호판 판독의 확정 보류 상태를 명확히 표현할 수 있다.

## 11-2. `frame_results` 제공 범위

**선택:** C 변형. 초기 v1에서는 `evidence`와 `eval` 모두 충분한 관찰 정보를 받을 수 있게 하고, consumer별 기본 소비 범위를 문서화한다.

**이유:** 김준영/evidence 관점에서는 초기부터 충분한 관찰 정보가 필요하다. 김대원/eval 관점에서는 기본 평가는 `best_frame + consensus` 중심이면 충분할 수 있으므로, 전체 `frame_results[]`는 진단/디버그용으로 둔다.

## 11-3. `target_hint` 필수 여부

**선택:** B. optional + fallback association

**이유:** `search`가 항상 stable track을 제공한다고 가정하면 `readout`이 `search` 내부 구현에 묶인다. 다만 Final `PlateReadout`에는 실제 association 대상과 근거를 남겨 `evidence`가 잘못된 차량 판독 위험을 검토할 수 있어야 한다.

## 11-4. `OverlayTimeReadout` 실행 방식

**선택:** A. 선택된 사건마다 Overlay OCR 실행

**이유:** v4 정책은 Verified Overlay Timestamp 우선이다. 초기에는 Overlay OCR을 기본 실행하여 evidence가 강한 시간 근거를 확보할 수 있게 한다.

**보류한 최적화:** C. overlay 존재 탐지 후 조건부 OCR

cost/latency가 실제로 문제가 될 경우 적용을 검토한다. 단, presence detection이 실제 overlay를 놓치면 verified overlay 근거 자체를 잃게 되므로 recall / false negative benchmark가 선행되어야 한다.

## 11-5. disagreement 표현

**선택:** C. 사람이 읽을 수 있는 masking text와 `disagree_positions[]` 둘 다 제공

**이유:** evidence는 불확실 문자를 검토해야 하고, eval은 OCR 오류 위치를 진단해야 한다.

---

# 12. Eval 반영 사항

`eval`은 abstain을 단순 정답 회피로만 합산하지 않는다. 최소 다음 지표를 분리해 볼 수 있어야 한다.

- Exact Plate Accuracy
- Wrong Accept Rate
- Abstention Rate
- Abstention Recall
- Detection / Association / CER diagnostics
- Overlay validation success/failure breakdown

abstain 비중이 낮은 초기 단계에서는 정답 회피 관점으로도 참고할 수 있지만, 지표 정의에서는 별도 metric으로 분리해 성능 해석이 뭉개지지 않게 한다.

---

# 13. Data Contract 이후 Tech Spec으로 넘길 것

- 최종 OCR 엔진 / detector / tracker 조합
- sampling FPS / sampling interval
- best frame scoring weight
- consensus threshold
- OCR confidence threshold
- crop 전처리 방식
- overlay timestamp 영역 탐지 방식
- PaddleOCR / detector 실행 환경
- Overlay presence detection 도입 여부와 benchmark 기준

---

# 14. Final Contract 통과 기준

- `readout`이 소유하면 안 되는 확정값을 소유하지 않는다.
- `readout` 구현이 `search` 내부 track 구조를 반드시 알아야 하는 형태가 아니다.
- 최종 `PlateReadout`에 실제 association 대상과 근거가 표현된다.
- Plate abstain / overlay uncertainty가 긴 search 재실행을 유발하지 않는다.
- Overlay OCR은 Source-derived Incident Clip 기준으로만 수행된다.
- `evidence`가 번호판 확인/보정 필요와 TimeResolution 판단을 수행할 수 있는 충분한 관찰 정보가 제공된다.
- `eval`이 best_frame/consensus 중심 평가와 상세 진단을 분리해서 수행할 수 있다.
- validation 필드의 의미가 Consumer가 이해할 수 있게 명시되어 있다.

---

# 관련 문서

- [ADR: PlateReadout / OverlayTimeReadout Contract Decision](https://app.notion.com/p/ADR-PlateReadout-OverlayTimeReadout-Contract-Decision-3d17ae78fc6a8055b329dfa8a77619e0?pvs=21)