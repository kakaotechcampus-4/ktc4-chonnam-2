# ADR — `SourceAsset` / `MediaStream` / `FrameRef` (+ canonical `AssetFacts`) Data Contract

**Status:** Proposed — Consumer Review pending

**Contract:** `../contract-source-asset-media-stream.md` (Draft `source-asset-media-stream/v0.2`)
**Producer / Owner:** `recording` — 정철원
**Consumers:** `search` — 서어진 · `readout` — 신유민 · `case` — 유소연 · `evidence` — 김준영(`AssetFacts`를 `case` 주입으로 받음)
**Architecture:** v4 §5-1 ② (`SourceAsset`/`MediaStream` 부분) · §5-3 · §4-모듈1 ⑥·⑨
**상위 결정:** `adr-data-contract-call-closure-2026-09-07.md` §4.6(B07)·§4.9(W07) — 자산 사실의 최소 목록·전달 경계·`FrameRef` 보장 6건 · `adr-data-contract-call-closure-2026-09-08.md` §4.5 — 이 Draft의 검수 결과와 상태
**Date:** 2026-09-08 (이 ADR 작성일. **수락일은 없다** — Consumer Review가 끝나지 않았다)

> 이 ADR은 계약이 **왜 이렇게 나뉘고 지금까지 무엇이 확정됐는지**를 남긴다. 계약 스키마는 여기 다시 적지 않는다(현재 규칙은 상위 폴더 계약이 소유). Consumer Review 결과와 수락 기록은 Review가 끝난 뒤 §7에 추가하고 그때 Status를 바꾼다. **지금 이 문서를 근거로 계약을 Accepted로 읽지 않는다.**

---

## 1. 계약을 분리한 이유

- v4 §5-1 ②는 `SourceAsset`/`MediaStream`/`RecordingTimeline`/`AssetSpan`을 한 줄에 두지만, `RecordingTimeline`·`AssetSpan`·`TimeSourceCandidate`는 이미 별도 Final 계약(`contract-recording-timeline-asset-span.md`)으로 수락됐고 그 계약은 헤더에 「`SourceAsset`/`MediaStream` 스키마는 범위 밖」이라고 명시했다. 남은 물리 자산 identity 계층을 담을 문서가 없었다.
- 2026-09-06 감사 B07은 「opaque ref만 있으면 통합이 된다」는 PM 판단을 뒤집었다 — `RequirementReport`의 ASSET 판정은 자산 사실 없이 계산할 수 없다. 그 사실을 담을 canonical 정의처가 필요했고, 2026-09-07 회차는 그것을 recording 자산 계약 2건이 소유한다고 정했다(`ACCEPTED_PENDING_IMPLEMENTATION`).
- `FrameRef`는 `PlateReadout`·`CandidateEvent.thumbnail_ref`·`CaseView.thumb_ref`가 이미 참조하는 타입인데 필드 계약이 없었다(W07). 위치를 ID에 인코딩하지 않는다는 규칙(v4 §5-3)을 필드로 고정할 자리가 필요했다.
- 파생 자산(`AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset`)은 lifecycle·provider 경계가 다른 관심사라 별도 계약(`contract-analysis-source-derived.md`)으로 나누고, 공통 `AssetFacts`는 이 계약 한 곳이 소유해 복제를 막는다.

## 2. 소유권과 권위 데이터

| 데이터 | 소유 | 권위 |
| --- | --- | --- |
| `SourceAsset`·`MediaStream`·`FrameRef` identity와 관계 | `recording` | 계약 필드. ref 문자열 파싱 금지 |
| 자산 존재·가용·크기·lineage의 판정 시점 사실 | `recording` | `lookup_asset_facts(asset_ref) → AssetFacts`, 시점은 `checked_at` |
| `FrameRef → media_stream_ref + source_offset_sec` 대응 · canonical frame 선택 알고리즘 | `recording`(알고리즘은 Tech Spec) | 동일성 보장을 깨지 않는 범위에서 구현 자유 |
| 자산 사실을 신고 규칙상 어떻게 판정하는가 | `evidence` policy | 이 계약 밖 |
| `AssetFacts`를 누가 조회해 누구에게 주는가 | `case`가 조회·주입 | B07 경계. `evidence`·`web`은 `recording`을 직접 호출하지 않음 |

## 3. 현재까지 확정된 설계 (상위 결정에서 온 것 — 이 Draft가 바꿀 수 없는 부분)

1. **opaque identity 세 종류**: `sa_`·`ms_`·`fr_` 접두어는 사람 구분용 convention이며 종류·role·위치를 인코딩하지 않는다(v4 §5-3 · 후속 보정 ADR W07).
2. **`SourceAsset != MediaStream`**, 한 파일에 복수 video/audio stream, camera role(`FRONT`/`REAR`/`UNKNOWN`)과 media 종류(`VIDEO`/`AUDIO`) 분리(v4 원칙 4 · §5-3).
3. **`FrameRef` 보장 6건**(2026-09-07 B07): opaque identity · 동일 stream 동일 canonical frame = 동일 ref · 내부 파싱 금지 · `read_frame(frame_ref)`로 실제 frame 획득 · `media_stream_ref`+source offset 계약 필드 조회 · rebase 불변.
4. **최소 자산 사실**(2026-09-07 B07): `asset_ref` · asset kind/derived role · byte size · 판정 시점 존재·가용 · lineage · 조건부 `duration + timeline_range`. 제외: resolution·fps·codec·checksum·번호판 가시성·화면 timestamp 표시.
5. **전달 경계**: `case → recording lookup → AssetFacts → case → evidence.check_requirements(..., assets)`.
6. **`CaseView.candidates[].thumb_ref`는 `FrameRef`**(2026-09-07 W07). 이미지 전달 형태는 이 계약이 정한다 — 아직 Pending.
7. 사용자 외부 원본은 서비스가 overwrite/delete하지 않는다(v4 §4-모듈1 ⑨ · 보안 검수 #15).

## 4. Draft가 새로 제안한 설계 (Consumer Review 대상)

- `AssetFacts` 필드 9개와 그 nullable 규칙(`AVAILABLE`이면 `byte_size` non-null, 그 외 `null` 허용 · `checked_at` 항상 필수 · `lineage=[]` 허용 · `derived_role`/`duration_sec`/`timeline_range` nullable).
- `availability` 3값(`AVAILABLE`/`UNAVAILABLE`/`UNKNOWN`).
- `asset_ref: ContractRef{kind, ref}` + 별도 `asset_kind` 필드 이중 표기.
- `MediaStream.role`은 video에만, audio에는 사용하지 않음.
- `read_frame`·`lookup_asset_facts` 두 capability 서명.

## 5. 고려한 대안과 기각 이유 (Draft·상위 결정 기준)

| 대안 | 기각 이유 |
| --- | --- |
| ref 문자열에 위치·role 인코딩(`fr_<stream>@<offset>` · `ms_<asset>_<role>`) | Consumer가 파싱하게 되어 recording 내부 구조에 결합. v4 §5-3·W07이 금지 |
| `SourceAsset` = video stream 하나로 취급 | 실측 AVI에 front/rear/audio 복수 stream. v4 원칙 4 위반 |
| evidence가 `recording` lookup을 직접 호출 | evidence는 다른 모듈을 호출하지 않는 경계(v4 §4-모듈4 · B07 회차에서 evidence Owner 반대). case 주입으로 확정 |
| 자산 사실을 `RequirementReport`/`ReportPackage` 계약에 복제 정의 | 규칙 복제(W05). canonical 정의는 recording 한 곳 |
| codec/fps/resolution을 최소 사실에 포함 | 이번 통합의 ASSET 판정에 불필요(B07). 필요해지면 계약 개정 |
| `AssetFacts`를 파생 계약에 재정의 | 두 곳 관리. 이 계약 §6 단일 소유로 확정 |

## 6. 불변조건 (Draft §3.3·§4.3·§5.2·§6.1 요약 — 원문은 계약)

identity 재사용 금지 · stream↔asset 역참조 일치 · role에서 identity 파생 금지 · `AUDIO`는 role 아님 · 한 stream 실패가 다른 stream/asset을 무효화하지 않음 · 동일 canonical frame = 동일 `FrameRef` · rebase 불변 · `source_offset_sec`는 display time이 아님 · `asset_ref.kind`·`asset_kind`·실제 대상 의미 일치 · `AVAILABLE ⇒ byte_size non-null` · `checked_at` 항상 필수·offset-aware · prefix로 kind/role/lineage 추론 금지.

## 7. 영향을 받는 Producer와 Consumer · Consumer별 확인 필요 항목

Consumer Review 문서는 PM 내부 기록이다. 아래는 공개해도 되는 확인 항목의 **주제**다. 답변과 판정은 Review 종료 후 이 절에 옮긴다.

| Consumer | 확인 필요 주제 |
| --- | --- |
| `search` | `CandidateEvent.thumbnail_ref`에 넣을 `FrameRef`의 발급 경로(span+시각 → FrameRef capability 부재) · `role=UNKNOWN`·`AUDIO` stream의 입력 선택 소유 · `ContractRef.kind` 표기 |
| `readout` | 판독 대상 frame의 `FrameRef` 발급 경로 · 복수 stream frame 구분 · `source_offset_sec` 정밀도 · `read_frame` 실패 표현 |
| `case` | `lookup_asset_facts` 호출 시점·신선도 · `availability=UNKNOWN` 재조회 정책 · thumbnail 이미지 전달 전 `thumb_ref`만으로의 표시 · 모르는 ref 응답 |
| `evidence` | `timeline_range`에 `timeline_ref{timeline_id, revision}` 부재 시 coverage 계산 가능 여부 · `UNKNOWN`/`UNAVAILABLE` 구분 · `byte_size=null` 허용 조건 · lineage 최소 구성 · `checked_at` stale 기준 소유 |

**Consumer Review 기록:** (비어 있음 — 아직 답변 없음)

## 8. 아직 확정하지 않은 내용 (계약 §9 Pending과 PM 검수 추가분)

- `MediaStream.media_type`/`role` 최종 enum·nullability · `media_stream_refs=[]` 허용 조건 · `AssetFacts.asset_kind` 전체 vocabulary · lineage 최소 구성 · `stream_selector` 직렬화 · thumbnail 이미지 전달 방식(계약 §9).
- `AssetFacts.timeline_range`의 모양과 timeline identity/revision 참조 · `SourceAsset.byte_size` 필수와 `AssetFacts.byte_size` nullable의 관계 · `duration_sec`의 부재/null 표기 통일 · `MediaStream.availability` 값 공간 · 헤더 버전 문자열(`…/v0.2`)과 본문(`"0.2.0"`) 형식 통일 · span+시각 → `FrameRef` 발급 capability(PM 검수, 2026-09-08 ADR §4.5).

## 9. 추가 CALL 발생 조건과 현재 열린 회차

- **열린 회차:** 자산 계층 `ContractRef.kind` 표기(`SOURCE_ASSET` vs 기존 `source_asset`)와 `asset_kind` 문자열 동일성 — Decider 정철원, `CALL_REQUIRED`. `AssetSpan` identity와 readout `span_ref` 참조 대상 — Decider 정철원, `CALL_REQUIRED`(파생 계약과 공유). 상태는 `adr-data-contract-call-closure-2026-09-08.md` §4.6·§9.
- **새 CALL이 생기는 조건:** Consumer 답변이 다른 Owner의 Accepted 계약 변경을 요구할 때(예: `Observation` 예시 표기, `PlateReadout.input_ref`) · `stream_selector`/profile 태그처럼 3자 이상이 값 집합을 나눠 가져야 할 때 · thumbnail 전달 방식이 `web`(신유민) 구현 선택을 강제할 때. 단일 Owner가 Draft 안에서 고칠 수 있는 항목(필드표 누락·표기 통일)은 CALL 없이 Owner가 반영한다.

## 10. 최종 승인 전 수정하면 안 되는 부분

- §3의 상위 결정 7건 — 이 Draft의 Consumer Review로 뒤집을 수 없다. 바꾸려면 해당 결정의 Decider(정철원 · B07/W07 확인자)와 변경 ADR이 필요하다.
- `AssetFacts`의 canonical 정의처가 이 계약 §6이라는 점 — 다른 계약에 복제하지 않는다.
- Pending 항목을 Consumer 답변 없이 채우는 것 — Owner도 Consumer 확인 없이 Pending을 확정하지 않는다.
- Status·수락일 — Consumer 4명의 판정이 기록되고 열린 회차 2건이 닫힌 뒤에만 `Accepted`로 바꾼다.

## 11. 한 줄 요약

> `recording`은 물리 파일 `SourceAsset`, 그 안의 `MediaStream`, canonical frame `FrameRef`를 서로 다른 opaque identity로 제공하고 최소 자산 사실을 `AssetFacts` 한 정의로 노출하기로 **제안**했다. B07·W07 상위 결정과 필드 수준에서 일치하며, Consumer Review와 표기·identity 회차 2건이 끝나기 전에는 수락되지 않았다.
