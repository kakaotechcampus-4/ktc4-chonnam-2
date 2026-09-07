# ADR — `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset` Data Contract

**Status:** Proposed — Consumer Review pending

**Contract:** `../contract-analysis-source-derived.md` (Draft `analysis-source-derived/v0.2`)
**Producer / Owner:** `recording` — 정철원
**Consumers:** `search` — 서어진 · `readout` — 신유민 · `case` — 유소연 · `evidence` — 김준영
**Architecture:** v4 §5-1 ③ · §4-모듈1 ⑥·⑦·⑨ · §7-3(Incident Clip ≠ Report Video) · §8-4(보관/삭제)
**상위 결정:** `adr-data-contract-call-closure-2026-09-07.md` §4.6(B07 — `AnalysisSource`가 Provider 입력을 보장 · `stream_selector` 미확정) · `adr-data-contract-call-closure-2026-09-08.md` §4.5 — 이 Draft의 검수 결과와 상태
**짝 계약의 공통 정의:** canonical `AssetFacts`는 `contract-source-asset-media-stream.md` §6 — 이 계약은 참조만 한다
**Date:** 2026-09-08 (이 ADR 작성일. **수락일은 없다**)

> 이 ADR은 계약이 **왜 네 의미로 나뉘고 지금까지 무엇이 확정됐는지**를 남긴다. 스키마는 계약이 소유한다. Consumer Review 결과는 Review가 끝난 뒤 §7에 추가하고 그때 Status를 바꾼다. **지금 이 문서를 근거로 계약을 Accepted로 읽지 않는다.**

---

## 1. 계약을 분리한 이유

- v4 §5-1 ③은 네 타입을 recording 소유로 두지만 정의처가 없었다. 2026-09-06 감사는 `AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset`이 「언급만 있고 전용 절이 없다」(경계 검사기 coverage NOTE 5건)고 지적했다.
- 물리 identity(`SourceAsset`·`MediaStream`·`FrameRef`)와 **lifecycle·provider 경계를 가진 파생물**은 관심사가 다르다. 파생물은 재생성 가능하고 삭제 정책의 대상이며 외부 provider 사본과 얽힌다. 사용자 외부 원본과 lifecycle을 섞지 않으려면 별도 문서가 필요했다(v4 원칙 3 · §8-4).
- `search`는 `AssetSpan`의 storage path/URL을 받지 않고 `AnalysisSource`로 실제 Provider 입력을 얻어야 한다는 것이 recording 계약 §12·B07에서 확정됐지만 `AnalysisSource`의 모양이 없었다.
- `PlateReadout.input_ref.incident_clip_ref`·`ReportPackage.assets.report_video_ref`·`provenance.derived_asset_refs`가 이미 참조하는 타입들이다.

## 2. 소유권과 권위 데이터

| 데이터 | 소유 | 권위 |
| --- | --- | --- |
| 분석 입력(`AnalysisSource`)의 lineage·가용 상태·준비 | `recording` | 계약 필드 + `prepare_analysis_source`/`open_analysis_source` |
| 외부 provider 사본 registry(`RemoteCopy`) — ref·expiry 등록/조회 | `recording` (registry owner) | `(analysis_source_ref, provider)` 조회 키 |
| provider upload/delete API 호출 | `search/providers` | v4 §4-모듈1 ⑦. recording은 반환된 ref·expiry를 등록 |
| 사건 clip(`IncidentClip`) materialization과 생성 근거 | `recording` | `source_provenance`(`timeline_ref.revision` 고정) |
| 신고·보조 파생물(`DerivedAsset`) 생성과 lineage | `recording` | `source_refs[]`·`transform_ref` |
| 파생물이 신고요건을 충족하는가 | `evidence` | 이 계약 밖. 자산 사실은 `AssetFacts` 경유 |
| 사후 timestamp 각인을 허용하는가 | `evidence`(판단) → `case` → `recording`(생성) | v4 §3-2 · Report Video에만 |
| `purge_case` 호출 | `case` | 사용자 외부 원본은 삭제 대상 아님 |

## 3. 현재까지 확정된 설계 (상위 결정에서 온 것)

1. `AssetSpan`에 local path·S3/GCS URI·provider file ID·`RemoteCopy` ID를 넣지 않는다. search는 `prepare_analysis_source`를 거쳐 입력을 얻는다(recording 계약 §12, Accepted).
2. `AnalysisSource`는 search가 실제 Provider 분석 입력으로 쓸 수 있는 형태를 보장한다. `stream_selector` 직렬화는 확정하지 않았다(2026-09-07 B07).
3. Incident Clip과 Report Video는 다르다. 사후 각인은 Report Video에만(v4 §7-3·§3-2).
4. 실패 경계: 파일 하나 probe 실패 → 해당 source만 · stream decode 실패 → 다른 stream 생존 · clip/export 실패 → Search/Evidence 결과 생존 · RemoteCopy 만료 → 재준비 가능, 기존 `AnalysisRun` 생존(v4 §4-모듈1 ⑨).
5. `purge_case`는 `ExternalSourceRef`의 사용자 원본을 삭제하지 않는다. provider가 delete API를 지원하면 `search/providers`가 호출하고, 미지원이면 expiry까지 남는다는 사실을 기록한다(v4 §8-4 · 보안 검수 #15·#16).
6. upload 방식·proxy profile 값·retention 일수·provider별 delete 방식은 v4에서도 미결이며 임의 확정하지 않는다(v4 §5-3 A6).
7. 자산 사실은 `AssetFacts`(짝 계약 §6) 한 정의를 쓴다.

## 4. Draft가 새로 제안한 설계 (Consumer Review 대상)

- 네 타입의 ref 접두어(`as_`·`rc_`·`clip_`·`da_`)와 각 스키마 예시.
- `open_analysis_source(ref) -> readable media stream` capability(v4 ⑥ 목록에는 없던 추가).
- `RemoteCopy` registry 키 `(analysis_source_ref, provider)` · coarse/fine 재사용 · expiry 후 기존 Run 불변.
- `IncidentClip.source_provenance`에 timeline ref·요청 범위·사용한 span 값을 **값으로** 보존(합성 `source_span_ref`를 만들지 않음).
- `DerivedAsset.derived_role`·`transform_ref`·`AnalysisSource.profile_ref`는 필드 자리만 두고 값은 Pending.
- lifecycle 트리(External Source Reference → Managed Source Copy / AnalysisSource / RemoteCopy / IncidentClip / DerivedAsset).

## 5. 고려한 대안과 기각 이유

| 대안 | 기각 이유 |
| --- | --- |
| `AnalysisSource` = 항상 proxy로 고정 | 업로드 전략(원본·부분·proxy)은 실측 후 profile 합의 대상. v4 A6 미결. Draft §10 금지 |
| public 계약에 storage/provider locator 노출을 필수화 | search가 저장소 구조에 결합. 「Search가 내부 저장소 구조를 몰라도 실제 분석 media를 열 수 있는 capability」가 목적 |
| recording이 provider upload/delete를 직접 호출 | AI provider 의존은 `search/providers` 경계(v4 ⑦). recording은 registry만 |
| `IncidentClip`을 Report Video 또는 확정 Evidence로 사용 | v4 §7-3 · evidence Post-stamp 경계 위반 |
| canonical ID가 없는 `AssetSpan`에 합성 `source_span_ref` 부여 | 존재하지 않는 identity를 만들어 Consumer가 파싱·조회하게 됨. 단, 이 선택은 Accepted readout 계약의 `span_ref`와 충돌해 회차가 필요하다(§9) |
| 파생 계약에 `AssetFacts` 재정의 | 규칙 복제. 짝 계약 §6 단일 소유 |

## 6. 불변조건 (Draft §2·§5.2·§6.3·§7.2 요약 — 원문은 계약)

모든 ref opaque · prefix가 종류·role·lineage를 소유하지 않음 · Source/Derived 구분과 lineage 보존 · 외부 원본과 서비스 사본의 lifecycle 분리 · 같은 `AnalysisSource`의 provider별 `RemoteCopy` 분리 · expiry 이후 기존 `AnalysisRun` 의미 불변 · `IncidentClip != AssetSpan != Report Video != confirmed Evidence` · `timeline_ref.revision`으로 provenance 고정 · 파생물 생성 실패가 기존 Search/Evidence 결과를 무효화하지 않음 · clip에 법적 위반·신고 유형·final `occurred_at` 없음.

## 7. 영향을 받는 Producer와 Consumer · Consumer별 확인 필요 항목

Consumer Review 문서는 PM 내부 기록이다. 아래는 확인 항목의 **주제**다.

| Consumer | 확인 필요 주제 |
| --- | --- |
| `search` | `open_analysis_source` 반환 형태가 provider SDK 입력으로 충분한가 · 만료된 `RemoteCopy`의 조회 결과(`null`/객체) · `register_remote_copy`의 `remote_info` 최소 필드 · coarse/fine profile 분리 필요성 · `timeline_range`의 revision 부재 · `duration_sec`과 `usage_summary.processed_duration_ms`의 관계 |
| `readout` | `input_ref.span_ref`의 참조 대상(→ 열린 회차) · clip을 여는 capability 필요 여부 · `source_profile`과 `profile_ref`의 관계 · 복수 stream clip의 판독 stream 선택 소유 · clip 생성 실패의 `ReadoutRun.failure` 표현 |
| `case` | `build_incident_clip` `options`에 case가 넣는 값 · 사용자 수정 시 clip 재발주와 `input_fingerprint` · Report Video 실패의 `CaseView.notices` 표현 · `purge_case` 결과 형태 |
| `evidence` | `derived_role` 최소 목록 · `source_refs[]`에 clip만 있을 때 lineage 재추적 vs 평탄화 · `transform_ref` 없이 각인 확인 가능 여부 · `timeline_range`≠`requested_range`(경계 잘림) 인지 필요성 · `RemoteCopy` 비소비 확인 |

**Consumer Review 기록:** (비어 있음 — 아직 답변 없음)

## 8. 아직 확정하지 않은 내용 (계약 §11 Pending과 PM 검수 추가분)

- 계약 §11 아홉 항목: `profile_ref` 필수성·값 · `stream_selector` 직렬화 · thumbnail 전달 방식 · provider별 upload/delete·즉시 delete · retention · proxy profile 값 · `derived_role` enum · `transform_ref` shape · `build_incident_clip` options.
- PM 검수 추가(2026-09-08 ADR §4.5): `IncidentClip.source_provenance.asset_spans[]`가 Accepted `AssetSpan` 형태(`timeline_range`/`source_range` 초 단위·`sequence`)와 다른 평탄화·ms 표기 · `requested_range`가 `SpanResolution`과 같은 이름·다른 단위 · `source_refs[]`(ContractRef)와 `media_stream_refs[]`(평문) 스타일 혼용 · `RemoteCopy`·`IncidentClip` 필드표 부재 · 헤더/본문 버전 문자열 형식 · `RemoteCopy` 만료와 `availability`의 관계 · 준비/생성 실패의 반환 형태.

## 9. 추가 CALL 발생 조건과 현재 열린 회차

- **열린 회차:** `AssetSpan` identity 부재와 `PlateReadout.input_ref.span_ref`의 참조 대상 — Decider 정철원, 확인 신유민·유소연·김준영, `CALL_REQUIRED`(Accepted 계약 둘과 이 Draft가 서로 다른 전제). 자산 계층 `ContractRef.kind` 표기 — `CALL_REQUIRED`(짝 계약과 공유). 상태는 `adr-data-contract-call-closure-2026-09-08.md` §4.6·§9.
- **새 CALL이 생기는 조건:** profile 태그 값 집합을 recording·search·readout이 나눠 가져야 할 때(Consumer가 `profile_ref`를 필수로 요구하면) · retention·즉시 delete가 보안 검수 #8·#16 판정에 필요해질 때(정철원·서어진·PM) · `derived_role`/`transform_ref`가 evidence 판정 규칙을 recording 계약에 고정하게 될 때. 단일 Owner가 Draft 안에서 고칠 수 있는 항목(단위·표기·필드표)은 CALL 없이 Owner가 반영한다.

## 10. 최종 승인 전 수정하면 안 되는 부분

- §3의 상위 결정 7건 — Consumer Review로 뒤집을 수 없다.
- `AssetFacts`를 이 계약에 복제 정의하지 않는다.
- retention 일수·proxy profile 값·provider delete 방식을 「완성도를 위해」 채우지 않는다(v4 A6).
- Status·수락일 — Consumer 4명의 판정이 기록되고 열린 회차가 닫힌 뒤에만 `Accepted`로 바꾼다.

## 11. 한 줄 요약

> `recording`은 분석 입력·provider 원격 사본 registry·Source-derived 사건 clip·신고 파생물을 서로 다른 opaque identity와 provenance/lifecycle로 관리하고, `search`가 저장소 구조를 몰라도 실제 분석 media를 열 수 있는 capability를 제공하기로 **제안**했다. v4 §4-모듈1·§7-3·§8-4 및 B07 상위 결정과 일치하며, Consumer Review와 identity·표기 회차가 끝나기 전에는 수락되지 않았다.
