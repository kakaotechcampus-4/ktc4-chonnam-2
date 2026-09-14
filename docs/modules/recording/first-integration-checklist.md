# 정철원 1차 완료 체크리스트

> 기준: 최신 `develop`의 Product Spec, Module Architecture, R&R, Final Data Contract, 관련 ADR, Mock Pack v5
>
> 목적: 내부 구현 방식을 설계하는 문서가 아니라, 1차 Mock E2E 통합 전에 `recording`과 담당 구현인 `common/runtime JobExecution`이 통합 가능한 상태인지 판정하는 문서다.

---

## 회의에서 먼저 볼 핵심

- [ ] `scenario_happy_001`에서 `SourceAsset`, `MediaStream`, timeline, 사건 clip, 분석용·신고용 자산을 Contract 형식으로 반환할 수 있다.
- [ ] 여러 `SourceAsset` 경계를 지나는 요청을 `resolve_span()`으로 해소하고 순서가 보존된 `AssetSpan[]`을 반환할 수 있다.
- [ ] `scenario_relative_rebase_001`에서 relative-only timeline을 정상 처리하고 rebase와 PARTIAL gap을 표현할 수 있다.
- [ ] `resolve_frame()`으로 발급한 opaque `FrameRef`를 `read_frame()`으로 다시 조회할 수 있다.
- [ ] `scenario_infra_failure_001`에서 `JobExecution`의 STALE, 재시도, FAILED, CANCELLED, SUCCEEDED를 구분할 수 있다.

---

## 담당 범위

| 구분 | 내용 |
| --- | --- |
| Owner | 정철원 |
| 주 담당 Module | `recording` |
| 보조 담당 Module | `common/runtime`의 `JobExecution` 구현 |
| JobExecution Contract Owner | 김준영 |
| Producer로 책임지는 Contract | `SourceAsset`, `MediaStream`, `FrameRef`, `AssetFacts`, `RecordingTimeline`, `TimeSourceCandidate`, `AssetSpan`, `SpanResolution`, `AnalysisSource`, `RemoteCopy`, `IncidentClip`, `DerivedAsset`, `DeletionReport` |
| 구현 책임이 있는 타 Owner Contract | `JobExecution` |
| Consumer로 사용하는 Contract | `JobRecord`, recording 호출에 필요한 timeline/span locator와 자산 ref, Worker가 반환하는 canonical 결과 ref, `UsageRecord` ref |
| 주요 Consumer | search, readout, case, evidence(case 경유), eval, web(CaseView 경유) |
| 주요 Producer 의존성 | case의 `JobRecord`, domain Worker 결과, UsageRecord 생산 경계, source/storage/provider Stub |

### 책임 경계

- `recording`은 파일, stream, frame, timeline, 구간, 자산 provenance와 픽셀 접근 경계를 책임진다.
- 위반 유형, 법적 판단, 신고 요건, 최종 발생 시각 선택, AI 모델 및 prompt는 결정하지 않는다.
- evidence와 web은 recording을 직접 호출하지 않는다.
- provider upload/delete API 호출은 `search/providers` 책임이다.
- recording은 `RemoteCopy` registry와 provider-compatible 자산 경계를 책임진다.
- JobExecution은 실행 lifecycle만 표현한다.
- 작업의 필요성과 재실행 의도는 `JobRecord`를 소유한 case가 결정한다.

---

## 1차 완료 정의

공용 Mock Pack v5를 기준으로 source/stream 등록, timeline 구성, span·frame 해소, AnalysisSource와 사건 clip·파생 자산 제공을 수행하고 Final Data Contract 형식의 결과를 반환할 수 있어야 한다.

relative-only, rebase, gap, UNKNOWN 및 Job의 STALE/FAILED/CANCELLED 상황에서도 identity, revision, provenance와 부분 결과 의미를 보존해야 한다.

Consumer가 내부 구현을 몰라도 연결할 수 있는 공개 entry와 JSON Artifact, smoke/contract test 결과를 Merge 회의에서 제시할 수 있으면 1차 완료로 본다.

---

## 구현 체크리스트

### A. Input

- [ ] `data/mock/recording/scenario_*.json` 7개를 테스트 입력 또는 동일 효과의 Stub으로 사용할 수 있다.
- [ ] 하나의 `SourceAsset`에 포함된 여러 video/audio `MediaStream`을 별도 identity로 처리한다.
- [ ] 자산 계층 `ContractRef.kind`를 소문자 snake_case로 정확히 비교한다.
- [ ] ref prefix를 파싱해 종류나 역할을 추론하지 않는다.
- [ ] `TIMELINE_POSITION`과 `STREAM_POSITION` Frame locator를 구분한다.
- [ ] 두 locator 형태의 필드가 섞인 입력을 거부할 수 있다.
- [ ] `resolve_span()`이 `{timeline_id, revision}`과 초 단위 범위를 받을 수 있다.
- [ ] `AnalysisSource.profile_ref`를 필수·non-null·opaque 값으로 처리한다.
- [ ] JobExecution entry가 `JobRecord.job_id`, `case_rev`, attempt와 실행 대상을 받을 수 있다.

### B. Core Flow

- [ ] `SourceAsset.media_stream_refs[]`와 `MediaStream.source_asset_ref`가 일치한다.
- [ ] `build_timeline()`이 파일 경계와 stream 구성을 보존한 timeline을 생성한다.
- [ ] `resolve_span()`이 여러 파일 경계를 순서대로 연결한 `AssetSpan[]`을 반환한다.
- [ ] `resolve_frame()`으로 최초 FrameRef를 발급할 수 있다.
- [ ] `read_frame(frame_ref)`로 실제 또는 Stub frame을 조회할 수 있다.
- [ ] 동일 MediaStream의 동일 canonical frame을 재조회하면 같은 FrameRef를 반환한다.
- [ ] `prepare_analysis_source()` 결과를 반복해서 처음부터 읽을 수 있다.
- [ ] `build_incident_clip()`이 canonical AssetSpan provenance를 포함한 IncidentClip을 생성한다.
- [ ] Happy Path에서 `REPORT_VIDEO`와 `PLATE_IMAGE` DerivedAsset을 제공한다.
- [ ] 파생 자산에 대응하는 `AssetFacts`를 제공한다.
- [ ] 하나의 `job_id`에 여러 attempt를 서로 다른 `execution_id`로 기록한다.

### C. Output Contract

- [ ] 모든 공개 출력에 해당 `contract_version`과 필수 필드가 존재한다.
- [ ] 모든 ID와 ref는 opaque identity로 처리한다.
- [ ] ID에 timeline 위치, stream role 또는 offset을 인코딩하지 않는다.
- [ ] `RecordingTimeline`의 `timeline_id + revision`을 함께 보존한다.
- [ ] 사용한 시각 후보와 anchor 상태를 보존한다.
- [ ] `AssetSpan.sequence`는 0부터 연속 증가한다.
- [ ] `spans + missing_ranges`가 요청 범위를 빠짐없이 설명한다.
- [ ] 같은 MediaStream의 span이 중복되지 않는다.
- [ ] 다른 MediaStream의 동일 시간대 span은 정상적으로 허용한다.
- [ ] IncidentClip의 `source_provenance.asset_spans[]`는 별도 `span_id`가 없는 canonical AssetSpan 구조다.
- [ ] recording 공개 구간에는 초 단위를 사용한다.
- [ ] `timeline_range`와 `requested_range`가 다르면 잘림 사실을 보존한다.
- [ ] `AssetFacts.asset_ref.kind`, `asset_kind`, 실제 대상 의미가 일치한다.
- [ ] `availability=AVAILABLE`이면 `byte_size`가 non-null이다.
- [ ] 모르는 크기나 duration을 0으로 만들지 않는다.
- [ ] `AssetFacts.timeline_ref`와 `timeline_range`가 쌍으로 존재하거나 함께 null이다.
- [ ] `DerivedAsset.source_refs[]`는 직접 부모를 가리킨다.
- [ ] `AssetFacts.lineage[]`는 원본까지 평탄화된 provenance를 제공한다.
- [ ] JobExecution이 v1.1 필수 필드를 모두 반환한다.
- [ ] JobExecution에 비용 금액을 중복 저장하지 않는다.
- [ ] UsageRecord는 `usage_refs[]`로만 연결한다.

### D. Failure / Partial / Uncertainty

- [ ] absolute anchor가 없다는 이유만으로 relative-only timeline을 실패 처리하지 않는다.
- [ ] `scenario_relative_rebase_001`의 gap을 `PARTIAL`과 `TIMELINE_GAP`으로 표현한다.
- [ ] timeline 경계 밖 구간은 `OUT_OF_TIMELINE_RANGE`로 구분한다.
- [ ] `MissingRange.source_ref` 키를 항상 포함한다.
- [ ] `source_ref` 값은 reason별 nullable 규칙을 따른다.
- [ ] SpanResolution FAILED에서는 top-level `failure`가 non-null이다.
- [ ] 위치를 특정할 수 없는 FAILED에서는 계약이 허용하는 빈 `missing_ranges`를 사용한다.
- [ ] GPS source 부재를 좌표 0이나 임의 좌표로 만들지 않는다.
- [ ] GPS 부재를 `Observation.status=UNKNOWN`과 reason으로 표현한다.
- [ ] 한 stream의 decode 실패가 다른 stream이나 SourceAsset 전체를 자동 실패시키지 않는다.
- [ ] clip/export 실패가 기존 Candidate나 Evidence를 삭제하지 않는다.
- [ ] 공개 capability 실패를 machine-readable code로 반환한다.
- [ ] STALE과 FAILED를 구분한다.
- [ ] STALE execution이 결과를 만들지 못했다면 `produced=[]`를 허용한다.
- [ ] CANCELLED의 부분 결과를 보존할 수 있지만 SUCCEEDED로 승격하지 않는다.

### E. State / Lifecycle

- [ ] timeline rebase 시 revision을 증가시킨다.
- [ ] 이전 timeline revision payload를 수정하지 않는다.
- [ ] rebase 후에도 기존 FrameRef가 다른 frame을 가리키지 않는다.
- [ ] 기존 IncidentClip 재사용과 새 materialization을 구분한다.
- [ ] 매 호출마다 이유 없이 새 IncidentClip ID를 발급하지 않는다.
- [ ] RemoteCopy를 `(analysis_source_ref, provider)` 의미로 조회한다.
- [ ] 유효한 RemoteCopy를 coarse/fine에서 재사용할 수 있다.
- [ ] RemoteCopy expiry가 과거 AnalysisRun의 의미를 변경하지 않는다.
- [ ] JobExecution은 닫힌 enum 6값을 사용한다.
- [ ] 허용된 상태 전이만 수행한다.
- [ ] attempt는 동일 `job_id` 안에서 1부터 증가한다.
- [ ] 새 attempt마다 새로운 `execution_id`를 사용한다.
- [ ] 현재 `case_rev`와 맞지 않는 결과를 Consumer가 식별할 수 있다.

### F. Integration

- [ ] recording 공개 함수/API 또는 Worker entry가 존재한다.
- [ ] Consumer가 내부 클래스나 저장소 구조를 몰라도 호출할 수 있다.
- [ ] search가 AnalysisSource를 열 수 있다.
- [ ] search가 RemoteCopy registry를 사용할 수 있다.
- [ ] search가 timeline 좌표로 FrameRef를 발급받을 수 있다.
- [ ] readout이 IncidentClip과 stream 좌표로 FrameRef를 발급받을 수 있다.
- [ ] readout이 FrameRef로 frame을 읽을 수 있다.
- [ ] case가 `resolve_span`, `build_incident_clip`, `lookup_asset_facts`, `purge_case` 경계를 호출할 수 있다.
- [ ] evidence에는 case가 조회한 AssetFacts와 recording Observation만 전달한다.
- [ ] evidence가 recording을 직접 호출하지 않는다.
- [ ] Fixture adapter와 실제 구현 entry가 같은 public Contract를 반환한다.
- [ ] 다른 모듈의 내부 객체나 비공개 파일 경로를 직접 참조하지 않는다.

### G. Test / Evaluation

- [ ] Happy Path의 source → timeline → span → asset 참조를 검증하는 contract test가 있다.
- [ ] Empty Scenario가 recording 실패로 오해되지 않는 smoke test가 있다.
- [ ] Relative Rebase Scenario에서 revision 1 보존과 revision 2 생성을 검증한다.
- [ ] Relative Rebase Scenario에서 PARTIAL gap을 검증한다.
- [ ] Infra Failure Scenario의 FrameRef source offset과 readout clip offset을 비교한다.
- [ ] Infra Failure Scenario에서 STALE, retry, FAILED, CANCELLED, SUCCEEDED를 구분한다.
- [ ] ref 파싱 또는 합성에 의존하지 않는지 확인한다.
- [ ] 공용 Mock validator가 통과한다.
- [ ] Contract fixture 검사가 통과한다.
- [ ] Boundary 검사가 통과한다.

### H. Operational

- [ ] public payload와 로그에 local path를 노출하지 않는다.
- [ ] provider credential과 인증정보를 노출하지 않는다.
- [ ] 원본 영상 내용을 불필요하게 로그에 남기지 않는다.
- [ ] Job attempt별 시작·종료 시각과 상태를 확인할 수 있다.
- [ ] 실제 capability/provider 호출이 시작된 경우에만 UsageRecord 경계와 연결한다.
- [ ] dispatch 전 취소를 사용량 발생으로 꾸미지 않는다.
- [ ] 사용자 외부 원본을 overwrite하거나 삭제하지 않는다.

---

## Contract별 완료 조건

### SourceAsset / MediaStream / FrameRef / AssetFacts

- [ ] 정상 Artifact를 생성하고 SourceAsset↔MediaStream 역참조를 만족한다.
- [ ] 파일과 stream identity를 분리한다.
- [ ] `AUDIO`와 camera role을 혼동하지 않는다.
- [ ] `role=UNKNOWN`인 video stream도 정상 identity로 유지한다.
- [ ] `resolve_frame`과 `read_frame`을 분리된 capability로 제공한다.
- [ ] `lookup_asset_facts()`가 정상 자산과 unknown/invalid ref를 구분한다.
- [ ] search, readout, case가 실제 출력 JSON을 읽을 수 있다.

### RecordingTimeline / AssetSpan / SpanResolution / TimeSourceCandidate

- [ ] absolute timeline을 생성할 수 있다.
- [ ] `USABLE_RELATIVE_ONLY` timeline을 생성할 수 있다.
- [ ] 가짜 absolute datetime을 생성하지 않는다.
- [ ] 다중 파일·stream 구간의 순서와 coverage를 보존한다.
- [ ] COMPLETE와 PARTIAL을 공용 fixture로 재현한다.
- [ ] FAILED 직렬화를 contract test로 검증한다.
- [ ] rebase 전 결과의 revision provenance를 보존한다.

### AnalysisSource / RemoteCopy

- [ ] non-null `profile_ref`를 가진 AnalysisSource를 생성한다.
- [ ] 반복 호출마다 처음부터 읽을 수 있는 새 stream을 제공한다.
- [ ] storage locator나 인증정보를 public Contract에 노출하지 않는다.
- [ ] 유효한 RemoteCopy를 조회·등록·재사용할 수 있다.
- [ ] RemoteCopy expiry와 availability를 표현할 수 있다.
- [ ] provider API 호출과 recording registry 책임이 분리되어 있다.

### IncidentClip / DerivedAsset / DeletionReport

- [ ] IncidentClip과 DerivedAsset 정상 Artifact를 생성한다.
- [ ] IncidentClip을 AssetSpan, Report Video 또는 확정 Evidence와 동일시하지 않는다.
- [ ] `REPORT_VIDEO`와 `PLATE_IMAGE`를 `derived_role`로 명시한다.
- [ ] ref prefix로 derived role을 추론하지 않는다.
- [ ] `transform_ref`가 있으면 transform 종류를 machine-readable하게 조회할 수 있다.
- [ ] `purge_case()`가 서비스 관리 자산만 대상으로 한다.
- [ ] 사용자 외부 원본을 DeletionReport 삭제 항목에 포함하지 않는다.
- [ ] 공용 Scenario에 없는 DeletionReport는 Contract test 또는 Stub JSON으로 직렬화를 증명한다.

### JobExecution

- [ ] JobRecord 하나에 여러 attempt를 연결할 수 있다.
- [ ] 6개 status와 시각 필드 nullability를 준수한다.
- [ ] 성공한 domain 결과를 `produced[]` ContractRef로 반환한다.
- [ ] readout 성공 execution 하나가 정확히 하나의 ReadoutRun을 생산한다.
- [ ] STALE로 호출이 끝나지 않은 execution은 `produced=[]`를 허용한다.
- [ ] CANCELLED 부분 결과를 성공 결과로 승격하지 않는다.
- [ ] UsageRecord 금액을 JobExecution에 복제하지 않는다.
- [ ] case와 eval이 fixture와 같은 의미로 실행 결과를 소비할 수 있다.

---

## Scenario별 완료 조건

| Scenario | 내 입력 | 내가 해야 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | SourceAsset 2개, MediaStream 3개, 정상 시각 후보와 범위 | timeline, span, AnalysisSource, clip, 파생 자산, GPS 사실 제공 | COMPLETE SpanResolution, AnalysisSource/RemoteCopy, IncidentClip, DerivedAsset 2개, AssetFacts | 모든 ref와 provenance가 끊김 없이 연결됨 |
| `scenario_empty_001` | 정상 source와 timeline | 검색 전 recording 기반 제공 | SourceAsset, MediaStream, timeline | Candidate가 없다는 이유로 recording 실패를 만들지 않음 |
| `scenario_unknown_abstain_partial_001` | 단일 source, 복수 시각 후보, GPS 부재 | 정상 clip·분석 source와 UNKNOWN 관찰 제공 | IncidentClip, AnalysisSource/RemoteCopy, UNKNOWN GPS, DerivedAsset 2개 | 모르는 GPS·시각 값을 생성하지 않음 |
| `scenario_plate_reread_001` | 기존 clip과 재판독 frame 요청 | 같은 source provenance에서 FrameRef 제공 | IncidentClip, AnalysisSource/RemoteCopy, FrameRef 3개 | 기존 FrameRef 의미를 변경하지 않음 |
| `scenario_correction_rerun_001` | 사용자 시각 정정 이후 재실행 요청 | 기존 timeline·clip provenance 유지 | 기존 timeline revision, IncidentClip, AnalysisSource/RemoteCopy | recording이 correction 값을 final truth로 재판정하지 않음 |
| `scenario_infra_failure_001` | readout 재시도·취소 작업과 frame 좌표 | FrameRef 제공 및 execution 상태 구분 | source offset 602/605/608 FrameRef, STALE/FAILED/CANCELLED/SUCCEEDED | readout offset 2/5/8과 일치하고 상태와 ref가 계약에 맞음 |
| `scenario_relative_rebase_001` | anchor 없는 revision 1과 추가 source가 반영된 revision 2 | relative-only 처리, rebase, gap 해소 | revision 1·2, PARTIAL SpanResolution, TIMELINE_GAP | 과거 revision을 변경하지 않고 gap을 명시함 |

---

## Merge 전 셀프 체크 증빙

- [ ] Happy Path 공개 entry의 입력 JSON
- [ ] Happy Path 출력 JSON
- [ ] 다중 파일 경계 SpanResolution JSON
- [ ] Relative Rebase revision 1·2 JSON
- [ ] PARTIAL missing_ranges JSON
- [ ] GPS source 부재 UNKNOWN JSON
- [ ] `resolve_frame → read_frame` 실행 결과
- [ ] AnalysisSource와 RemoteCopy 등록·조회 결과
- [ ] IncidentClip 결과 JSON
- [ ] REPORT_VIDEO·PLATE_IMAGE DerivedAsset JSON
- [ ] Infra Failure JobExecution 상태별 JSON
- [ ] attempt별 실행 로그
- [ ] smoke/contract test 결과
- [ ] 공용 검증 스크립트 결과
- [ ] Stub으로 남은 경계와 실제 구현으로 교체할 부분을 설명한 메모

---

## Merge 전 확인 질문

1. Happy Path에서 어떤 recording Artifact가 어떤 순서로 생성되는지 Contract와 ref로 설명할 수 있는가?
2. search, readout, case가 각각 내 출력의 어떤 필드와 capability를 사용하는지 알고 있는가?
3. absolute anchor가 없는 정상 timeline과 입력 오류를 구분하는가?
4. timeline rebase 이후에도 기존 Candidate, FrameRef, IncidentClip provenance가 유지되는가?
5. PARTIAL, FAILED, STALE, CANCELLED가 각각 어느 계층의 상태인지 구분하는가?
6. 실제 구현과 Stub 경계를 실행 결과로 설명할 수 있는가?
7. 다른 모듈의 내부 객체나 ref 문자열 구조에 의존하지 않는가?

---

## 접합부 확인

| 접합 상대 | 확인 Contract | 내 역할 | 상대 역할 | Merge에서 확인할 것 |
| --- | --- | --- | --- | --- |
| recording → search | AnalysisSource, RemoteCopy, RecordingTimeline, FrameRef | 분석 자산·timeline·frame 제공 | source 사용, provider copy 사용, Candidate/thumbnail 생산 | profile_ref, revision, FrameRef identity, provider 책임 분리 |
| recording → readout | IncidentClip, FrameRef, MediaStream | clip provenance와 frame 제공 | 번호판·화면 시각 판독 | clip offset과 source offset 대응, incident_clip_ref, frame 안정성 |
| case ↔ recording | SpanResolution, IncidentClip, AssetFacts, DeletionReport | 파일 경계 해소와 자산 결과 제공 | orchestration과 Consumer 전달 | timeline revision, requested/actual range, case의 span 재계산 금지 |
| recording → evidence | AssetFacts, GPS Observation, DerivedAsset | 사실과 provenance 생산 | case가 전달한 사실로 판정 | 직접 호출 금지, UNKNOWN 보존, transform/lineage 조회 |
| case → common/runtime | JobRecord → JobExecution | execution lifecycle 구현 | 작업 의도와 재실행 결정 | job_id, attempt, execution_id, stale 결과 미반영 |
| common/runtime ↔ Worker | JobExecution.produced | Worker 결과 ref 기록 | canonical 결과 생산 | 상태별 produced 의미 |
| common/runtime → case/eval | JobExecution, UsageRecord 연결 | execution과 usage ref 제공 | projection과 평가 | 비용 중복 금지, 상태 해석 일치 |

---

## 부분 완료 / 통합 대기

| 항목 | 현재 어디까지 됨 | 기다리는 내용 | 관련 담당 | Mock 대체 |
| --- | --- | --- | --- | --- |
| 실제 upload/storage | public 자산 의미와 ref 확정 | local/S3 및 대용량 전략 | 김준영·정철원 | 가능 |
| AnalysisSource profile 값 | 필수·opaque 규칙 확정 | 실제 값과 보장 속성 | 정철원·서어진·신유민 | 가능 |
| stream_selector | 책임과 필요성 확인 | exact schema와 기본 선택 | 정철원·서어진·신유민 | 가능 |
| thumbnail 전달 | FrameRef 경계 확정 | web 전달 방식 | 정철원·서어진·유소연·신유민 | 가능 |
| provider upload/delete | registry 계약 확정 | provider별 adapter | 서어진·김준영 | 가능 |
| retention 기간 | 삭제 경계 확정 | 운영 기간과 정책 수치 | 김준영·정철원 | 가능 |
| transform_ref payload | 조회 가능성 확정 | exact payload schema | 정철원·김준영 | opaque ref 가능 |
| build_incident_clip options | capability 확정 | exact options schema | 정철원·case/evidence | 가능 |
| SpanResolution FAILED E2E | 직렬화 확정 | 공용 Scenario 추가 여부 | Mock Pack 담당·Consumer | Contract test 가능 |
| DeletionReport E2E | Contract 확정 | purge 전용 Scenario | case·evidence·Mock Pack 담당 | Stub 가능 |
| 실제 DB Queue/Lease | JobExecution 계약·fixture 확정 | persistence와 Worker 기반 | 김준영·정철원 | in-memory 가능 |

통합 대기 항목은 1차 Mock Merge를 자동으로 막지 않는다. 임시 public 필드를 만들어 해결하지 않으며, 실제 접합에 새로운 필드가 필요하면 `Contract 변경 검토 필요`로 별도 제기한다.

---

## 1차 완료 제외 범위

- 모든 블랙박스 제조사·codec·손상 파일 대응
- 최종 proxy resolution/FPS/bitrate 최적화
- production 규모의 multipart upload와 storage lifecycle
- 모든 provider upload/delete adapter
- 최종 retention 기간
- 정밀 frame seek/rounding 성능 최적화
- thumbnail 이미지의 최종 web 전달 방식
- 모든 DerivedAsset role 확장
- production DB Queue의 확장성·장애 복구 완성
- BLOCK, INFO_AI_ESTIMATED, 실제 purge 등 전체 E2E 확장
- 최종 보안·관측성·비용 최적화

Stub을 사용하더라도 public Contract, identity, provenance, 상태 의미와 Consumer 연결은 제외하지 않는다.

---

## Merge 중단 기준

- Happy Path 공개 entry가 실행되지 않는다.
- Canonical Contract JSON을 반환하지 못한다.
- Final Contract와 다른 필드명, enum 또는 nullability를 사용한다.
- 필수 ID, revision, provenance 또는 참조가 누락된다.
- 공용 Scenario에서 모듈별 ID가 서로 다르다.
- SourceAsset과 MediaStream을 동일 객체로 취급한다.
- AssetSpan과 IncidentClip을 동일 객체로 취급한다.
- IncidentClip과 Report Video를 동일 객체로 취급한다.
- ref를 파싱·합성하거나 위치·role을 ID에 인코딩한다.
- 가짜 absolute datetime, GPS 좌표, byte size 또는 duration을 생성한다.
- relative-only timeline을 anchor 부재만으로 실패 처리한다.
- PARTIAL gap을 COMPLETE로 반환하거나 missing range를 버린다.
- rebase가 과거 revision, FrameRef 또는 IncidentClip provenance를 변경한다.
- local path, provider locator 또는 인증정보를 public payload에 노출한다.
- STALE, FAILED, CANCELLED를 SUCCEEDED와 동일하게 처리한다.
- stale 결과를 현재 Case 상태에 반영한다.
- Consumer가 내부 객체를 직접 import해야 연결할 수 있다.
- 공용 validator 또는 담당 contract/smoke test가 실패한다.

---

## 검증 명령

현재 공용 문서·fixture 검증:

```powershell
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
$env:PYTHONUTF8='1'; python scripts/check_boundaries.py
```

recording 및 JobExecution 구현 실행·테스트 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples/recording_consumer.py
```

Consumer 예시는 public fixture loader와 `RecordingService`만 사용하며 저장소 내부를 직접 참조하지 않는다. 실제 ffmpeg/provider/storage/DB Queue는 1차 완료 제외 범위로 남는다.

### 1차 구현 검증 결과 (2026-09-14)

- recording·common/runtime 자동 테스트: 전체 통과
- 공용 Mock validator: 전체 통과
- Contract fixture 검사: 전체 통과
- Boundary 검사: 위반 0건
- Happy Path Consumer 예시: Canonical JSON 출력 확인

위 결과는 Mock E2E 기준의 구현 증빙이다. 실제 미디어 처리와 운영 인프라 항목의 완료를 의미하지 않는다.

---

## 회의에서 말할 한 줄 요약

> recording은 블랙박스 Source와 stream을 입력으로 받아 timeline, span, frame, 분석·사건·신고용 자산을 Canonical Contract로 반환하고, common/runtime에서는 JobExecution lifecycle을 구현합니다. Happy Path와 relative rebase PARTIAL, UNKNOWN GPS, 인프라 실패·재시도·취소까지 공용 Mock 기준으로 identity와 provenance가 유지되는지 검증합니다.
