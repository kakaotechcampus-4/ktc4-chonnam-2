# CONTRACT_CONFLICTS — Mock Pack 생성 전 Contract 정합성 문제 목록

이 문서는 Mock을 만들기 위해 Contract를 임의로 해석하거나 바꾼 지점이 없다는 것을 보여주기 위한 기록이다. 아래 항목은 이번 Mock Pack 생성에서 **해결하지 않았고**, Mock은 이 항목들이 요구하지 않는 범위에서만 만들었다.

## 1. 이미 알려진 BLOCK/Pending (재확인, 새로 만들지 않음)

원본: `../architecture/contracts/adr/adr-consistency-followup-2026-09-06.md` §3. 이번 작업은 이 표를 다시 만들지 않고 그대로 인용한다.

| ID | 내용 | 이 Mock Pack이 한 일 |
| --- | --- | --- |
| B01 | CaseView `evidence.*_display`의 `needs_review` 생산 규칙·`occurred_at`→EvidenceValue 변환·위치 대표값·`source_label_key` 전달이 Pending | 두 시나리오의 `case_view.*.json`은 이 파생 규칙을 코드로 재현하지 않고, 계약 §8/§9가 이미 예시로 든 값의 형태만 재사용했다. 새 파생 로직을 만들지 않았다 |
| B02 | `requirements.scope`/`readiness`의 CaseView projection 선택 규칙(현재 basis, 동일 scope 이력)이 Pending | Happy 시나리오는 `scope=FINAL_PACKAGE`+`readiness=WARN`, Partial 시나리오는 `scope=EVIDENCE`+`readiness=BLOCK`로 **하나의 basis만** 표현했다. "동일 scope 이력" 다중 버전 표현은 만들지 않았다 |
| B03 | 판독 결과 → ReadoutRun 연결 위치, 공통 `Observation.run_ref` 표현이 Pending | `PlateReadout`/`OverlayTimeReadout`이 자신을 생성한 `run_id`를 보존한다는 계약 §5 규칙만 따랐고, `Observation<T>.produced_by.run_ref`를 readout 실행에 연결하는 새 매핑은 만들지 않았다 |
| B05 | `UsageRecord`가 `ReadoutRun`을 참조하는 방식이 Pending | `usage_records.*.json`의 readout 관련 행은 계약 §7의 공식 예시(`run_ref: null`, `execution_ref`만 사용)를 그대로 따랐다. `run_ref`를 ReadoutRun에 연결하는 새 정책은 만들지 않았다 |
| B06~B09 | SpanResolution 요청 범위 완전성·실제 자산 metadata·상대 입력·사용 revision 연결이 Pending | `span_resolution.*.json`은 opaque id(`sa_`/`ms_`)와 `mock-pack-v1-refs.md`의 ref 작업 규약만 썼다. 실제 자산 lookup이 가능한 것처럼 만들지 않았다 |
| B11 잔여 / B12 잔여 | PM 추가 결정 순서·최초 Accepted 날짜 확인 대기 | Mock 생성과 무관 — 그대로 둠 |
| W02 잔여 | v1.1의 네 evidence 필드(`case_type_display`/`report_type_display`/`violation_display`/`preview_ref`) 삭제 의도 미확정 | 두 시나리오의 CaseView는 이 네 필드를 **계속 포함**했다(계약이 아직 삭제를 확정하지 않았으므로 유지가 보수적 선택) |
| W04 잔여 | JobExecution/UsageRecord의 실제 Consumer 확인·domain PARTIAL↔runtime status 접합 미확정 | `job_executions.*.json`은 `status`만 채우고 `case`/`eval`이 이걸 자기 domain 상태로 어떻게 번역하는지는 만들지 않았다 |
| W07 잔여 | `thumb_ref`가 가리키는 자산 종류(`fr_`/`da_`), recording 자산 계약 2건 부재 | `thumb_ref`는 `fr_h001_thumb`처럼 opaque id로만 채웠다 |
| N02 | `CorrectionRecord` Draft 리뷰·`target_field` 값 공간, taxonomy Owner 확정 | 이번 Seed Pack에서는 `CorrectionRecord` fixture를 **아예 만들지 않았다**(§3 참고) |

## 2. 존재하지 않는 Contract (Mock 생성 불가로 분류)

- `contract-source-asset-media-stream.md` (`SourceAsset`/`MediaStream`/`FrameRef`) — 파일 자체가 없음. `sa_`/`ms_`/`fr_` opaque id만 참조했고, 이 객체들의 필드 스키마 fixture는 만들지 않았다.
- `contract-analysis-source-derived.md` (`AnalysisSource`/`RemoteCopy`/`IncidentClip`/`DerivedAsset`) — 파일 자체가 없음. `clip_`/`da_` opaque id만 참조했다.

## 3. Draft 상태 Contract — Seed Pack에서 제외

- `CorrectionRecord` (`contract-correction-record.md`) — Status: `Draft — Consumer Review 대기`. `evidence`(김준영)의 정식 Consumer Review가 진행되지 않았고, `target_field` 값 공간 자체가 "[추가검토 필요]"로 표시되어 있다. Draft를 기준으로 Mock을 만들면 나중에 Final과 어긋날 가능성이 높아 Seed v0에서는 만들지 않았다. `TimeResolution.considered[].input_ref`가 `{kind: correction_record, ref: ...}` 형태로 이걸 참조할 수 있다는 것만 계약 원문에 있고, 실제 예시 fixture는 v1(Draft가 닫힌 뒤)로 미룬다.

## 4. 이번 Consistency Check에서 새로 발견한 것 (해결하지 않고 기록만 함)

이 절은 이미 알려진 위 1~3과 별개로, 14개 계약을 나란히 놓고 봤을 때 새로 눈에 띈 점이다. **Mock 생성 편의로 통일하지 않았고**, 각 계약 원문 그대로 fixture에 반영했다.

- **"실행/판정 결과" 필드명이 계약마다 다르다.** 같은 "이게 어떻게 끝났는가"라는 개념을 `AnalysisRun`/`ReadoutRun`은 `outcome`, `JobExecution`/`TimeResolution`/`Observation`/`SpanResolution`은 `status`, `RequirementReport`는 `overall`이라는 서로 다른 필드명으로 표현한다. 값 공간도 제각각이다(`SUCCEEDED/PARTIAL/FAILED` vs `OK/NEEDS_REVIEW/UNKNOWN/ERROR/NOT_APPLICABLE` vs `PASS/WARN/BLOCK/UNKNOWN` vs `COMPLETE/PARTIAL/FAILED`). 특히 `SpanResolution.status=COMPLETE`는 다른 계약들의 "정상" 값인 `SUCCEEDED`/`OK`/`PASS`와 이름이 다르다 — 같은 "정상 완료"를 뜻하지만 문자열이 다르다.
- **Primary identifier 명명 관례가 모듈 경계로 나뉜다.** `recording`/`search`/`readout`/`case` 쪽 계약은 자기 자신의 식별자를 `*_id`로 쓴다(`timeline_id`, `candidate_id`, `run_id`, `job_id`, `execution_id`, `usage_id`, `readout_id`, `correction_id`). 반면 `evidence` 쪽 계약(`EvidenceRecord`/`RequirementReport`/`ReportPackage`/`TimeResolution`)은 자기 자신의 식별자도 `*_ref`로 쓴다(`record_ref`, `requirement_report_ref`, `package_ref`, `resolution_ref`). 값 공간이 겹치는 문제는 아니지만 "이 필드가 자기 ID인지 남의 것을 가리키는 참조인지" 신규 인원이 헷갈리기 쉬운 지점이다.
- **`JobRecord.kind`의 실제 값 개수 불확실.** 계약은 "확인된 값: `COARSE_SEARCH`, `PLATE_READ`"라고만 하고 "전체 목록은 모듈 접두어 규칙에 따라 계속 등재(닫힌 enum 아님)"이라고 되어 있다. 하지만 `ReadoutRun.operation`에는 `PLATE_READ` 외에 `OVERLAY_TIME_READ`가 이미 확정 값으로 존재한다 — 그런데 이에 대응하는 `JobRecord.kind` 값이 계약에 없다. 이번 Mock에서는 **"하나의 `PLATE_READ` Job이 `PlateReadout` + `OverlayTimeReadout` 두 ReadoutRun을 함께 만든다"고 가정**하고 `job_h001_plate` 하나의 `JobExecution.produced`에 두 `readout_run` ref를 모두 넣었다. 이건 Mock을 만들기 위한 **임시 가정이며 Contract가 확정한 것이 아니다** — 실제로는 `OVERLAY_TIME_READ`용 `JobRecord.kind`가 별도로 필요할 수도 있다. → **Architecture 확인 필요** 항목으로 별도 기록.

## 5. Fixture 생성 불가 (그대로 둔 것)

- 위 §2의 두 계약이 없는 이상, `SourceAsset`/`MediaStream`/`FrameRef`/`IncidentClip`/`DerivedAsset` 자체를 표현하는 fixture는 만들 수 없다. `data/mock/`의 모든 recording 자산 참조는 opaque id 문자열일 뿐이다.
- `CorrectionRecord` fixture 없음 (§3).
