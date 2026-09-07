# 04. Mock Validation Report

## 검증 방법

`scripts/validate_mock_pack.py` — 무거운 validation framework 없이(실제 Contract Model 코드가 아직 없으므로, `src/daesingo/*/README.md` "아직 코드가 없다") 경량 스크립트로 확인했다:

1. `data/mock/**/*.json` 49개 전체 JSON parse
2. `manifest.json` / `scenarios/*.json` / `fixture_index.csv`가 가리키는 모든 경로 실존 확인
3. 시나리오별 ID 참조 일관성(`candidate_id`/`run_id`/`job_id`/`execution_id`/`usage_id`/`case_id` 등이 모듈 fixture 사이에서 어긋나지 않는지)
4. 계약이 명시한 주요 invariant(예: `SpanResolution.status`↔`missing_ranges` 관계, `AnalysisRun.completed_at>=started_at`, Candidate Search/Visual Verify Run 분리, Fine-relative `at_offset_ms`, `AnalysisRun.usage_summary`↔`UsageRecord` 집계, `JobExecution.status`↔`ended_at`, `token_usage.total==input+output`, `CaseView.package`↔`requirements.scope/readiness` 등)

### 실행 결과 (2026-09-07 기준)

```
검사한 JSON 파일 수: 49
오류(ERROR): 0
경고(WARN): 0
```

**이 결과가 뜻하는 것과 뜻하지 않는 것.** PASS는 "이번에 만든 49개 파일이 서로 참조 무결하고 스크립트가 아는 invariant를 어기지 않는다"는 뜻이다. 계약 의미 전체, 예시 직렬화 전체, Owner 수락을 검증한 것은 아니다(경계 스크립트 관례와 동일 — `scripts/README.md` 참고).

## Contract별 생성 Fixture

| Contract | Normal | Empty | Unknown | Abstain | Partial | 기타 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| RecordingTimeline | 2 | N/A | N/A | N/A | 0 | timeline_status=PARTIAL/UNUSABLE 예시 없음(v1 확장 대상) |
| SpanResolution | 1(COMPLETE) | N/A | N/A | N/A | 1 | FAILED(spans=[]) 예시 없음 |
| TimeSourceCandidate | 2 | N/A | N/A | N/A | N/A | 계약상 "실제 값 있을 때만 생성" — TimeSourceCheck(부재 표현) fixture는 안 만듦 |
| AnalysisScope | 2 | N/A | N/A | N/A | N/A | — |
| AnalysisRun | 3(SUCCEEDED: Candidate Search 1 + Visual Verify 2) | N/A | N/A | N/A | 1(Candidate Search) | FAILED 예시 없음 |
| CandidateEvent | 2 | 0 | N/A | N/A | N/A | Candidate 0개(SUCCEEDED+빈배열) 예시 없음 — Type B 대표 Scenario 미작성 |
| VisualEvidence | 1(OBSERVED/MATCHED) | N/A | N/A | N/A | 1(AMBIGUOUS) | NOT_OBSERVED 예시 없음 |
| PlateReadout | 1 | N/A | N/A | 1 | N/A | — |
| OverlayTimeReadout | 2 | N/A | N/A | N/A | 0 | format_ok/monotonic_ok=false 예시 없음 |
| ReadoutRun | 4(SUCCEEDED) | N/A | N/A | N/A | 0 | PARTIAL/FAILED(failure 객체 있는) 예시 없음 |
| Observation\<T\> | 0 | N/A | 2 | N/A | N/A | GPS 정상(OK) 관찰 예시가 없다 — 두 시나리오 다 UNKNOWN만 씀 |
| TimeResolution | 2(OK) | N/A | 0 | N/A | 0(NEEDS_REVIEW) | 원문 자체에 예시 없던 계약, 이번에 처음 만듦 |
| EvidenceRecord | 1 | N/A | N/A | N/A | 1(필드 부재) | 원문 자체에 예시 없던 계약 |
| EvidenceNeeds | 1(items 有) | 1([]) | N/A | N/A | N/A | — |
| RequirementReport | 0(PASS) | N/A | 0 | N/A | 1(WARN)+1(BLOCK) | §13이 요구한 8케이스 중 2개만 채움 — 원문 자체에 예시 없던 계약 |
| ReportPackage | 1 | N/A | N/A | N/A | N/A(BLOCK이라 미생성, 의도됨) | 원문 자체에 예시 없던 계약 |
| JobRecord | 6 | N/A | N/A | N/A | N/A | force_rerun=true 예시 없음(계약 원문 §9엔 있음, 이번 Pack엔 미포함) |
| JobExecution | 6(SUCCEEDED) | N/A | N/A | N/A | 0 | FAILED/STALE 예시 없음 |
| UsageRecord | 4(token 有) | N/A | N/A | N/A | 4(token=null) | — |
| CaseView | 1(READY/WARN) | N/A | N/A | N/A | 1(EVIDENCE_REVIEW/BLOCK) | — |
| CorrectionRecord | 0 | N/A | N/A | N/A | N/A | **의도적 제외** — Draft (`CONTRACT_CONFLICTS.md` §3) |

## Scenario별 Contract Coverage

| Scenario | RecordingTimeline | SpanResolution | AnalysisScope | AnalysisRun | CandidateEvent | VisualEvidence | ReadoutRun | PlateReadout | OverlayTimeReadout | Observation | TimeResolution | EvidenceRecord | EvidenceNeeds | RequirementReport | ReportPackage | JobRecord | JobExecution | UsageRecord | CaseView |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| scenario_happy_001 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| scenario_partial_001 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |

## 발견한 문제

세부 원문은 `CONTRACT_CONFLICTS.md`에 있다. 여기서는 분류만 한다.

### Contract 충돌

- 없음(값 공간이 실제로 서로 모순되는 경우는 못 찾았다).

### 불명확한 Contract

- "실행/판정 결과" 필드명이 계약마다 다르다(`outcome` vs `status` vs `overall`, `SpanResolution.status=COMPLETE`만 다른 계약의 "정상" 값과 이름이 다름) — `CONTRACT_CONFLICTS.md` §4-1
- Primary identifier 명명 관례가 모듈 경계로 갈린다(`*_id` vs evidence 쪽 `*_ref`) — §4-2
- `JobRecord.kind`가 `OVERLAY_TIME_READ`에 대응하는 값을 갖는지 불명확 — §4-3
- Search Fine Job은 열린 확장 규칙에 따라 `JobRecord.kind=VISUAL_VERIFY`를 사용했으나, 확인된 값 목록 등재는 case/search Owner 확인 필요 — §4-4

### Architecture 확인 필요

- 위 `JobRecord.kind`/`ReadoutRun.operation` 불일치를 어떻게 풀지는 이 Mock Pack이 결정할 사항이 아니다. `case`(유소연)·`readout`(신유민)·PM(김준영) 확인이 필요하다.
- `VISUAL_VERIFY` Job kind 이름은 Final `AnalysisRun.operation`과 맞춘 보수적 확장이며, `case`(유소연)·`search`(서어진)가 확인해야 한다.
- `CorrectionRecord`가 Final로 오르기 전까지는 Rerun(Type I)·사용자 수정(Type F) 대표 Scenario를 만들 수 없다.

### Fixture 생성 불가

- `SourceAsset`/`MediaStream`/`FrameRef`/`AnalysisSource`/`RemoteCopy`/`IncidentClip`/`DerivedAsset` — 계약 파일 자체가 없음(`CONTRACT_CONFLICTS.md` §2)
- `CorrectionRecord` — Draft(§3)

## 담당 Owner 검수 목록

R&R(`docs/management/ownership.md`)과 각 계약의 Producer/Consumer 관계에서 도출했다. 검수 담당을 임의로 새로 배정하지 않았다.

| 영역/Contract | Producer Owner | Consumer Owner | Mock 검수 담당 |
| --- | --- | --- | --- |
| RecordingTimeline · AssetSpan · SpanResolution · TimeSourceCandidate | 정철원 (recording) | 서어진(search)·유소연(case)·김준영(evidence) | 정철원 |
| AnalysisScope | 유소연(case)+서어진(search) 공동 | 서어진(search) | 유소연 · 서어진 |
| AnalysisRun · CandidateEvent · VisualEvidence | 서어진 (search) | 유소연(case)·김대원(eval)·김준영(evidence)·신유민(readout) | 서어진 |
| PlateReadout · OverlayTimeReadout · ReadoutRun | 신유민 (readout) | 유소연(case)·김준영(evidence)·김대원(eval) | 신유민 |
| Observation\<T\> | recording/search/readout (Contract Owner 김준영) | 김준영(evidence)·유소연(case, projection) | 김준영 |
| TimeResolution · EvidenceRecord · EvidenceNeeds · RequirementReport · ReportPackage | 김준영 (evidence) | 유소연(case)·신유민(web projection 대리) | 김준영 |
| JobRecord · CaseView · CorrectionRecord(Draft) | 유소연 (case) | 신유민(web)·김준영(evidence) | 유소연 |
| JobExecution · UsageRecord | 김준영(계약 Owner)/정철원(구현 담당) (common/runtime) | 유소연(case)·김대원(eval)·서어진(search 일부) | 김준영 |
| eval fixture(ground truth/prediction) | 김대원 (eval) | — | 김대원 |

## 각 Owner가 검수할 내용

### Producer (자기 모듈 fixture를 만든 사람 기준)

- 이 Mock 출력이 실제 자기 모듈에서 생산 가능한 형태인가?
- Final Contract와 일치하는가? (특히 자기 계약의 §8/§9 예시가 없었던 `TimeResolution`/`EvidenceRecord`/`RequirementReport`/`ReportPackage`는 이번이 사실상 첫 구체 인스턴스이므로 김준영 확인이 특히 중요하다)
- 현실적으로 불가능한 값 조합은 없는가? (예: 정철원 — `sa_h001_01`/`ms_h001_0x` 같은 opaque id 형태가 실제 recording 파이프라인이 낼 수 있는 형태인지)
- Consumer가 필요한 값이 빠져 있지 않은가?

### Consumer

- 이 Fixture만으로 자기 모듈 개발을 시작할 수 있는가?
- 필요한 실패/부분 성공 상태가 포함되어 있는가? (위 Contract별 표의 빈 칸이 "아직 없는 케이스" 목록이다)
- 신유민(web): `CaseView` 두 개(READY/WARN, EVIDENCE_REVIEW/BLOCK)만으로 §19가 요구하는 정상/결과없음/low confidence/UNKNOWN/ABSTAIN/일부정보부족/처리중/실패 8개 UI 상태를 다 커버하지 못한다 — "결과 없음"·"처리 중"(running_jobs 有)·"실패" 상태는 v1에서 추가 필요
- 김대원(eval): partial 시나리오용 ground truth/prediction이 없다 — Partial Success 채점 검증은 v1로 미뤄졌다
