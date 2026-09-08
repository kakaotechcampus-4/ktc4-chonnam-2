# ADR — `AnalysisSource` / `RemoteCopy` / `IncidentClip` / `DerivedAsset` Data Contract

**Status:** Accepted — Consumer Review 종결 (2026-09-08)

**Contract:** `../contract-analysis-source-derived.md` (`analysis-source-derived/v1`)
**Producer / Owner:** `recording` — 정철원
**Consumers:** `search` — 서어진 · `readout` — 신유민 · `case` — 유소연 · `evidence` — 김준영
**Architecture:** v4 §5-1 ③ · §4-모듈1 ⑥·⑦·⑨ · §7-3(Incident Clip ≠ Report Video) · §8-4(보관/삭제)
**상위 결정:** `adr-data-contract-call-closure-2026-09-07.md` §4.6(B07 — `AnalysisSource`가 Provider 입력을 보장 · `stream_selector` 미확정) · `adr-data-contract-call-closure-2026-09-08.md` §4.5(Draft 검수) · §4.8(자산 ref `kind` 표기) · §4.9(`AssetSpan` identity와 사건 구간 ref) · §4.10(Consumer Review 종결)
**짝 계약의 공통 정의:** canonical `AssetFacts`는 `contract-source-asset-media-stream.md` §6 — 이 계약은 참조만 한다
**Date:** 2026-09-08 (작성일) · **수락일 2026-09-08** (Consumer Review 4건 종결 후 Owner 정철원 반영)

> 이 ADR은 계약이 **왜 네 의미로 나뉘고 무엇이 확정됐는지**를 남긴다. 스키마는 계약이 소유하고 이 문서는 근거·기각안·Consumer Review 기록만 소유한다. §4는 Draft 단계의 「제안」 기록이고 §1~§3·§5·§6은 그대로다. **Consumer Review 결과와 수락 근거는 §7에 있다.**

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

## 4. Draft가 새로 제안한 설계 (Consumer Review 대상 — 결과는 §7)

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
## 7. Consumer Review 결과 (2026-09-08 종결)

### 7.1 Consumer별 검토 역할

| Consumer | 이 계약에서의 역할 | 검토한 것 |
| --- | --- | --- |
| `search` — 서어진 | 가장 직접적인 Consumer. `prepare_analysis_source` → `AnalysisSource` → provider 업로드 경로의 호출자이고 `RemoteCopy` registry 재사용자 | `open_analysis_source` 반환 형태가 provider SDK 입력으로 충분한가 · 만료된 사본의 조회 결과 · `register_remote_copy` 최소 필드 · profile 분리 필요성 · `timeline_range`의 revision · `duration_sec`과 사용량의 관계 |
| `readout` — 신유민 | `PlateReadout.input_ref.incident_clip_ref`로 `IncidentClip`을 받는 소비자 | 사건 구간 ref의 대상 · clip을 여는 capability 필요 여부 · `source_profile`과 `profile_ref`의 관계 · 복수 stream clip의 판독 stream 선택 소유 · clip 실패의 `ReadoutRun.failure` 표현 |
| `case` — 유소연 | clip 발주·Report Video export orchestration과 `purge_case` 호출 주체. readout 입력 조립(`needs_map`) | `build_incident_clip` options에 case가 넣는 값 · 사용자 구간 수정 시 재발주와 `input_fingerprint` · export 실패의 `CaseView.notices` 표현 · `DeletionReport` 형태 |
| `evidence` — 김준영 | `ReportPackage.assets.report_video_ref`·`provenance.*`를 opaque ref로 조립. 자산 사실은 `AssetFacts` 경유 | `derived_role` 최소 목록 · clip만 있을 때의 lineage 재추적 vs 평탄화 · `transform_ref` 없이 각인 확인 가능 여부 · 경계 잘림 인지 필요성 · `RemoteCopy` 비소비 확인 |

### 7.2 제기된 핵심 우려

1. **같은 개념이 두 모양이었다.** `IncidentClip.source_provenance.asset_spans[]`가 「canonical `AssetSpan` 필드 형태를 따른다」고 선언하면서 예시는 평탄화(`source_start_sec`·`timeline_start_ms`)에 초/ms를 섞어 썼고 `sequence`가 빠져 있었다. 수락된 `AssetSpan`은 `sequence` + `timeline_range{start_sec,end_sec}` + `source_range{start_sec,end_sec}` 중첩이다. evidence는 Source-derived 증명을 `SpanResolution.spans[]`와 clip provenance **두 경로**에서 받으므로 같은 개념이 두 모양이면 판정 코드가 둘로 갈린다. 복수 파일 clip은 `sequence` 없이 순서를 복원할 수 없어 readout도 여기서 막힌다.
2. **같은 이름이 다른 단위였다.** `source_provenance.requested_range`가 ms인데 `SpanResolution.requested_range`는 초였다. recording 공개 경계는 초이고 ms 변환은 경계에서 명시적으로 한다는 원칙과 어긋난다.
3. **사건 구간을 가리키는 ref가 없었다.** canonical `AssetSpan`에는 identity가 없는데, 수락된 `PlateReadout.input_ref.span_ref`와 `EvidenceNeeds` §8.3은 span ref를 전제했다. 수락된 계약 둘과 이 Draft가 서로 다른 전제를 갖고 있었다.
4. **`open_analysis_source`의 반환이 업로드에 부족했다.** stream만으로는 provider 업로드를 만들 수 없고 `content_type`과 실제 `byte_size`가 필요하다. 재시도할 때 같은 ref를 다시 열 수 있어야 하고, 실패는 `NOT_FOUND`/`UNAVAILABLE`/`UNSUPPORTED_MEDIA`/일시 오류를 구분해야 한다.
5. **만료 판단의 소유가 불명확했다.** `find_remote_copy`가 만료된 사본을 돌려주면 search가 provider별 TTL 정책을 해석해야 한다.
6. **`profile_ref`가 optional·값 미정이었다.** `prepare_analysis_source`는 항상 profile을 입력받는데 반환 객체의 `profile_ref`가 nullable이면 search가 재사용 가능 여부를 판단할 수 없다.
7. **timeline 좌표에 revision이 없었다.** 같은 `timeline_id`라도 revision이 바뀌면 같은 offset이 다른 영상을 가리킨다.
8. **failure code가 없었다.** clip 생성·Report Video export 실패를 case가 `CaseView.notices[].code`로 옮기려면 machine-readable 코드가 필요하고, readout은 입력 부재를 `PLATE_ABSTAINED`(입력이 있는 상태의 도메인 결과)와 구분해야 한다.
9. **`DeletionReport`가 이름만 있었다.** `purge_case` 결과를 사용자에게 보여주려면 자산별 결과 형태가 필요하다.
10. **필드 정의표가 없었다.** `RemoteCopy`·`IncidentClip`은 예시만 있고 타입·필수성·nullable 규칙이 없었다.
11. **`kind` 표기와 두 ref 스타일.** 대문자 `kind`(형제 계약과 공유되는 문제)와, 한 객체 안의 `ContractRef[]`/평문 string[] 혼용.
12. **`lineage` 평탄화.** `DerivedAsset.source_refs[]`에 clip만 있을 때 evidence는 recording을 호출할 수 없어 원본을 따라갈 수 없다.

### 7.3 계약에 반영한 변경

| # | 반영 | 계약 위치 |
| --- | --- | --- |
| 1 | `asset_spans[]`를 **canonical `AssetSpan`과 동일한 필드·중첩·단위**로 확정. `sequence` 필수, `timeline_range`/`source_range` 중첩 초 단위, 평탄화 표기 삭제. clip 생성 후 원본 구간을 복원하는 유일한 근거이므로 같은 개념을 두 모양으로 두지 않는다 | §6.3 · §6.4-2 |
| 2 | `source_provenance.requested_range`를 `{start_sec, end_sec}`로 통일 — `SpanResolution`과 같은 이름·같은 단위. `timeline_range`·`AnalysisSource.timeline_range`·`DerivedAsset.timeline_range`도 초 단위 | §6.2 · §6.3 · §4.1 · §7.1 |
| 3 | **`AssetSpan`에 identity를 추가하지 않고** 사건 구간 canonical ref를 `incident_clip`으로 단일화. 합성 `source_span_ref` 금지와 「Consumer가 canonical 값을 결합·해시해 span ref를 발급하는 것」 금지를 함께 명문화. `incident_clip_ref`의 immutability·재발급 규칙(같은 ref = 같은 provenance · 새 provenance = 새 ref · 위치값 인코딩 금지)을 확정. readout 입력에서 `span_ref` 삭제(형제 문서 `plate-readout/v1.2`) · clip 생성 전 `candidate_event` fallback | §6.1 · §6.4-3 · §6.5 · §6.8 · §6.9 |
| 4 | `open_analysis_source`가 `{ stream, content_type, byte_size }`를 반환하고 같은 ref 재호출 시 **처음부터 읽을 수 있는 새 stream**을 준다. local path·인증정보·provider URL은 public 계약에 노출하지 않고 path가 필요한 provider는 `search/providers`가 내부 임시 파일로 변환. 최소 failure code 4종 | §4.2 |
| 5 | `find_remote_copy`는 **조회 시점 `AVAILABLE`이고 만료 전인 사본만** 반환하고, 만료·`UNAVAILABLE`·미등록은 모두 cache miss와 같은 `null`. **만료 판단은 registry Owner인 recording** | §5.3 |
| 6 | `register_remote_copy`의 `remote_info` 최소 필드를 `provider_object_ref`·`expires_at`으로 확정. `remote_copy_ref`와 초기 `availability`는 recording이 부여. 토큰·URL·local path 저장 금지 | §5.3 · §5.2-9 |
| 7 | `profile_ref`를 **필수 non-null**로 변경. profile은 실행 단계가 아니라 media 특성을 표현하고 조건이 같으면 coarse/fine이 같은 자산을 재사용. **canonical 값 공간 소유는 recording.** `profile_ref`는 opaque이며 Consumer는 파싱 없이 동등성 비교만 한다. `source_profile`(readout 라벨)과 다른 개념임을 명시 | §4.4 |
| 8 | `timeline_range != null ⇔ timeline_ref != null` 쌍 규칙을 `AnalysisSource`·`IncidentClip`·`DerivedAsset`에 적용하고 `timeline_ref = {timeline_id, revision}`. Timeline에 속하지 않으면 둘 다 `null` | §4.3 · §6.2 · §7.1 |
| 9 | 최소 failure code 확정 — `INCIDENT_CLIP_BUILD_FAILED` · `REPORT_VIDEO_EXPORT_FAILED`. case는 기존 `CaseView.notices[].code`에 매핑하고 새 `CaseView` 필드를 만들지 않는다. dispatch 후 입력 부재는 `ReadoutRun.failure`의 `kind: INPUT` · `code: INPUT_UNAVAILABLE`이고 `PLATE_ABSTAINED`와 혼용하지 않는다. clip 준비가 job 조립 전에 실패하면 dispatch 자체를 하지 않는다(case 경계) | §9 · §7.5 · §6.8 |
| 10 | `DeletionReport` 최소 구조 신설 — `case_id`·`requested_at`·`completed_at`·`status(COMPLETE\|PARTIAL\|FAILED)`·`items[]{asset_ref, result(DELETED\|NOT_FOUND\|PENDING_EXPIRY\|FAILED), failure_code}`. 외부 원본은 대상 아님, delete 미지원 사본은 `PENDING_EXPIRY`, 일부 실패는 `PARTIAL` | §8.1 |
| 11 | `RemoteCopy`·`IncidentClip`에 타입·필수성·nullable을 포함한 필드표 신설 | §5.1 · §6.2 |
| 12 | 자산 `kind`를 소문자 snake_case로 통일(값 공간은 형제 계약 §2.1 소유). `source_refs[]`(`ContractRef[]`)와 `media_stream_refs[]`(평문 string[])의 스타일 차이가 **의도된 구분**임을 명시 — Consumer는 필드의 계약 타입으로 종류를 판단하고 prefix를 파싱하지 않는다 | §2 · §2.1 |
| 13 | `derived_role` 등재 값 `REPORT_VIDEO`·`PLATE_IMAGE` 확정. `transform_ref`가 non-null이면 **적용된 transform 종류를 machine-readable하게 조회할 수 있다**는 보장 추가(조회 불가 시 evidence는 해당 check를 `UNKNOWN`으로 낸다). 사후 각인은 Report Video에만 | §7.3 · §7.4 · §7.2-7 |
| 14 | **`timeline_range`(실제 materialize)와 `requested_range`(요청)가 다를 수 있음**을 불변조건으로 명시 — 경계 잘림. Consumer는 두 필드 비교로 알 수 있고 허용 폭 판정은 evidence policy 소유 | §6.4-8 |
| 15 | `AssetFacts.lineage[]` 평탄화 규칙은 형제 계약 §6.3이 소유하고 이 계약은 참조. 객체의 `source_refs[]`는 직접 부모, `lineage[]`는 원본까지의 전체 provenance임을 두 곳에서 같은 문장으로 구분 | §3 · §4.1 · §7.1 |
| 16 | `build_incident_clip`의 materialization option은 **recording 소유**. case는 전후 여유 시간을 계산하지 않고 이미 결정된 interval을 전달하며, 사건 범위 정책이 필요하면 evidence가 결정하고 case가 전달 | §6.6 |
| 17 | 사용자 구간 수정(`SPAN_ADJUST`) 시 — case는 `input_fingerprint`를 바꿔 캐시 재사용을 막고, recording은 provenance가 달라지면 새 clip을 발급하며 기존 clip을 mutate하지 않는다 | §6.7 |
| 18 | `evidence`가 `RemoteCopy`를 소비하지 않음을 불변조건으로 확인. `AnalysisSource.duration_sec`은 준비된 전체 길이이고 실제 처리량의 authoritative 값은 `UsageRecord.processed_duration_sec`임을 명시(계약 필드 변경 없음) | §5.2-10 · §4.5 |
| 19 | 헤더와 모든 payload가 `analysis-source-derived/v1` 한 문자열. forward-compatibility·breaking change 규칙과 v0.2 → v1 변경 목록 명문화 | 헤더 · §12 |

### 7.4 반영하지 않은 요청과 이유

| 요청 | 판정 | 이유 |
| --- | --- | --- |
| `AssetSpan`에 canonical identity(`span_id`) 추가 | **기각(대안 채택)** | 한 Consumer가 「수정 파일 수가 적다」는 실용적 이유로 선호했다. 그러나 이 선택은 `AssetSpan`을 immutable value mapping에서 identity·저장·조회·재발급 정책을 가진 자원으로 바꾼다 — 고칠 문서는 적지만 recording의 영속 모델과 책임은 더 크게 변한다. 또한 결정적 발급 규칙이 없으면 재처리 동일성이 깨지고, 있으면 composite key 해시와 같아져 얻는 것이 적다. readout은 독립 span identity가 필요하지 않다고 확인했고, evidence는 clip provenance로 원본 구간을 복원할 수 있다고 확인했고, case도 기능적으로 반대하지 않는다고 확인했다. 선호했던 Consumer 본인이 「recording·readout·evidence가 수정 범위를 감당할 수 있다면 case가 막을 근거는 없다」고 확인했다 |
| `span_ref`를 `SpanResolution` identity로 재정의(`resolution_id` 추가) | **기각** | resolution과 clip이 1:1이 아닐 수 있어 provenance가 한 단계 더 필요하다. 이름이 `span_ref`인데 가리키는 것이 `SpanResolution`이면 필드명도 바꿔야 해서 개정 규모가 채택안과 같아지고, recording과 readout **양쪽**을 고쳐야 한다 |
| `span_ref`라는 이름을 유지하고 `IncidentClip`을 가리키게 의미 재정의 | **기각** | 이름과 대상이 어긋난 필드를 남기지 않는다. 필드를 삭제하고 이미 존재하는 `incident_clip_ref`를 쓴다 |
| profile의 **정확한 값 목록** 확정 | **미반영 — Pending 유지** | recording·search·readout 3자 합의 항목이다. 요청한 Consumer 자신이 3자 합의를 전제로 요청했고, 계약이 확정한 것(필수 non-null · recording 소유 · opaque · 동등성 비교만)만으로 payload를 만들고 소비할 수 있다. 값이 늘어도 breaking이 아니다 |
| `transform_ref`의 exact schema | **미반영 — Pending 유지** | 요청자가 `RECOMMENDED`로 냈고 「조회할 수 있다는 보장 한 줄」이면 충분하다고 했다. 그 보장은 §7.4에 들어갔고, 조회 불가 시의 outcome은 evidence policy 소유다 |
| `derived_role` 전체 enum · 어느 role이 필수인지 | **부분 반영** | evidence 판정에 필요한 2건만 등재했다. 필수성과 부재 시 outcome은 evidence policy 소유이므로 recording 계약에 고정하지 않는다 |
| retention 기간 · provider별 즉시 delete 지원 · proxy resolution/FPS/bitrate | **미반영 — Pending 유지** | v4 A6에서도 미결이고 실측 전이다. 「완성도를 위해」 채우지 않는다. `PENDING_EXPIRY` 결과값으로 delete 미지원 상황은 표현할 수 있다 |
| `stream_selector` 직렬화 · thumbnail 전달 방식 | **미반영 — Pending 유지** | 형제 계약과 같은 이유(§7.4) |
| `build_incident_clip` options schema | **미반영 — Pending 유지** | option 소유가 recording으로 확정됐고, case가 넣을 값이 없다는 것이 확인됐으므로 Consumer 구현이 막히지 않는다 |
| 경계 잘림 허용 폭 · `availability` → outcome 매핑 | **의도적 미반영** | evidence policy 소유. 계약은 「다를 수 있다」는 사실과 비교 가능한 두 필드만 제공한다 |
| `IncidentClip`을 여는 별도 capability(`open_incident_clip`) | **요청 철회** | 요청자가 검토 중 철회했다. 실제 필요한 것은 형제 계약의 `resolve_frame` 신설이었고 그쪽으로 이관됐다. 이 계약은 clip이 canonical `AssetSpan` provenance를 완전하게 제공한다는 것까지만 보장한다 |

### 7.5 조건부 승인 조건의 충족 근거

| Consumer | 판정과 승인 전제 | 충족 | 근거 위치 |
| --- | --- | --- | --- |
| `search` | 변경 요청 — `open_analysis_source` 반환·실패 형태 | 충족 | §4.2 |
| | 만료 사본은 `null`, 판단은 recording | 충족 | §5.3 |
| | `remote_info` 최소 필드 | 충족 | §5.3 |
| | `profile_ref` 필수 non-null + 값 공간 소유(값은 3자 합의) | 충족 | §4.4 |
| | `timeline_ref` 쌍 규칙 | 충족 | §4.3 |
| | 자산 `kind` 정확 문자열 | 충족 | §2 · 형제 계약 §2.1 |
| `readout` | `APPROVE_WITH_CHANGES` 전제 = 입력 실패 taxonomy가 `PLATE_ABSTAINED`와 구분되는 `ReadoutRun.failure`로 매핑 | 충족 | §6.8 · §9 |
| | (확인) 사건 구간 ref = `incident_clip_ref`, `span_ref` 삭제 | 충족 | §6.8 |
| | (확인) clip provenance에 `sequence`·canonical 구조·초 단위 | 충족 | §6.3 |
| `case` | `APPROVE_WITH_CHANGES` — Owner 내부 불일치(span 형태·단위) 정리 | 충족 | §6.3 |
| | `options`·failure code·`DeletionReport`를 명시적으로 연결·확정 | 충족 | §6.6 · §9 · §8.1 |
| | `SPAN_ADJUST` 시 캐시 무효화 책임 명확화 | 충족 | §6.7 |
| `evidence` | `timeline_range`의 모양과 `timeline_ref`(또는 `null` 규칙) | 충족 | §4.3 · 형제 계약 §6.4 |
| | `availability` 3값의 부여 조건 | 충족 | 형제 계약 §3.5 |
| | lineage 최소 구성(원본 계열 1건 이상 · 「모름」을 빈 배열로 표기 금지) | 충족 | 형제 계약 §6.3 |
| | 자산 `kind` 확정 + `asset_kind` 대응표 | 충족 | 형제 계약 §2.1 · §6.2 |

**판정.** `case`는 `APPROVE_WITH_CHANGES`였고 나머지 셋은 `CHANGES_REQUIRED`에 승인 전제를 붙였다. Owner(정철원)가 전제를 전부 수용해 반영했으므로 **조건 충족**으로 판정하고 계약을 `Final — Accepted`, 이 ADR을 `Accepted`로 전환했다. 종합 판정과 남은 항목의 비차단 근거는 `adr-data-contract-call-closure-2026-09-08.md` §4.10이 함께 기록한다.

### 7.6 구현에서 확인해야 하지만 계약 승인을 막지 않는 항목

- `open_analysis_source`의 stream이 실제 provider SDK 입력으로 충분한지 — provider adapter는 `search/providers` 소관이고 실행 코드가 없다.
- `find_remote_copy`의 만료 판정이 provider 실제 expiry와 어긋나는 경계(clock skew) 처리.
- 복수 파일 경계를 넘는 clip materialization의 실제 프레임 정확도.
- `DeletionReport`의 `PENDING_EXPIRY` 항목을 사용자에게 어떻게 표현할지 — `CaseView` projection 문구는 case·web 소관이다.
- `input_fingerprint` 알고리즘 — 별건으로 미결 유지다.
- profile 값이 정해진 뒤 coarse/fine이 실제로 같은 자산을 재사용하는지.

## 8. 아직 확정하지 않은 내용

계약 §11 Pending과 같다 — profile 값 목록(3자 합의) · `stream_selector` 직렬화와 기본 선택 정책 · thumbnail 전달 방식 · provider별 upload/delete·즉시 delete·retention · proxy resolution/FPS/bitrate · `derived_role` 추가 값 · `transform_ref` exact schema · `build_incident_clip` options schema.

**2026-09-08 Consumer Review에서 닫힌 항목**(이전 판본의 이 절에 있었다): `profile_ref` 필수성 · `asset_spans[]`의 형태·단위·`sequence` · `requested_range`의 이름/단위 충돌 · `source_refs[]`와 `media_stream_refs[]` 스타일 혼용의 근거 · `RemoteCopy`·`IncidentClip` 필드표 · 헤더/본문 버전 문자열 · `RemoteCopy` 만료와 `availability`의 관계 · 준비/생성 실패의 반환 형태 · `derived_role` 등재 2건 · transform 조회 가능성 보장.

## 9. 추가 결정 회차 발생 조건

- **열린 회차: 없다.** `AssetSpan` identity ↔ 사건 구간 ref 회차와 자산 `kind` 표기 회차는 2026-09-08에 종결됐다(`adr-data-contract-call-closure-2026-09-08.md` §4.8·§4.9).
- **새 회차가 생기는 조건:** ① profile 값 집합의 3자 합의가 성립하지 않을 때(정철원·서어진·신유민) ② retention·즉시 delete가 보안 검수 #8·#16 판정에 필요해질 때 ③ `derived_role`/`transform_ref`가 evidence 판정 규칙을 recording 계약에 고정하게 될 때 ④ Consumer가 다른 Owner의 수락된 계약 변경을 요구할 때. 단일 Owner가 계약 안에서 고칠 수 있는 항목(단위·표기·필드표·예시)은 회차 없이 Owner가 반영한다.

## 10. 이후 변경 시 지켜야 하는 것

- §3의 상위 결정 7건 — 이 계약 개정으로 뒤집을 수 없다.
- `AssetFacts`와 자산 계층 `kind` 값 공간을 이 계약에 복제 정의하지 않는다(형제 계약 §6·§2.1 소유).
- retention 일수·proxy profile 값·provider delete 방식을 「완성도를 위해」 채우지 않는다(v4 A6).
- **`AssetSpan`에 identity를 만들지 않는다.** 합성 span ref와 Consumer 측 span ref 발급 금지는 이 회차의 결정이며 뒤집으려면 새 결정 회차와 변경 ADR이 필요하다.
- 이 ADR은 수락됐으므로 본문을 고치지 않는다. 표기 보정만 예외다(`README.md`).
- `Final` 이후의 breaking change는 major version과 migration이 필요하다.

## 11. 한 줄 요약

> `recording`은 분석 입력·provider 원격 사본 registry·Source-derived 사건 clip·신고 파생물을 서로 다른 opaque identity와 provenance/lifecycle로 관리하고, 사건 구간의 canonical reference를 `incident_clip` ref로 단일화하며(`AssetSpan`에는 identity를 두지 않는다), `search`가 저장소 구조를 몰라도 실제 분석 media를 열 수 있는 capability를 제공한다. v4 §4-모듈1·§7-3·§8-4 및 B07 상위 결정과 일치하며, 4 Consumer의 필수 조건이 모두 반영되어 2026-09-08 수락됐다.
