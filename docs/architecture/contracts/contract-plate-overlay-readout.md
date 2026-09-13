# Final Data Contract — PlateReadout / OverlayTimeReadout v1

**Status:** `Final — Accepted`

> **B03·B05 종결 (2026-09-07).** 판독 결과 최상위에 필수 `run_ref: ContractRef{kind:"readout_run"}`를 두고(§3·§4·§6), 사용량 연결은 `UsageRecord.run_ref`가 authoritative다(`contract-usage-record.md`). 결정 근거·기각안은 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.3·§4.4. 같은 회차에 예시 `observation` 블록을 `Observation<T> v1`에 맞췄다(R-9-5~7, Producer-side 정합).

**Accepted:** `2026-09-06` (v1) · `2026-09-07` (v1.1 — `run_ref` 필수 추가, 신유민) · `2026-09-08` (v1.2 — `input_ref.span_ref` 삭제, 신유민 확인 · Decider 정철원)

**수락 근거:** 전환 조건이 둘 다 해소됐다. ① `frame_ref` 형식 확정 — 정철원(`recording` Owner) CALL-4 회신으로 `fr_<opaque-id>` opaque 형식이 확정됐고 아래 §「`frame_ref` 형식」에 반영했다. ② Owner 수락 — 신유민 「`contract-plate-overlay-readout.md`의 기존 내용은 Canonical Contract v1 승격에 동의합니다」(CALL-6 회신, 2026-09-06). 근거는 `adr/adr-consistency-2026-09.md` §6 R-4·R-5

**Architecture Contract:** v4 §5-1 ⑦

**Contract:** `PlateReadout` / `OverlayTimeReadout`

**Contract Version:** `plate-readout/v1.2` · `overlay-time-readout/v1.2`

**Related ADR:** `adr/adr-plate-overlay-readout.md` · `adr/adr-data-contract-call-closure-2026-09-07.md` §4.3 (v1.1 근거) · `adr/adr-data-contract-call-closure-2026-09-08.md` §4.9 (v1.2 근거)

**Contract Lead:** 신유민

**Runtime Producer:** `readout`

**Consumer:** `case` — 유소연 (Direct) → `evidence` — 김준영 (projection) · `eval` — 김대원

> Direct Consumer는 `case`다(v4 §5-1 ⑦ `case → evidence`). `evidence`는 다른 모듈을 직접 호출하지 않고 입력 JSON으로 받는다 — `contract-evidence-record-needs.md` §「책임 경계」와 v4 §2 원칙 6.

**기준 문서:** Module Architecture v4, Readout/Web Architecture Input Memo, Consumer Review 반영본

> **`input_ref.span_ref` 삭제 (2026-09-08 · Decider 정철원(`recording`, `AssetSpan` 소유) · 확인 신유민(`readout`)·유소연(`case`)·김준영(`evidence`)).** canonical `AssetSpan`에는 독립 identity가 없고 앞으로도 추가하지 않는다는 결정에 따라 **`PlateReadout.input_ref.span_ref`와 `OverlayTimeReadout.input_ref.span_ref`를 삭제**한다. `span_ref`라는 이름으로 `IncidentClip`이나 `SpanResolution`을 가리키는 **의미 재정의도 하지 않는다.** 예시가 쓰던 `"span_001"`은 recording이 발급하지 않는 ID였다. clip 생성 이후 사건 구간의 canonical reference는 `{kind:"incident_clip", ref:...}`이며, 「어느 구간을 읽었나」는 `incident_clip_ref` 하나로 알 수 있다 — timeline·요청 범위·사용한 span 값이 모두 `IncidentClip.source_provenance`에 있다(`contract-analysis-source-derived.md` §6.2·§6.3). 필드 삭제이므로 **`plate-readout/v1.1 → v1.2`** · **`overlay-time-readout/v1.1 → v1.2`**. 근거·기각안 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.9.

> **의미 명시 — 버전 변경 없음 (2026-09-10 · Decider 신유민).** §3에 두 절을 추가했다 — **`crop_ref` identity**(`(frame_ref, bbox, 추출 파라미터)`, opaque identity이고 조회 handle이 아니다 · 발급 주체는 `readout`)와 **`input_ref.source_profile` 값 공간 등재**(`readout-native` · `readout-native-hires`, 열린 목록). 둘 다 **기존 필드의 의미를 명시한 것이라 `plate-readout/v1.2` · `overlay-time-readout/v1.2`를 유지한다**(스키마 변경 없음). 요청 김대원(이슈 #30 B-2) · 답변 이슈 #31 A-3 · Producer 경계 확인 정철원(이슈 #40 C절) · Consumer 확인 김준영(PR #27).

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
| A | `PlateReadout` | `readout` | `case` 경유 `evidence` · `eval` | 번호판 관찰값, 대상 차량 association 근거, 프레임별 OCR, consensus, abstain 근거 전달 | 작성 |
| B | `OverlayTimeReadout` | `readout` | `case` 경유 `evidence` · `eval` | 화면 Timestamp OCR 관찰값과 검증 결과 전달 | 작성 |

---

# 3. 공통 원칙

1. `readout`은 관찰하고, `evidence`가 확정한다.
2. OCR 근거는 항상 Source-derived `Incident Clip` 또는 그에 대응하는 Source-derived frame/crop이어야 한다.
3. 사후 Timestamp가 삽입된 `Report Video`를 다시 OCR 근거로 사용하지 않는다.
4. `PlateReadout.abstained = true`는 Case/Search 전체 실패가 아니라 번호판 확정 보류 상태다.
5. 번호판 OCR confidence는 보조 신호이며 단독 확정 기준이 아니다.
6. `target_hint`는 optional이다. 단, 최종 `PlateReadout`에는 readout이 실제로 어떤 대상 차량을 association했는지와 그 근거가 남아야 한다.
7. 초기 v1에서는 `evidence`와 `eval` 모두 충분한 관찰 정보를 받을 수 있게 한다. 이후 payload/storage/운영 비용을 측정한 뒤 consumer별 projection 또는 요약 범위를 조정할 수 있다.

## `frame_ref` 형식 — 현재 작업 규약 참조

ref 형식·위치/role 분리 방향은 `../module-architecture.md` §5-3만 참조한다. **정식 `FrameRef` 필드 계약은 `contract-source-asset-media-stream.md` §5가 소유한다**(`source-asset-media-stream/v1`, 2026-09-08 Consumer Review 종결) — 보장 의미 6건(opaque identity · 동일 stream 동일 canonical frame = 동일 ref · 내부 파싱 금지 · `read_frame` 획득 · `media_stream_ref`+source offset 조회 · rebase 불변)이 §5.2에 있고, 좌표에서 `FrameRef`를 발급받는 `resolve_frame`은 §5.3, offset 정밀도 보장은 §5.4, 조회 실패의 machine-readable failure는 §6.6이다. 같은 6건은 `contract-recording-timeline-asset-span.md` §12에도 남아 있다. `readout`은 ref를 자체 발급하거나 ID 내부를 해석하지 않고 전달받은 근거 ref를 보존한다.

## `crop_ref` identity — 확정 (2026-09-10 · Decider 신유민 · 요청 김대원(`eval`, 이슈 [#30](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/30) B-2) · **확인 완료** 정철원(`recording`, 이슈 [#40](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/40) C절) · 김준영(`evidence`, PR #27 리뷰))

**적용 대상은 `PlateReadout.frame_results[].crop_ref`다** — `OverlayTimeReadout`에는 `crop_ref`가 없다. 이 절을 §3(공통 원칙)에 두는 것은 아래 `source_profile`과 같은 「입력을 무엇으로 식별하는가」 계열이기 때문이고, 규칙 자체는 plate 한정이다.

지금까지 이 계약은 `crop_ref`를 필드 목록과 예시에만 두고 identity를 정의하지 않았다. Mock Pack v3의 `plate_reread_001`에서 **같은 `crop_ref`가 두 판독에서 서로 다른 값을 낸** 상태가 만들어져(원 판독 `17나2804` / 재판독 `17나2867`) `eval`이 「재판독이 무엇을 바꿔서 맞혔는가」를 귀속할 수 없었다. 아래를 확정한다.

- **`crop_ref`의 identity는 `(frame_ref, bbox, 추출 파라미터)`다.** 추출 파라미터에는 그 판독의 `input_ref.source_profile`이 포함된다. 셋 중 하나라도 다르면 **다른 `crop_ref`**다.
- **같은 `crop_ref`가 서로 다른 픽셀을 가리키는 일은 없다.** id를 재사용하지 않는다 — 프레임을 다시 떠서 읽으면 새 `crop_ref`를 발급한다(같은 상황에서 새 프레임에 새 `frame_ref`가 붙는 것과 같은 규칙).
- 따라서 **run 간 비교에 써도 된다.** 두 `PlateReadout`의 `frame_results[]`에 같은 `crop_ref`가 있으면 입력이 같았다는 뜻이고, 값이 달라졌다면 그 차이는 입력이 아니라 provider/모델 쪽에서 온 것이다.
- **`crop_ref`는 opaque identity이지 조회 handle이 아니다.** crop 이미지를 가져오는 public 경로는 어느 계약에도 없다. `DerivedAsset(derived_role=PLATE_IMAGE)`는 신고자료용 파생물이지 이 crop이 아니다(`contract-analysis-source-derived.md` §7.3). Consumer는 identity 비교·추적에만 쓰고 이미지 획득을 가정하지 않는다.
- **발급 주체는 `readout`이다.** `frame_ref`와 다른 점이다 — `FrameRef`는 `recording`이 발급하고 readout은 보존만 하지만(위 절), crop을 발급·조회하는 API는 `contract-source-asset-media-stream.md`에도 `contract-analysis-source-derived.md`에도 없다. 따라서 crop은 readout 내부 산출물로 둔다.
  - **확인 완료 (정철원, 이슈 [#40](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/40) C절, 2026-09-10).** 「`recording`은 기존 `FrameRef`를 안정적으로 제공하고, crop identity를 생성하거나 해석하지 않는다」로 Producer 경계가 확정됐다. 함께 동의된 4항목 — ① 같은 canonical frame은 기존 `FrameRef` 유지 ② readout의 extraction profile이 달라지면 새 crop identity 사용 ③ crop ID에 frame 위치나 profile 의미를 인코딩하지 않음 ④ `recording` Consumer가 crop ID 문자열을 파싱하지 않음. 따라서 위 「발급 주체는 `readout`」이 그대로 유효하다.
  - **잔여 — 문구 정정은 이 PR 범위 밖이다.** `contract-analysis-source-derived.md` §6.8과 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.10의 「readout은 `IncidentClip` 또는 그 clip에서 **발급된** Source-derived `FrameRef`/crop을 근거로 사용한다」는 여전히 crop도 asset 계층이 발급하는 것처럼 읽힌다. 위 확정과 어긋나지는 않으나 오독 여지가 남아 있고, 두 문서 모두 `recording`·ADR 소유라 별도 후속으로 분리했다.
  - 나중에 `recording`이 crop 자산을 발급하게 되면 readout은 `crop_ref`를 대체하지 않고 `PLATE_IMAGE`처럼 **별도 필드**로 받는다.
- **`evidence` Consumer 수용 (김준영, PR #27 리뷰, 2026-09-11).** crop 이미지 조회 handle로 쓰지 않고 내부 ID를 해석하지 않는다는 조건으로 위 전제를 수용했다.
- **스키마 변경이 아니다.** 기존 필드의 의미를 명시한 것이므로 `plate-readout/v1.2`를 유지한다.
- **fixture 반영 완료.** Mock Pack v4(`develop` @ `d9d8e2b`)에서 `plate_reread_001`의 재판독 crop이 `crop_p001_004/005`로 교체돼 위 규칙과 일치한다 — 원 판독 `001/002`, 재판독 새 프레임 `003`과 충돌 없다(이슈 [#38](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/38) B 배정분 확인).

## `input_ref.source_profile` 값 공간 — 등재 (2026-09-10 · 신유민)

`source_profile`은 「같은 clip을 어떤 판독용 프로파일로 떠서 읽었나」를 나르는 필드이고, 재판독처럼 **같은 입력을 다시 읽는 실행에서 두 run의 유일한 기록된 차이**가 된다(`ReadoutRun`은 모델·프롬프트 세부를 담지 않는다 — §1 「포함하지 않는 것」). 지금까지 예시에만 등장하고 등재 목록이 없었다.

| 값 | 의미 |
| --- | --- |
| `readout-native` | 기본 판독 프로파일 |
| `readout-native-hires` | 고해상도 재추출 프로파일. 저해상도·프레임 불일치로 abstain한 뒤 재판독할 때 쓴다 |

- **닫힌 목록이 아니다.** 신규 값은 이 표에 등재한 뒤 쓴다(`failure-taxonomy.md`의 값 등재 규칙과 같다).
- `source_profile`(readout의 판독 라벨)과 `profile_ref`(자산 식별자)는 다른 개념이다 — 연결이 필요해지면 canonical space 소유자인 `recording`이 대응을 정한다(`contract-analysis-source-derived.md` §4.4). 그 §4.4의 canonical profile 값 목록은 아직 Pending이며, 아래 표는 그것과 별개인 **readout 판독 라벨**의 목록이다.

## `ReadoutRun`과의 연결 — `run_ref` (B03 종결, 2026-09-07 · Decider 신유민 · 확인 유소연·김대원)

`PlateReadout`·`OverlayTimeReadout`은 최상위 **필수** 필드 `run_ref`로 자신을 생성한 실행을 가리킨다.

```
"run_ref": { "kind": "readout_run", "ref": "rr_881" }
```

- 모양은 `contract-observation.md` §3의 공통 `ContractRef {kind, ref}`다. 평문 `run_id` 문자열을 쓰지 않는다. `ref` 값은 `ReadoutRun.run_id`다.
- **불변조건: 결과가 존재하면 `run_ref`가 존재하고 유효하다.** `ReadoutRun.outcome`이 `SUCCEEDED`든 `PARTIAL`이든 무관하다.
- `readout_id`(결과 식별자)와 `run_ref`(실행 식별자)는 **둘 다 유지**한다. 실행이 완전히 실패하면 `ReadoutRun`만 남고 결과는 생성되지 않으므로(`ReadoutRun` 1건 : 결과 0~1건) 둘을 합치지 않는다.
- **재시도는 새 `run_id`와 새 `readout_id`**다. 재시도 결과 간 supersede 관계는 `readout` 소유가 아니다 — 어느 `readout_id`가 현재 값인지는 `case` 진행 상태와 `CaseView` projection 소관이며 **이 계약에 `supersedes_ref`를 두지 않는다.**
- 결과 → run 역추적은 보장하고, 그 반대(run → 결과)는 보장하지 않는다. `ReadoutRun.result_refs[]`는 없다.
- 결과 안의 `observation.produced_by.run_ref`는 최상위 `run_ref`와 **같은 실행**을 가리킨다. `readout`이 생산하는 `Observation`은 `produced_by.run_ref`를 항상 채운다(`Observation` v1은 optional이지만 readout 결과는 항상 `ReadoutRun`에서 나오므로 Producer-side로 강화). 최상위 `run_ref`가 authoritative다.

v4 §4-모듈3 ③이 `read_plate -> ReadoutRun, PlateReadout`으로 반환값을 둘로 명시한다. 이 계약은 **관찰 결과**를 담고, 실행의 성공/부분성공/실패와 실패 단계는 `contract-readout-run.md`가 담는다. `run_ref`는 `JobRecord.job_id`나 `JobExecution.execution_id`가 아니다 — `ReadoutRun → JobExecution` 역추적은 `JobExecution.produced`의 `{kind:"readout_run", ref}`가 담당한다.

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
| `run_ref` | **필수.** 이 결과를 생성한 `ReadoutRun`의 `ContractRef` — `{kind:"readout_run", ref:<run_id>}` (§3) |
| `case_id` | 연결된 case |
| `candidate_id` | 사용자가 선택했거나 case가 지정한 사건 후보 |
| `input_ref` | OCR 근거가 된 `incident_clip_ref`(**필수**), `source_profile`, `provenance`(근거가 Source-derived임을 뜻하는 불변조건 §3-2·§3-3의 실제 근거). (v1.2, 2026-09-08) `span_ref`는 삭제됐다 — 사건 구간 canonical ref는 `incident_clip_ref`다 |
| `target_association` | 실제로 어떤 차량/영역을 대상으로 번호판을 읽었는지와 근거 |
| `observation` | 번호판 관찰값 — 공용 `Observation<T> v1` envelope(`contract_version`·`value`·`status`·`source`·`support_refs`·`produced_by`). 확정값이 아님. `support_refs`는 빈 배열 — 근거 ref는 `best_frame`·`frame_results[]`가 소유한다 |
| `consensus` | 여러 프레임 OCR을 종합한 결과 |
| `abstained` | 번호판 확정을 보류했는지 |
| `abstain_reason` | 보류 사유 |
| `best_frame` | 대표 근거 프레임/crop |
| `frame_results` | 프레임별 OCR 관찰 결과 |

## 예시 JSON

정상 실행(`ReadoutRun rr_881`, `outcome=SUCCEEDED` — `contract-readout-run.md` §7)에서 생성된 결과:

```json
{
  "readout_id": "readout_plate_001",
  "run_ref": { "kind": "readout_run", "ref": "rr_881" },
  "case_id": "case_001",
  "candidate_id": "candidate_001",
  "input_ref": {
    "incident_clip_ref": "clip_0001",
    "source_profile": "readout-native",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
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
    "contract_version": "observation/v1",
    "value": "12가34?6",
    "status": "NEEDS_REVIEW",
    "source": { "kind": "readout.plate_ocr" },
    "support_refs": [],
    "produced_by": {
      "module": "readout",
      "run_ref": { "kind": "readout_run", "ref": "rr_881" }
    }
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

**완전 실패 예시는 없다 — 그것이 규칙이다.** `ReadoutRun rr_882`(`outcome=FAILED`, `failure.kind=PLATE_DETECTION` — `contract-readout-run.md` §8)처럼 실행이 완전히 실패하면 `PlateReadout`은 **생성되지 않는다.** 실패 사실·원인은 `ReadoutRun`만 갖는다.

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

**`abstain_reason`이 authoritative다** (2026-09-07). `observation.reason.code`는 abstain 외의 사유(`UNKNOWN`/`ERROR` 진단)에만 쓰고, `abstained=true`일 때 `reason.code`를 중복 채우지 않는다. 두 필드가 어긋날 자리를 만들지 않기 위함이다.

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
| `run_ref` | **필수.** 이 결과를 생성한 `ReadoutRun`의 `ContractRef` — `{kind:"readout_run", ref:<run_id>}` (§3) |
| `case_id` | 연결된 case |
| `candidate_id` | 사용자가 선택했거나 case가 지정한 사건 후보 |
| `input_ref` | OCR 근거가 된 Source-derived input (`provenance` 포함) |
| `observation` | 화면 timestamp 관찰값 — 공용 `Observation<T> v1` envelope. `source.kind`는 namespaced `readout.overlay_ocr`(`TimeResolution`이 쓰는 시각 source 값 공간과 같은 enum으로 합치지 않는다). 최종 발생 시각 확정값이 아님 |
| `validation` | readout이 수행한 형식/시간흐름/구간 정합성 검증 |
| `samples` | 검증에 사용한 sample별 OCR 결과 |

## 예시 JSON

정상 실행(`ReadoutRun rr_883`, `operation=OVERLAY_TIME_READ`, `outcome=SUCCEEDED`)에서 생성된 결과. 실행이 완전히 실패하면 이 결과도 생성되지 않고 `ReadoutRun`만 남는다(§4 말미와 같은 규칙):

```json
{
  "readout_id": "readout_time_001",
  "run_ref": { "kind": "readout_run", "ref": "rr_883" },
  "case_id": "case_001",
  "candidate_id": "candidate_001",
  "input_ref": {
    "incident_clip_ref": "clip_0001",
    "source_profile": "readout-native",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "observation": {
    "contract_version": "observation/v1",
    "value": "2026-09-02T18:31:12+09:00",
    "status": "OK",
    "source": { "kind": "readout.overlay_ocr" },
    "support_refs": [],
    "produced_by": {
      "module": "readout",
      "run_ref": { "kind": "readout_run", "ref": "rr_883" }
    }
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
