# ADR — `SourceAsset` / `MediaStream` / `FrameRef` (+ canonical `AssetFacts`) Data Contract

**Status:** Accepted — Consumer Review 종결 (2026-09-08)

**Contract:** `../contract-source-asset-media-stream.md` (`source-asset-media-stream/v1`)
**Producer / Owner:** `recording` — 정철원
**Consumers:** `search` — 서어진 · `readout` — 신유민 · `case` — 유소연 · `evidence` — 김준영(`AssetFacts`를 `case` 주입으로 받음)
**Architecture:** v4 §5-1 ② (`SourceAsset`/`MediaStream` 부분) · §5-3 · §4-모듈1 ⑥·⑨
**상위 결정:** `adr-data-contract-call-closure-2026-09-07.md` §4.6(B07)·§4.9(W07) — 자산 사실의 최소 목록·전달 경계·`FrameRef` 보장 6건 · `adr-data-contract-call-closure-2026-09-08.md` §4.5(Draft 검수) · §4.8(자산 ref `kind` 표기) · §4.9(`AssetSpan` identity) · §4.10(Consumer Review 종결)
**Date:** 2026-09-08 (작성일) · **수락일 2026-09-08** (Consumer Review 4건 종결 후 Owner 정철원 반영)

> 이 ADR은 계약이 **왜 이렇게 나뉘고 무엇이 확정됐는지**를 남긴다. 계약 스키마는 여기 다시 적지 않는다 — 현재 규칙은 상위 폴더 계약이 소유하고 이 문서는 근거·기각안·Consumer Review 기록만 소유한다. §4는 Draft 단계의 「제안」 기록이고 §1~§3·§5·§6은 그대로다. **Consumer Review 결과와 수락 근거는 §7에 있다.**

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

## 4. Draft가 새로 제안한 설계 (Consumer Review 대상 — 결과는 §7)

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
## 7. Consumer Review 결과 (2026-09-08 종결)

### 7.1 Consumer별 검토 역할

| Consumer | 이 계약에서의 역할 | 검토한 것 |
| --- | --- | --- |
| `search` — 서어진 | `CandidateEvent.thumbnail_ref: FrameRef` **생산자**. `stream_selector`로 분석 대상 stream 선택 | FrameRef 발급 경로 · `role=UNKNOWN`·`AUDIO` stream의 입력 선택 소유 · 실패 표현 · `kind` 문자열 비교 · 자기가 소비하지 않는 객체 경계 |
| `readout` — 신유민 | `PlateReadout.best_frame.frame_ref`·`frame_results[].frame_ref` **생산자** | 판독 대상 frame의 FrameRef 발급 경로 · 복수 stream frame 구분 · `source_offset_sec` 정밀도 · frame 조회 실패의 `ReadoutRun.failure` 매핑 |
| `case` — 유소연 | `lookup_asset_facts` **호출자**이고 `AssetFacts`를 evidence에 주입하는 broker. `CaseView.candidates[].thumb_ref` projection | 호출 시점·신선도 · `UNKNOWN` 재조회 정책 · 모르는 ref의 응답 · `thumb_ref` 자산 종류 · `timeline_range`의 revision |
| `evidence` — 김준영 | `AssetFacts`를 case 주입으로 받아 ASSET 판정. `FrameRef`는 직접 소비하지 않음(readout observation 경유) | coverage 계산에 필요한 revision provenance · `UNKNOWN`/`UNAVAILABLE` 구분 기준 · `byte_size=null` 허용 조건 · lineage 최소 구성 · `derived_role` 최소 목록 |

### 7.2 제기된 핵심 우려

1. **FrameRef를 최초로 발급받을 방법이 없었다.** Draft에는 `read_frame(frame_ref)`만 있어서 「이미 있는 frame을 읽는」 capability만 존재했다. search는 thumbnail용, readout은 판독 대상용으로 **좌표에서 FrameRef를 얻어야** 하는데 그 경로가 계약에 없었다. 상위 Architecture(v4)의 서명은 `read_frame(frame_ref | span, at) -> FrameRef`로 두 동작이 한 함수에 섞여 있었다.
2. **revision 없는 timeline 좌표.** `AssetFacts.timeline_range`에 기준 timeline과 revision이 없었다. evidence가 스스로 필요하다고 확정한 FINAL_PACKAGE coverage 판정은 `CandidateEvent.span`(revision 포함)·`AnalysisScope` relative range(revision 포함)와 비교하는 것이라, rebase 이후 비교 대상이 사라진다. case·evidence 둘이 같은 이유로 `REQUIRED`로 올렸다.
3. **실패와 「없음」이 구분되지 않았다.** `lookup_asset_facts`에 모르는 ref를 넣었을 때의 응답이 없어서, 「자산이 있었다가 사라짐」(`availability=UNAVAILABLE`)과 「애초에 잘못된 ref」를 같은 payload로 받게 된다. case는 이 둘을 사용자에게 다르게 보여줘야 하고, readout은 frame 조회 실패를 `PLATE_ABSTAINED`(도메인 결과)와 구분해 `ReadoutRun.failure`로 옮겨야 한다.
4. **같은 대상에 두 표기가 공존했다.** Draft는 자산 ref `kind`를 대문자(`SOURCE_ASSET`)로, 이미 수락된 `Observation`·`TimeResolution`·`RequirementReport` 예시와 확정된 run ref는 소문자(`source_asset`·`analysis_run`)로 썼다. 네 Consumer 모두 `kind`를 **정확 문자열로 비교**할 계획이라, 두 표기가 남으면 대소문자 무시 비교나 Consumer별 상수표가 생긴다 — 둘 다 lineage를 조용히 끊는 경로다.
5. **null·부재·0의 의미가 계약군 안에서 엇갈렸다.** `SourceAsset.byte_size`는 「필수 0 이상」인데 `AssetFacts.byte_size`는 「`AVAILABLE` 아니면 `null` 허용」이었고, `duration_sec`은 한쪽은 「부재」 한쪽은 「nullable」이었다. `MediaStream.availability`의 값 공간은 명시가 없었다.
6. **lineage 「빈 배열」이 두 뜻이었다.** evidence는 recording을 직접 호출할 수 없어서 clip → source_asset을 스스로 따라갈 수 없다. `lineage=[]`가 「원본이 없다」와 「lineage를 모른다」를 함께 뜻하면 Source-derived 증명이 성립하지 않는다.
7. **`role=UNKNOWN`·`AUDIO`의 처리 소유가 불명확했다.** 계약이 선택 정책까지 정해야 하는지, `stream_selector`로 미뤄야 하는지.
8. **버전 문자열이 두 형식이었다.** 헤더는 `…/v0.2`, 본문 payload는 `"0.2.0"`.

### 7.3 계약에 반영한 변경

| # | 반영 | 계약 위치 |
| --- | --- | --- |
| 1 | `resolve_frame(locator) -> FrameRef`와 `read_frame(frame_ref) -> image`를 **분리**하고, locator를 `TIMELINE_POSITION`(timeline_id+revision+at_sec, search용)·`STREAM_POSITION`(media_stream_ref+source_offset_sec, readout용) 두 형태로 명시적 discriminator를 두어 구분. 두 형태의 필드를 섞지 않는다. canonical frame은 **원본 MediaStream 기준**으로 발급하고 `AnalysisSource`·proxy 기준으로 발급하지 않는다 | §5.3 |
| 2 | `source_offset_sec`·`at_sec`은 decimal seconds이며 **최소 ms 수준 또는 원본 stream time base보다 정밀한 값**을 보존. 임의 반올림 금지. 실제 선택된 frame의 offset을 `FrameRef`에 기록하고, 요청 offset과 다를 수 있음을 명시. 같은 canonical frame으로 정규화되는 요청은 같은 FrameRef | §5.4 |
| 3 | `AssetFacts`에 `timeline_ref {timeline_id, revision}`를 신설하고 `timeline_range`를 `{start_sec, end_sec}`로 확정. **쌍 불변조건** `timeline_ref == null ⇔ timeline_range == null`. rebase가 기존 `AssetFacts`의 revision을 바꾸지 않는다 | §6.4 · §6.1-7 |
| 4 | `resolve_frame`·`read_frame`·`lookup_asset_facts` 실패를 정상 `null`·`UNAVAILABLE` 객체와 **구분되는 machine-readable failure `{kind, code}`**로 제공. frame 최소 code `FRAME_NOT_FOUND`·`STREAM_UNAVAILABLE`·`OUT_OF_RANGE`·`UNKNOWN_REF`·`TEMPORARY_FAILURE`, lookup 최소 code `UNKNOWN_REF`·`INVALID_REF_KIND`·`TEMPORARY_FAILURE`. `UNKNOWN_REF`(등록된 적 없음)·`INVALID_REF_KIND`(대상이 아닌 kind)·`UNAVAILABLE`(있었지만 지금 못 씀) 세 가지를 혼용 금지 | §6.6 |
| 5 | 자산 계층 `ContractRef.kind` 값 공간을 **이 계약 §2.1 한 곳이 소유**하고 8개 값을 소문자 snake_case로 확정. 정확 문자열 비교 강제 — 대소문자 무시·별칭·prefix 추론·Consumer별 변환표 금지. `asset_kind`는 대문자 enum을 유지하고 §6.2 **1:1 대응표**로 연결(문자열 동일성 요구하지 않음). `asset_kind`의 직접 대상이 아닌 kind는 `INVALID_REF_KIND` | §2.1 · §2.2 · §6.2 |
| 6 | `byte_size`·`duration_sec`을 `SourceAsset`·`MediaStream`·`AssetFacts`에서 **키 항상 존재 + nullable**로 통일. `AVAILABLE ⇒ byte_size non-null`, 그 외 측정 실패는 `null`이고 **0으로 꾸미지 않는다.** `availability` 3값과 부여 조건을 세 객체가 공유하도록 한 절에 정의하고, 한 stream의 `UNAVAILABLE`이 asset 전체 상태를 바꾸지 않음을 명시 | §3.4 · §3.5 |
| 7 | 파생 자산 `lineage[]`를 **원본까지 평탄화**하고 최소 하나의 `source_asset` 또는 `external_source`를 포함하도록 확정. 객체의 `source_refs[]`(직접 부모)와 `AssetFacts.lineage[]`(전체 provenance)를 다른 필드로 구분. **모르는 상태를 빈 배열로 표현 금지** — `availability=UNKNOWN` 또는 lookup failure로 표면화. `SOURCE_ASSET` 자신의 `lineage=[]`는 「위가 없다」는 사실 | §6.3 · §6.1-8 |
| 8 | `role=UNKNOWN`은 정상 video stream 상태이고 알려진 role이 없으면 후보로 쓸 수 있음을 계약이 보장. **선택 우선순위는 계약이 정하지 않는다** — search `stream_selector`·readout 도메인 판단 소유. `AUDIO` stream은 원본 자산 사실에 그대로 기록하고 분석 사본에서만 profile에 따라 제외 | §4.4 |
| 9 | 헤더와 모든 payload가 `source-asset-media-stream/v1` **한 문자열**을 쓰고 `1.0.0` 형식과 혼용하지 않음. forward-compatibility 규칙(모르는 optional 필드 무시 · optional 추가는 minor · 필수 추가·타입 변경·nullable 축소·enum 제거는 breaking) 명문화 | 헤더 · §10 |
| 10 | `CandidateEvent.thumbnail_ref`·`CaseView.candidates[].thumb_ref` = `FrameRef`를 본문에 명시. 이미지 전달 경계(`web → recording` 금지, `case → recording → projection → web`)도 함께 | §7 |
| 11 | `lookup_asset_facts` 결과가 자체 `checked_at`을 갖는다는 점만 계약이 보장하고, **호출 시점·재조회 정책은 case orchestration, stale 기준은 evidence policy**가 소유함을 명시(스키마에 고정하지 않음) | §6.5 |

### 7.4 반영하지 않은 요청과 이유

| 요청 | 판정 | 이유 |
| --- | --- | --- |
| `AnalysisSource` profile의 **정확한 값 목록**을 이 Review에서 확정 | **미반영 — Pending 유지** | recording·search·readout 3자 합의 항목이다. 계약이 정한 것은 「`profile_ref`는 필수 non-null」·「canonical 값 공간은 recording 소유」·「Consumer는 문자열을 파싱하지 않고 동등성 비교만」까지다(형제 계약 §4.4). 값 목록은 opaque ref의 **내용**이므로 필드 모양·소유·필수성을 확정하는 데 필요하지 않고, 소비 코드도 동등성 비교만 하므로 값이 늘어도 breaking이 아니다. 요청한 Consumer 자신이 3자 합의를 전제로 요청했다 |
| `stream_selector`의 직렬화와 기본 stream 선택 정책 | **미반영 — Pending 유지** | 선택 **정책**은 search 소유이고 계약은 값의 의미만 보장한다는 결론에 Consumer가 동의했다. B07·W07 결정과도 일치 |
| thumbnail 이미지의 실제 전달 방식(URL/endpoint/stream) | **미반영 — Pending 유지** | 전달 방식은 `web` 구현 선택을 강제한다. 자산 **종류**(`FrameRef`)와 호출 경계만 확정했다 |
| `availability` → `BLOCK`/`UNKNOWN` 판정 매핑을 계약에 등재 | **의도적 미반영** | 판정 매핑은 evidence policy 소유다. recording 계약은 상태 **사실**만 제공한다. evidence Owner 본인이 「이 매핑은 계약에 고정하지 않는다」고 확인했다 |
| `derived_role`의 어느 값이 필수인지와 부재 시 outcome | **의도적 미반영** | 같은 이유. 등재 값 2건(`REPORT_VIDEO`·`PLATE_IMAGE`)만 형제 계약 §7.3에 두고 필수성 판정은 evidence policy에 남겼다 |
| `media_stream_refs=[]` 허용 조건 · `media_type`/`role` enum 확장 | **미반영 — Pending 유지** | 어느 Consumer도 필수로 요구하지 않았고 payload를 만들거나 소비하는 데 필요하지 않다 |
| `resolution`/`fps`/`codec`/checksum을 최소 자산 사실에 포함 | **기각(상위 결정 유지)** | B07에서 이번 통합의 ASSET 판정에 불필요하다고 확정됐다. 필요해지면 계약 개정 |
| frame seek/rounding 알고리즘을 계약에 명시 | **기각** | recording Tech Spec 소유. 계약은 동일성 보장과 정밀도 하한만 갖는다 |

### 7.5 조건부 승인 조건의 충족 근거

네 Consumer는 모두 `CHANGES_REQUIRED`로 시작하면서 **각자 승인 전제를 명시**했고, Owner(정철원)가 그 전제를 전부 수용해 `CHANGES_REQUIRED 수용 — 개정 후 재검수`로 답했다. 아래는 각 전제와 그것이 계약 본문의 어디로 들어갔는지다.

| Consumer | 승인 전제 | 충족 | 근거 위치 |
| --- | --- | --- | --- |
| `search` | FrameRef 발급 capability | 충족 | §5.3 `resolve_frame` |
| | 구분 가능한 실패 형태 | 충족 | §6.6 |
| | profile **책임**과 **값 공간 소유** | 충족 | 형제 계약 §4.4 — 필수 non-null · recording 소유 · opaque. 값 목록은 요청자 본인이 3자 합의로 분리 |
| | Timeline revision 연결 | 충족 | §6.4 |
| | `availability`/null 규칙 | 충족 | §3.4 · §3.5 |
| | 자산 `kind` 값 확정 | 충족 | §2.1 · §2.2 |
| `readout` | 좌표 → FrameRef capability | 충족 | §5.3 `STREAM_POSITION` locator |
| | `source_offset_sec` 정밀도 보장 | 충족 | §5.4 |
| | 실패 taxonomy가 `PLATE_ABSTAINED`와 구분되는 `ReadoutRun.failure`로 매핑 | 충족 | §6.6 말미(`kind: INPUT` · `code: INPUT_UNAVAILABLE`) |
| `case` | `thumb_ref` = `FrameRef` 본문 명시 | 충족 | §7 |
| | `timeline_range`에 revision 추가 | 충족 | §6.4 |
| | 모르는 ref의 실패 형태 구분 | 충족 | §6.6 (`UNKNOWN_REF` vs `UNAVAILABLE`) |
| | 자산 `kind` 소문자 반영 | 충족 | §2.1 · §2.2 · §6.2 |
| `evidence` | 자산 ref `kind` 확정 + `asset_kind` 4값 닫힌 목록 + 1:1 대응표 | 충족 | §6 필드표 · §6.2 |
| | `derived_role` 2값 등재 | 충족 | 형제 계약 §7.3 |
| | clip provenance span 형태·단위 정리 | 충족 | 형제 계약 §6.3 |
| | lineage 평탄화 규칙 | 충족 | §6.3 |

**판정.** 네 Consumer가 제시한 필수 조건은 모두 계약 본문에 들어갔고, 미반영으로 남긴 항목(§7.4)은 어느 Consumer도 승인 전제로 걸지 않았거나 요청자 자신이 별도 합의로 분리한 것이다. 따라서 **조건 충족**으로 판정하고 계약을 `Final — Accepted`, 이 ADR을 `Accepted`로 전환했다. 이 판정과 남은 항목의 비차단 근거는 `adr-data-contract-call-closure-2026-09-08.md` §4.10이 함께 기록한다.

### 7.6 구현에서 확인해야 하지만 계약 승인을 막지 않는 항목

계약 의미가 확정됐으나 **실행 코드가 없어 이번에 확인할 수 없는** 것들이다. 계약 불확정과 구분한다.

- `resolve_frame`의 두 locator가 실제 구현에서 같은 canonical frame으로 정규화되는지 — 동일성 보장은 계약이지만 seek/rounding은 Tech Spec이다.
- `source_offset_sec`의 실제 정밀도가 원본 stream time base를 넘는지.
- `lookup_asset_facts` 호출 빈도가 `check_requirements` 직전 매회로 충분한 성능인지 — case orchestration 규칙이며 스키마에 고정하지 않았다.
- `lineage` 평탄화가 깊은 파생 사슬에서 몇 단계까지 실제로 채워지는지.
- `AssetFacts`를 case가 evidence에 주입하는 실제 payload가 `check_requirements` 서명과 맞는지.

## 8. 아직 확정하지 않은 내용

계약 §9 Pending과 같다 — `MediaStream.media_type`/`role` enum 확장·nullability · `media_stream_refs=[]` 허용 조건 · profile 값 목록(3자 합의) · `stream_selector` 직렬화와 기본 선택 정책 · thumbnail 이미지 전달 방식 · frame seek/rounding 알고리즘.

**2026-09-08 Consumer Review에서 닫힌 항목**(이전 판본의 이 절에 있었다): `AssetFacts.timeline_range`의 모양과 timeline identity/revision · `byte_size` 필수/nullable 관계 · `duration_sec` 부재/null 표기 · `MediaStream.availability` 값 공간 · 헤더/본문 버전 문자열 형식 · 좌표 → `FrameRef` 발급 capability · `asset_kind` vocabulary와 외부 계약 kind 매핑 · lineage 최소 구성.

## 9. 추가 결정 회차 발생 조건

- **열린 회차: 없다.** 자산 계층 `ContractRef.kind` 표기와 `AssetSpan` identity 회차는 2026-09-08에 종결됐다(`adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.9).
- **새 회차가 생기는 조건:** ① profile 값 집합을 recording·search·readout이 나눠 갖는 방식이 3자 합의로 정해지지 않을 때 ② thumbnail 전달 방식이 `web` 구현 선택을 강제할 때 ③ Consumer가 다른 Owner의 수락된 계약 변경을 요구할 때 ④ `derived_role`/`transform_ref`가 evidence 판정 규칙을 recording 계약에 고정하게 될 때. 단일 Owner가 계약 안에서 고칠 수 있는 항목(필드표 누락·표기 통일·예시 보정)은 회차 없이 Owner가 반영한다.

## 10. 이후 변경 시 지켜야 하는 것

- §3의 상위 결정 7건 — 이 계약 개정으로 뒤집을 수 없다. 바꾸려면 해당 결정의 Decider와 변경 ADR이 필요하다.
- `AssetFacts`의 canonical 정의처가 이 계약 §6이고 **자산 계층 `kind` 값 공간의 정의처가 §2.1**이라는 점 — 다른 계약에 복제하지 않는다.
- Pending 항목을 Consumer 확인 없이 채우지 않는다. Owner도 마찬가지다.
- 이 ADR은 수락됐으므로 **본문을 고치지 않는다.** 결정이 바뀌면 새 ADR을 쓰고 표기 보정만 예외다(`README.md`).
- `Final` 이후의 breaking change(필수 필드 추가·타입 변경·nullable 축소·enum 값 제거)는 major version과 migration이 필요하다.

## 11. 한 줄 요약

> `recording`은 물리 파일 `SourceAsset`, 그 안의 `MediaStream`, canonical frame `FrameRef`를 서로 다른 opaque identity로 제공하고, 좌표에서 FrameRef를 발급하는 `resolve_frame`과 revision·평탄화 lineage·판정 시점을 담은 `AssetFacts` 한 정의로 자산 사실을 노출한다. B07·W07 상위 결정과 일치하며, 4 Consumer가 제시한 필수 조건이 모두 반영되어 2026-09-08 수락됐다.
