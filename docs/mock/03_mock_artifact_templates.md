# 03. Mock Artifact Templates

이 문서의 JSON은 전부 `data/mock/`의 실제 fixture 파일에서 그대로 옮겼다(재입력하지 않았다). 서로 달라지면 fixture가 맞다. Partial 시나리오 예시는 지면 절약을 위해 파일 경로만 가리키고, 눈에 띄게 다른 값(ABSTAIN/UNKNOWN/PARTIAL 등)만 별도로 보여준다.

## Contract Inventory

| # | Contract | Producer | Consumer | 주요 역할 | 다른 Contract 참조 |
| - | --- | --- | --- | --- | --- |
| 1 | RecordingTimeline | recording (정철원) | search, case, readout, evidence | 여러 SourceAsset을 하나의 논리 시간축에 배치 | TimeSourceCandidate, SourceAsset/MediaStream(미작성) |
| 2 | AssetSpan | recording | search, readout, case, evidence | Timeline 구간 → 실제 Source+Stream+local range 매핑 | SourceAsset/MediaStream(미작성) |
| 3 | SpanResolution | recording (`resolve_span()`) | search, evidence | 구간 요청 결과(성공/부분/실패)를 AssetSpan[]+MissingRange[]로 표현 | RecordingTimeline, AssetSpan |
| 4 | TimeSourceCandidate | recording | evidence | Source 위치 ↔ 절대시각 관찰 후보 | RecordingTimeline |
| 5 | AnalysisScope | case+search 공동 (유소연/서어진) | search | case 상태 → search 입력 파라미터 경계 계약 | (case_id 등 의도적으로 미포함) |
| 6 | AnalysisRun | search (서어진) | case, eval | search public capability 실행 1회 기록 | AnalysisScope, UsageRecord |
| 7 | CandidateEvent | search | case, eval | Recording Timeline 기준 사건 후보 span | AnalysisRun, RecordingTimeline |
| 8 | VisualEvidence | search (서어진) | evidence, readout | Fine/Classification 시각 관찰 (법적 판단 없음) | AnalysisRun, CandidateEvent |
| 9 | PlateReadout | readout (신유민) | case→evidence, eval | 번호판 판독 관찰(association+consensus+abstain) | ReadoutRun, Observation |
| 10 | OverlayTimeReadout | readout | case→evidence, eval | 화면 타임스탬프 OCR+검증 | ReadoutRun, Observation |
| 11 | ReadoutRun | readout (신유민) | case, eval | 판독 실행 1회 성공/부분/실패 기록 | PlateReadout/OverlayTimeReadout, UsageRecord |
| 12 | Observation\<T\> | recording/search/readout 공통 envelope | evidence, case(projection) | 관찰된 사실의 공통 의미 봉투 | AnalysisRun(run_ref) |
| 13 | TimeResolution | evidence (김준영) | case, web(projection) | recording/readout 시간 관찰 + 사용자 보정을 비교해 최종 occurred_at 확정 | Observation, CorrectionRecord(Draft) |
| 14 | EvidenceRecord | evidence (김준영) | case, web(projection) | 현재 authoritative confirmed values의 immutable snapshot | CandidateEvent, VisualEvidence, AssetSpan, TimeResolution, CorrectionRecord(Draft) |
| 15 | EvidenceNeeds | evidence | case | 추가 관찰/판독 필요를 declarative하게 전달 | EvidenceRecord |
| 16 | RequirementReport | evidence (김준영) | case, web(projection) | 신고 규칙 적용 판정(PASS/WARN/BLOCK/UNKNOWN) | EvidenceRecord |
| 17 | ReportPackage | evidence (김준영) | case, web(projection) | 안전신문고 handoff용 confirmed 값+자산 묶음 | EvidenceRecord, RequirementReport |
| 18 | JobRecord (Job Intent) | case (유소연) | common/runtime | 발주 의도(실행 상태 아님) | AnalysisScope |
| 19 | JobExecution | common/runtime (김준영/정철원) | case, web(projection), eval | 실행 lifecycle(QUEUED~STALE) | JobRecord, UsageRecord |
| 20 | UsageRecord | common/runtime (김준영) | case, eval, search | 외부 유료 호출 1건의 사용량+가격 | JobExecution, AnalysisRun |
| 21 | CaseView | case (유소연) | web(유일한 read contract), eval | web이 화면을 그리기 위한 유일한 통합 상태(safe projection) | 거의 전부(간접) |
| — | CorrectionRecord | case (유소연) | evidence | **Draft** — 사용자 직접 수정 이력 | TimeResolution, EvidenceRecord |
| — | SourceAsset/MediaStream/FrameRef | recording | (미작성) | opaque id만 존재 | — |
| — | AnalysisSource/RemoteCopy/IncidentClip/DerivedAsset | recording | (미작성) | opaque id만 존재 | — |

## 데이터 흐름

```
AnalysisScope ─────────────────────────────┐
                                            ▼
RecordingTimeline ──▶ SpanResolution ──▶ AnalysisRun ──▶ CandidateEvent ──▶ VisualEvidence
     │                                                         │                │
     ▼                                                         ▼                ▼
TimeSourceCandidate                                    PlateReadout ◀── ReadoutRun ──▶ OverlayTimeReadout
     │                                                         │                │
     └──────────────────────┬──────────────────────────────────┴────────────────┘
                             ▼
                       Observation<T> (공통 envelope, GPS 등)
                             │
                             ▼
                      TimeResolution ──▶ EvidenceRecord ──▶ EvidenceNeeds
                                              │                  │
                                              ▼                  │ (optional=false면 case가 JobIntent 자동 발주)
                                       RequirementReport ◀────────┘
                                              │
                                              ▼ (scope=FINAL_PACKAGE & PASS/WARN)
                                        ReportPackage
                                              │
        JobRecord ──▶ JobExecution ──▶ UsageRecord (case가 발주, common/runtime이 실행)
                                              │
                                              ▼
                                          CaseView  ──▶ web (유일한 read contract)
```

---

## RecordingTimeline

- Producer: `recording`(정철원) · Consumer: `search`/`case`/`readout`/`evidence`
- 정상 예시 (`data/mock/recording/timeline.happy_001.json`):
```json
{
  "contract": "RecordingTimeline", "contract_version": "recording-timeline/v1",
  "timeline_id": "tl_h001", "revision": 1,
  "time_basis": { "mode": "ABSOLUTE_AND_RELATIVE",
    "working_anchor": { "value": "2026-08-24T18:20:00+09:00", "source_candidate_ref": "tsc_h001_filename", "status": "OK" } },
  "time_source_candidates": ["tsc_h001_filename"],
  "source_placements": [ { "source_asset_ref": "sa_h001_01", "timeline_start_sec": 0.0, "timeline_end_sec": 900.0,
    "media_stream_refs": ["ms_h001_01", "ms_h001_02", "ms_h001_03"] } ],
  "gaps": [], "timeline_status": "USABLE", "produced_by": "recording"
}
```
- 대표 Partial 예시: `data/mock/recording/timeline.partial_001.json` (`timeline_id=tl_p001`, 첫 Source 배치는 0~1200초, `timeline_status=PARTIAL`)
- 핵심 불변조건: `revision>=1`, rebase 시 ID 유지·revision만 증가, `working_anchor`는 final `occurred_at`이 아님
- 사용 Scenario: happy_001, partial_001

## AssetSpan / SpanResolution

- Producer: `recording`(`resolve_span()`) · Consumer: `search`, `evidence`
- 정상 예시(COMPLETE, `data/mock/recording/span_resolution.happy_001.json`):
```json
{
  "contract": "SpanResolution", "contract_version": "span-resolution/v1",
  "timeline_ref": { "timeline_id": "tl_h001", "revision": 1 },
  "requested_range": { "start_sec": 690.0, "end_sec": 708.0 }, "status": "COMPLETE",
  "spans": [ { "sequence": 0, "timeline_range": { "start_sec": 690.0, "end_sec": 708.0 },
    "source_asset_ref": "sa_h001_01", "media_stream_ref": "ms_h001_01",
    "source_range": { "start_sec": 690.0, "end_sec": 708.0 } } ],
  "missing_ranges": []
}
```
- 대표 Partial 예시(`data/mock/recording/span_resolution.partial_001.json`) — `status=PARTIAL`, `missing_ranges`에 `SOURCE_UNAVAILABLE` 1건 포함
- 핵심 불변조건: `COMPLETE`면 `missing_ranges=[]`, `PARTIAL`이면 둘 다 비어있지 않음, `FAILED`면 `spans=[]`
- 사용 Scenario: happy_001(COMPLETE), partial_001(PARTIAL)

## TimeSourceCandidate

- Producer: `recording` · Consumer: `evidence`
- 정상 예시(`data/mock/recording/time_source_candidates.happy_001.json`, 배열 1건):
```json
{ "candidate_id": "tsc_h001_filename", "source_kind": "FILENAME", "source_detail": "MDR_YYMMDD_HHMMSS.AVI",
  "value": "2026-08-24T18:20:00+09:00", "applies_to": { "source_asset_ref": "sa_h001_01", "source_offset_sec": 0.0 },
  "observation_status": "OK", "producer_checks": { "parse_valid": true },
  "provenance": { "producer": "recording", "observed_from": "MDR_260824_182000.AVI" } }
```
- 핵심 불변조건: 실제 시간값이 있을 때만 생성(값 없음은 별도로 `TimeSourceCheck`가 표현하며 이번 Pack엔 별도 fixture로 만들지 않았다 — 두 시나리오 모두 filename time이 존재하는 케이스라서), numeric confidence 없음, immutable
- 사용 Scenario: happy_001, partial_001

## AnalysisScope

- Producer: `case`+`search` 공동(유소연/서어진) · Consumer: `search`
- 정상 예시(`data/mock/search/analysis_scope.happy_001.json`):
```json
{ "scope_id": "scope_h001", "time_ranges": [ { "start": "2026-08-24T09:00:00Z", "end": "2026-08-24T09:40:00Z" } ],
  "target_event_types": ["SOLID_LINE_LANE_CHANGE"], "hint": { "vehicle": "흰색 SUV", "free_text": null },
  "budget": { "max_cost_krw": 300, "max_latency_sec": 180 }, "contract_version": "1.0.0" }
```
- Partial 예시(`data/mock/search/analysis_scope.partial_001.json`) — `hint.vehicle=null`(차량 힌트 없음), `target_event_types=["SIGNAL"]`
- 핵심 불변조건: `case_id`/`selection_rev`/파일 참조/위치를 절대 포함하지 않음, `time_ranges>=1`, `budget`은 scope 전체 단일값
- 사용 Scenario: happy_001, partial_001

## AnalysisRun

- Producer: `search`(서어진) · Consumer: `case`, `eval`
- 정상 예시(SUCCEEDED, `data/mock/search/analysis_run.happy_001.json`):
```json
{ "run_id": "run_h001_search", "operation": "CANDIDATE_SEARCH", "input_ref": { "kind": "ANALYSIS_SCOPE", "ref": "scope_h001" },
  "implementation": { "impl_id": "gemini-candidate-search@c7", "model_ref": "gemini-3.7-flash", "prompt_version": "coarse-c7", "config_version": "search-v2" },
  "outcome": "SUCCEEDED", "started_at": "2026-08-24T18:25:02+09:00", "completed_at": "2026-08-24T18:26:06+09:00",
  "issues": [], "usage_refs": ["usage_h001_1"],
  "usage_summary": { "processed_duration_ms": 300000, "token_usage": { "input_tokens": 14200, "output_tokens": 1200, "total_tokens": 15400 }, "latency_ms": 64000, "total_cost": { "amount": "0.42", "currency": "USD" } },
  "contract_version": "analysis-run-candidate-event/v1" }
```
- Partial 예시(`data/mock/search/analysis_run.partial_001.json`) — `outcome="PARTIAL"`, `issues`에 `SUBRANGE_PROVIDER_TIMEOUT` 1건
- 핵심 불변조건: `completed_at>=started_at`, `FAILED`는 usable Candidate 금지, `PARTIAL`은 `issues.length>=1`
- 사용 Scenario: happy_001(SUCCEEDED), partial_001(PARTIAL)

## CandidateEvent

- Producer: `search` · Consumer: `case`, `eval`
- 정상 예시(`data/mock/search/candidate_events.happy_001.json`, 배열 1건):
```json
{ "candidate_id": "cand_h001", "run_id": "run_h001_search",
  "span": { "timeline_id": "tl_h001", "start_ms": 690000, "end_ms": 708000, "representative_ms": 698000 },
  "rank": 1, "ranking_score": 0.86, "event_type_hint": "SOLID_LINE_LANE_CHANGE",
  "summary": "흰색 SUV가 백색 실선 구간에서 인접 차로로 진입", "uncertainties": [], "thumbnail_ref": "fr_h001_thumb" }
```
- Partial 예시(`data/mock/search/candidate_events.partial_001.json`) — `ranking_score=0.62`, `uncertainties=["대상 차량 식별 모호"]`
- 핵심 불변조건: `run_id`는 생성한 AnalysisRun과 일치, `start_ms<end_ms`, `rank`는 1부터 중복 없이
- 사용 Scenario: happy_001, partial_001

## VisualEvidence

- Producer: `search`(서어진) · Consumer: `case`→`evidence`/`readout`
- 정상 예시(OBSERVED+MATCHED, `data/mock/search/visual_evidence.happy_001.json`):
```json
{ "schema_version": "visual-evidence/v1.0", "visual_evidence_id": "ve_h001", "run_id": "run_h001_search",
  "input_ref": "analysis-input:case_happy_001", "candidate_id": "cand_h001",
  "verification": "OBSERVED", "visual_event_type": "SOLID_LINE_LANE_CHANGE",
  "target": { "association_status": "MATCHED", "described_as": "흰색 SUV", "match_with_hint": true, "association_confidence": 0.83, "track_ref": null, "evidence_refs": ["fr_h001_a"] },
  "primitives": [ { "kind": "WHITE_SOLID_LINE", "state": "PRESENT", "confidence": 0.9, "evidence_refs": ["fr_h001_a"] } ],
  "temporal_facts": [ { "at_offset_ms": 698000, "fact": "TARGET_CROSSES_LINE", "evidence_refs": ["fr_h001_a"] } ],
  "uncertainties": [], "legal_status": null }
```
- Partial 예시(`data/mock/search/visual_evidence.partial_001.json`) — `target.association_status="AMBIGUOUS"`, `uncertainties`에 `TARGET_AMBIGUOUS` 1건
- 핵심 불변조건: `legal_status`는 항상 null, `OBSERVED`면 `visual_event_type != null`, `track_ref==null`도 정상
- 사용 Scenario: happy_001(MATCHED), partial_001(AMBIGUOUS)

## ReadoutRun

- Producer: `readout`(신유민) · Consumer: `case`, `eval`
- 정상 예시(`data/mock/readout/readout_runs.happy_001.json`, 배열 2건 중 1건):
```json
{ "run_id": "rr_h001_plate", "operation": "PLATE_READ", "outcome": "SUCCEEDED", "failure": null,
  "usage_refs": ["usage_h001_2"], "started_at": "2026-08-24T18:31:00+09:00", "ended_at": "2026-08-24T18:31:07+09:00" }
```
- Partial 예시(`data/mock/readout/readout_runs.partial_001.json`) — **`outcome`은 여전히 `SUCCEEDED`다**(abstain은 실패가 아님, §9 불변조건 5번)
- 핵심 불변조건: `abstained+reason`은 실패가 아니다 — SUCCEEDED로 센다. `PARTIAL`/`FAILED`만 `failure` 필수
- 사용 Scenario: happy_001, partial_001

## PlateReadout

- Producer: `readout` · Consumer: `case`→`evidence`, `eval`
- 정상(비abstain) 예시(`data/mock/readout/plate_readout.happy_001.json`, 요약):
```json
{ "readout_id": "readout_h001_plate", "case_id": "case_happy_001", "candidate_id": "cand_h001",
  "observation": { "kind": "PLATE", "status": "OK", "value": "12가 3476", "provenance": "SOURCE_DERIVED_INCIDENT_CLIP" },
  "consensus": { "text": "12가 3476", "disagree_positions": [], "method": "MULTI_FRAME" },
  "abstained": false, "abstain_reason": null }
```
- ABSTAIN 예시(`data/mock/readout/plate_readout.partial_001.json`, 요약):
```json
{ "readout_id": "readout_p001_plate",
  "observation": { "kind": "PLATE", "status": "NEEDS_REVIEW", "value": "12나 34?6", "provenance": "SOURCE_DERIVED_INCIDENT_CLIP" },
  "consensus": { "text": "12나 34?6", "disagree_positions": [5], "method": "MULTI_FRAME" },
  "abstained": true, "abstain_reason": "FRAME_DISAGREEMENT" }
```
- 핵심 불변조건: single-frame confidence만으로 자동 확정 금지, 애매하면 abstain
- 사용 Scenario: happy_001(비abstain), partial_001(ABSTAIN)

## OverlayTimeReadout

- Producer: `readout` · Consumer: `case`→`evidence`, `eval`
- 정상 예시(`data/mock/readout/overlay_time_readout.happy_001.json`, 요약):
```json
{ "readout_id": "readout_h001_overlay",
  "observation": { "kind": "OVERLAY_TIMESTAMP", "status": "OK", "value": "2026-08-24T18:31:30+09:00", "source": "VIDEO_OVERLAY_OCR" },
  "validation": { "format_ok": true, "monotonic_ok": true, "duration_match_ok": true, "sample_count": 5 } }
```
- Partial 예시(`data/mock/readout/overlay_time_readout.partial_001.json`) — 이 Scenario에서도 overlay 자체는 OK(시간은 성공하는 케이스로 설계)
- 핵심 불변조건: 최종 occurred_at 선택은 evidence/TimeResolution 책임, overlay 불확실은 filename candidate를 버리는 이유가 아님
- 사용 Scenario: happy_001, partial_001

## Observation\<T\>

- Producer: `recording`/`search`/`readout` 공통 envelope · Consumer: `evidence`, `case`(projection)
- 두 Scenario 모두 GPS UNKNOWN 예시를 썼다(이 프로젝트의 대시캠 소스에 GPS 스트림이 없다고 가정, `data/mock/evidence/observations.happy_001.json`):
```json
[ { "contract_version": "observation/v1", "value": null, "status": "UNKNOWN",
    "source": { "kind": "recording.gps_stream" }, "support_refs": [], "produced_by": { "module": "recording" },
    "reason": { "code": "recording.gps.source_absent" } } ]
```
- 핵심 불변조건: `OK`면 `value!=null`, `UNKNOWN/ERROR/NOT_APPLICABLE`이면 `value==null`, `ABSTAIN`은 공통 status에 없음(readout 도메인 전용)
- 사용 Scenario: happy_001, partial_001 (둘 다 UNKNOWN — GPS 정상 관찰 예시는 이번 Pack에 없음, v1에서 추가 권장)

## TimeResolution

- Producer: `evidence`(김준영) · Consumer: `case`, `web`(projection)
- 정상 예시(`data/mock/evidence/time_resolution.happy_001.json`, 요약):
```json
{ "contract_version": "time-resolution/v1", "resolution_ref": { "kind": "time_resolution", "ref": "tres_h001" },
  "status": "OK",
  "resolved": { "value": "2026-08-24T18:31:30+09:00", "source": { "kind": "readout.overlay_timestamp", "input_ref": { "kind": "overlay_time_readout", "ref": "readout_h001_overlay" } },
    "verification": "VERIFIED", "computation": { "mode": "DIRECT", "timezone": { "zone_id": "Asia/Seoul", "utc_offset": "+09:00", "source": "SOURCE_EXPLICIT" } }, "user_corrected": false },
  "conflict": { "exists": false, "between_refs": [], "requires_user_notice": false } }
```
- **이 계약은 원문 자체에 §8/§9 예시 JSON이 전혀 없다** — 이번 Pack이 만든 예시가 사실상 이 계약의 첫 구체 인스턴스다. Owner 검수 시 특히 눈여겨봐야 할 지점
- Partial 예시(`data/mock/evidence/time_resolution.partial_001.json`) — 이 Scenario에서도 `status=OK`(시간은 성공하도록 설계했다)
- 핵심 불변조건: `status=UNKNOWN`이면 `resolved` 없음, `resolved` 있으면 `provenance.selected_input_ref` 필수
- 사용 Scenario: happy_001, partial_001

## EvidenceRecord

- Producer: `evidence`(김준영) · Consumer: `case`, `web`(projection)
- **이 계약도 원문에 JSON 예시가 없다** — 아래는 계약 스키마(§3)를 그대로 따라 처음 만든 예시다
- 정상 예시(`data/mock/evidence/evidence_record.happy_001.json`, 요약):
```json
{ "contract_version": "evidence-record/v1.1", "record_ref": { "kind": "evidence_record", "ref": "ev_h001" },
  "case_ref": { "kind": "case", "ref": "case_happy_001" }, "selection_rev": 1,
  "vehicle_number": { "value": "12가 3476", "source": { "kind": "readout.plate_overlay_ocr", "observability": "OBSERVED" }, "user_corrected": false },
  "location": { "address": { "value": "미금역 사거리 인근", "source": { "kind": "search.visual_inference", "observability": "INFERRED" }, "user_corrected": false } } }
```
- Partial 예시(`data/mock/evidence/evidence_record.partial_001.json`) — **`vehicle_number`/`location` 키 자체가 없다**(placeholder 금지 원칙, §10 불변조건 6)
- 핵심 불변조건: 확정 못한 값은 null/placeholder가 아니라 필드 부재, `occurred_at` 있으면 `time_resolution_ref` 필수
- 사용 Scenario: happy_001, partial_001

## EvidenceNeeds

- Producer: `evidence` · Consumer: `case`
- 정상 예시(items 없음, `data/mock/evidence/evidence_needs.happy_001.json`):
```json
{ "contract_version": "evidence-needs/v1", "basis_record_ref": { "kind": "evidence_record", "ref": "ev_h001" }, "items": [] }
```
- Partial 예시(`data/mock/evidence/evidence_needs.partial_001.json`) — `items`에 `PLATE_REREAD`(계약 §11 공식 예시와 거의 동일 구조)
- 핵심 불변조건: `(kind, would_fill)` 조합 중복 금지, v1 kind는 `OVERLAY_TIME_OCR`/`PLATE_REREAD`만 허용, `items=[]`이 신고 가능을 뜻하지 않음
- 사용 Scenario: happy_001(빈 배열), partial_001(PLATE_REREAD)

## RequirementReport

- Producer: `evidence`(김준영) · Consumer: `case`, `web`(projection)
- **원문에 JSON 예시 없음**(§13은 필요한 Mock 케이스 목록만 bullet로 제공) — 이번 Pack이 실제 예시를 처음 만들었다
- 정상 예시(FINAL_PACKAGE/WARN, `data/mock/evidence/requirement_report.happy_001.json`, 요약):
```json
{ "scope": "FINAL_PACKAGE", "overall": "WARN",
  "checks": [ { "code": "evidence.location.confidence", "category": "LOCATION", "outcome": "WARN", "reason_code": "location.inferred_needs_review" } ] }
```
- BLOCK 예시(EVIDENCE scope, `data/mock/evidence/requirement_report.partial_001.json`, 요약):
```json
{ "scope": "EVIDENCE", "overall": "BLOCK",
  "checks": [ { "code": "evidence.vehicle_number.present", "category": "VEHICLE", "outcome": "BLOCK", "reason_code": "vehicle_number.unconfirmed" },
              { "code": "evidence.location.present", "category": "LOCATION", "outcome": "UNKNOWN", "reason_code": "location.no_source_available" } ] }
```
- 핵심 불변조건: `checks[].code` 중복 금지, `overall=ERROR` 없음(엔진 실패는 Report 자체 미생성으로 처리)
- 사용 Scenario: happy_001(WARN), partial_001(BLOCK) — §13이 요구하는 8가지 Mock 케이스(EVIDENCE/FINAL_PACKAGE × PASS/WARN/BLOCK/UNKNOWN) 중 이번 Pack은 2가지만 채웠다. **나머지 6가지는 v1 확장 대상**

## ReportPackage

- Producer: `evidence`(김준영) · Consumer: `case`, `web`(projection)
- **원문에 JSON 예시 없음** — 정상 예시(`data/mock/evidence/report_package.happy_001.json`, 요약):
```json
{ "package_ref": { "kind": "report_package", "ref": "pkg_h001" }, "evidence_record_ref": { "kind": "evidence_record", "ref": "ev_h001" },
  "requirement_report_ref": { "kind": "requirement_report", "ref": "req_h001" },
  "report": { "title": "백색 실선 침범 신고 (흰색 SUV 12가 3476)", "template_ref": "report-template/lane-change/v1" },
  "handoff": { "destination": "SAFETY_REPORT", "supported_actions": ["DOWNLOAD_ASSETS", "COPY_FIELDS", "OPEN_DESTINATION"] } }
```
- Partial 시나리오에는 이 fixture가 **없다** — BLOCK이므로 의도된 부재(§8.1 생성 조건 미충족)
- 핵심 불변조건: `BUILDING/INCOMPLETE/ERROR/READY` 같은 status 필드 없음, `EvidenceRecord` 전체를 embed하지 않음(확정값만 snapshot)
- 사용 Scenario: happy_001만

## JobRecord (Job Intent)

- Producer: `case`(유소연) · Consumer: `common/runtime`
- 정상 예시(`data/mock/case/job_records.happy_001.json`, 배열 2건 중 1건):
```json
{ "job_id": "job_h001_coarse", "case_id": "case_happy_001", "case_rev": 1, "kind": "COARSE_SEARCH",
  "scope_ref": "scope_h001", "input_fingerprint": "sha1:h001-coarse", "force_rerun": false, "requested_at": "2026-08-24T18:24:50+09:00" }
```
- **주의(§4 새 발견):** `kind="PLATE_READ"`인 두 번째 JobRecord(`job_h001_plate`)가 `PlateReadout`과 `OverlayTimeReadout` 두 ReadoutRun을 모두 만든다고 가정했다 — `OVERLAY_TIME_READ`용 별도 kind가 계약에 없어서 내린 임시 가정이다(`CONTRACT_CONFLICTS.md` §4 참고)
- 핵심 불변조건: 동일 job_id 재사용 금지, 캐시 재사용은 `(case_id,kind,input_fingerprint)` 동일+`force_rerun=false`+기존 SUCCEEDED에 한정
- 사용 Scenario: happy_001, partial_001

## JobExecution

- Producer: `common/runtime`(김준영/정철원) · Consumer: `case`, `web`(projection), `eval`
- 정상 예시(`data/mock/case/job_executions.happy_001.json`, 배열 2건 중 1건):
```json
{ "execution_id": "exec_h001_plate", "job_id": "job_h001_plate", "status": "SUCCEEDED", "attempt": 1,
  "queued_at": "2026-08-24T18:30:51+09:00", "started_at": "2026-08-24T18:31:00+09:00", "ended_at": "2026-08-24T18:31:12+09:00",
  "produced": [ { "kind": "readout_run", "ref": "rr_h001_plate" }, { "kind": "readout_run", "ref": "rr_h001_overlay" } ],
  "failure_kind": null, "usage_refs": ["usage_h001_2", "usage_h001_3"] }
```
- 핵심 불변조건: `SUCCEEDED`가 아니면 `produced`를 유효 결과로 취급 안 함, `QUEUED/RUNNING`이면 `ended_at=null`
- 사용 Scenario: happy_001, partial_001 (둘 다 SUCCEEDED — FAILED/STALE 예시는 v1 확장 대상)

## UsageRecord

- Producer: `common/runtime`(김준영) · Consumer: `case`, `eval`, `search`
- 정상 예시(`data/mock/case/usage_records.happy_001.json`, 배열 3건 중 1건, readout 호출은 token 없음):
```json
{ "usage_id": "usage_h001_2", "execution_ref": "exec_h001_plate", "run_ref": null, "case_id": "case_happy_001",
  "provider_label": "ocr-local", "operation": "READOUT_PLATE", "token_usage": null,
  "processed_duration_sec": 7.0, "latency_ms": 820, "cost": { "amount": "0", "currency": "KRW" } }
```
- 핵심 불변조건: `token_usage`는 전체 null이거나 세 필드 모두 존재(일부만 채우지 않음), `total_tokens=input+output`, append-only
- 사용 Scenario: happy_001, partial_001

## CaseView

- Producer: `case`(유소연) · Consumer: `web`(유일한 read contract), `eval`
- 정상 예시(`data/mock/case/case_view.happy_001.json`, 요약):
```json
{ "case_id": "case_happy_001", "stage": "READY", "user_reviewed": true,
  "evidence": { "plate_display": { "value": "12가 3476", "needs_review": false, "info_state": "INFO_SOURCE_VERIFIED" },
                "location_display": { "value": "미금역 사거리 인근", "needs_review": true, "info_state": "INFO_NEEDS_REVIEW" } },
  "requirements": { "scope": "FINAL_PACKAGE", "readiness": "WARN", "checks": [] },
  "package": { "package_ref": "pkg_h001", "artifact_ref": "da_h001_report_video" } }
```
- Partial 예시(`data/mock/case/case_view.partial_001.json`, 요약):
```json
{ "case_id": "case_partial_001", "stage": "EVIDENCE_REVIEW",
  "evidence": { "plate_display": { "value": null, "needs_review": true, "info_state": "INFO_UNKNOWN" } },
  "requirements": { "scope": "EVIDENCE", "readiness": "BLOCK", "checks": [] }, "package": null,
  "notices": [ { "code": "PLATE_ABSTAINED", "severity": "WARN", "blocking": false }, { "code": "LOCATION_UNKNOWN", "severity": "WARN", "blocking": false } ] }
```
- **B01/B02 주의:** 위 `evidence.*_display`/`requirements` 값은 계약 §8/§9가 이미 예시로 든 값의 형태를 재사용한 것이며, 이 값을 만들어내는 파생 규칙 자체는 Pending이다(`CONTRACT_CONFLICTS.md` §1 B01/B02)
- 사용 Scenario: happy_001, partial_001
