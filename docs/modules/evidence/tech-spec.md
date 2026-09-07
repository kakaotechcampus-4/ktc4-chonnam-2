# Evidence + common/runtime 1차 통합 Technical Spec

> **상태:** 1차 Mock 통합 구현 · **작성일:** 2026-09-07 · **Owner:** 김준영
>
> **기준:** `architecture/module-architecture.md` v4, Final Data Contract,
> `first-integration-checklist.md`, Mock Pack Seed v0
>
> **구현 결정:** `decisions/first-integration-runtime-boundary.md`

## 1. 구현 목표

공용 `scenario_happy_001`과 `scenario_partial_001`의 upstream JSON을 같은
입력 envelope로 받아 다음 순수 파이프라인을 실행한다.

```text
VisualEvidence + PlateReadout + OverlayTimeReadout
+ TimeSourceCandidate[] + Observation[] + case context
                         |
                         v
TimeResolution -> EvidenceRecord -> EvidenceNeeds
                                      |
                                      v
                              RequirementReport
                                      |
                                PASS / WARN only
                                      v
                                ReportPackage
```

Consumer는 Python 내부 타입을 알 필요가 없다. 모든 공개 함수는 JSON으로
직렬화 가능한 `Mapping`을 받고 plain `dict`를 반환한다.

## 2. 범위와 제외

포함:

- `evidence` 공개 함수 6개와 전체 조립 함수 `assemble()`
- 초기 4종 `visual_event_type` 정책 매핑
- 검증된 Overlay 우선, filename/metadata fallback, UNKNOWN 보존
- ABSTAIN 시 번호판 필드 부재와 `PLATE_REREAD` Need
- `BLOCK > UNKNOWN > WARN > PASS` 판정
- ready-only `ReportPackage`와 결정론적 신고문
- `JobExecution`/`UsageRecord` 계약 검증과 usage aggregate
- 운영 로그의 번호판/GPS/payload key 마스킹
- 공용 Mock Pack adapter, CLI, smoke/contract test

제외 또는 Pending:

- `CorrectionRecord` 기반 USER_INPUT 재평가(B01/B03 관련 접합 포함)
- derived asset metadata 기반 용량·번호판 가시성·시각 표시 판정
- `VisualEvidence.verification=NOT_OBSERVED`인 no-result 경로(1차 두 Scenario는
  `OBSERVED`만 다루며 현재 공개 조립 함수는 이를 명시적으로 거절한다)
- `JobExecution` queue/lease/heartbeat/retry 구현(정철원 담당)
- `ReadoutRun`과 `UsageRecord.run_ref` 접합(B05)
- CaseView basis/projection 선택(B01/B02)
- 신고기한과 공휴일 데이터 소스
- 실제 안전신문고 제출 및 인증

이 항목들은 placeholder나 새 enum으로 대신하지 않는다.

## 3. 공개 API

`src/daesingo/evidence/__init__.py`가 공개 경계다.

```python
resolve_time(overlay_time_readout, time_source_candidates, *, resolution_ref, supersedes_ref=None)
build_evidence_record(visual_evidence, plate_readout, observations, time_resolution, *, ...)
build_evidence_needs(evidence_record)
evaluate_requirements(evidence_record, *, requirement_report_ref, scope, evaluated_at, asset_refs=())
build_report_package(evidence_record, requirement_report, *, ...)
assemble(request)
```

- 각 단계 함수는 독립 contract test가 가능하다.
- `assemble()`은 같은 실행에서 만든 ref를 다음 단계에 그대로 연결한다.
- 입력을 `deepcopy`한 뒤 처리하고 caller 객체를 mutate하지 않는다.
- Contract를 만족할 수 없는 입력은 `EvidenceContractError`로 fail closed 한다.
- Gate가 닫힌 정상 경로는 예외가 아니라 `report_package=None`이다.

`src/daesingo/common/__init__.py`는 다음 계약 유틸리티를 공개한다.

```python
validate_job_execution(execution)
validate_usage_record(record)
validate_execution_usage_links(executions, usage_records)
aggregate_usage(records)
sanitize_log_event(event)
```

실제 queue 실행은 이 API에 포함하지 않는다.

## 4. `assemble()` 입력 envelope

입력은 upstream Contract 원문과 orchestration context를 분리한다.

```json
{
  "case_ref": {"kind": "case", "ref": "case_happy_001"},
  "selection_rev": 1,
  "candidate_ref": {"kind": "candidate_event", "ref": "cand_h001"},
  "evidence_interval_ref": {"kind": "asset_span", "ref": "sa_h001_01:690.0-708.0"},
  "visual_evidence": {},
  "plate_readout": {},
  "overlay_time_readout": {},
  "time_source_candidates": [],
  "observations": [],
  "location_hint": "미금역 근처",
  "requirement_scope": "FINAL_PACKAGE",
  "evaluated_at": "2026-08-24T18:35:00+09:00",
  "package_created_at": "2026-08-24T18:36:00+09:00",
  "refs": {
    "resolution_ref": {},
    "record_ref": {},
    "requirement_report_ref": {},
    "package_ref": {}
  },
  "assets": {
    "requirement_asset_refs": [],
    "report_video_ref": {},
    "plate_image_ref": {},
    "source_refs": []
  }
}
```

ID와 평가/생성 시각은 runtime이 주입한다. 순수 함수가 clock이나 랜덤 ID를
읽지 않기 때문에 같은 입력은 같은 출력을 만든다. `requirement_scope`도 현재
판정 시점을 선택하는 orchestration context이며 B02 projection 규칙이 아니다.

공용 fixture adapter는 `tests/fixtures/evidence_request.*.json`의 `fixture_paths`
만 실제 upstream JSON으로 치환한다. 처리 함수는 fixture 경로를 모른다.

## 5. 내부 정책

### 5.1 시각

1. Overlay observation이 `OK`이고 format/monotonic/duration 검증이 모두 참이며
   sample이 1개 이상이면 `VERIFIED`로 채택한다.
2. 이때 filename/metadata 후보는 `considered[]`에 남기고 사용하지 않은 이유를
   보존한다.
3. 검증 Overlay가 없으면 정상 filename/metadata 후보를 비교한다. 단독 후보나
   충돌 fallback은 `NEEDS_REVIEW`, 같은 값을 말하는 복수 후보는 `AGREED`다.
4. 사용할 후보가 없으면 `UNKNOWN`이며 `resolved`를 만들지 않는다.

Recording 입력의 metadata source enum은 Final Contract 그대로 `FILE_METADATA`와
`VENDOR_METADATA`를 사용한다. 충돌 후보는 둘 이상이어도 합의가 아니므로
`resolved.verification=UNVERIFIED`다.

첫 두 공용 Scenario는 1번 경로만 완료 조건으로 사용한다. 나머지는 경로와
불변조건을 열어 둔 최소 구현이며 전체 fallback matrix 완료를 뜻하지 않는다.

### 5.2 Event mapping

`policy.py`의 immutable `EVENT_POLICIES`가 초기 4종 매핑과 신고문 template
revision을 소유한다. `visual_event_type`, `safety_report_type`,
`violation_expression`은 각각 별도 값을 유지한다.

대상 association이 `AMBIGUOUS`이면 법적 확정을 추가하지 않고 기존 Mock과 같이
`violation_expression`에 대상 특정 모호 provenance만 보존한다. 별도 Requirement
check 신설은 Consumer 합의 전에는 하지 않는다.

### 5.3 값 승격과 위치

- `PlateReadout.abstained=true` 또는 observation이 `OK`가 아니면
  `vehicle_number`를 만들지 않는다.
- GPS `UNKNOWN/ERROR/NOT_APPLICABLE`은 정상적인 값 부재로 처리한다.
- GPS `OK`는 숫자 `lat`과 `lon`/`lng`가 있어야 `coord`로 승격한다.
- 사용자 위치 단서는 `location.user_hint`로만 보존한다.
- 확정된 `location.search_keyword`가 있으면 Package projection에서 이를 우선하고,
  없을 때만 `user_hint`의 `근처`/`인근`/`부근` 접미사를 검색 보조어에서 제거한다.
- 신고문이 `user_hint`를 사용할 때는 `사용자가 ...로 기억한 지점`이라고 표기해
  객관 주소나 GPS로 오인되지 않게 한다.
- `OK + null`처럼 Contract invariant를 어긴 Observation은 UNKNOWN으로
  바꾸지 않고 오류로 거절한다.

### 5.4 Requirement와 Package

첫 rule set은 번호판, 사건시각, 위치의 세 check를 만든다. 판정 엔진 오류는
`overall=ERROR`를 만들지 않고 예외로 종료한다.

Package는 `scope=FINAL_PACKAGE`, `overall in {PASS, WARN}`, Report Video 존재,
필수 handoff 값 존재일 때만 생성한다. `WARN`은 진행 가능한 상태다.

신고문은 confirmed Evidence에 없는 `VisualEvidence.target.described_as`를 사용하지
않는다. 따라서 기존 Happy fixture와 JSON 구조는 같지만 title/description의
`흰색 SUV`는 의도적으로 빠진다. 이는 체크리스트의 Contract 변경 검토 항목을
값 생성 없이 안전하게 처리한 차이다.

## 6. common/runtime

- `JobExecution` 10개 필드, 닫힌 status, timestamp 관계를 검증한다.
- `UsageRecord.token_usage`는 전체 객체 또는 `null`만 허용하고 합계를 검증한다.
- Execution↔Usage 연결은 양방향이어야 한다.
- usage aggregate는 duration/token/latency/cost를 원장에서 계산한다.
- `sanitize_log_event()`는 원본을 mutate하지 않고 민감 key와 문자열 내 번호판/
  좌표 패턴을 마스킹한다.

마스킹은 운영 로그의 방어선이며 도메인 저장 데이터 삭제 기능이 아니다.

## 7. 실행과 검증

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/run_evidence_fixture.py happy_001 --output <output-dir>
python scripts/run_evidence_fixture.py partial_001 --output <output-dir>
python scripts/validate_mock_pack.py
python scripts/validate_evidence_impl.py
python scripts/check_boundaries.py
```

`validate_mock_pack.py`는 팀 공용 정적 fixture 참조와 invariant만 검증한다.
모듈 전용 `validate_evidence_impl.py`가 실제 `assemble()` 출력을 생성해 두
Scenario의 canonical fixture와 비교한다. ReportPackage 신고문은 위 정책 차이
때문에 구조만 비교하고, 나머지 4개 산출물은 값까지 비교한다.

## 8. 파일 구조

```text
src/daesingo/evidence/
  __init__.py       public exports
  policy.py         event/rule/template policy data
  service.py        pure pipeline
src/daesingo/common/
  __init__.py       public exports
  runtime.py        JobExecution/UsageRecord contract helpers
  privacy.py        structured log sanitization
scripts/
  evidence_fixture_support.py
  run_evidence_fixture.py
  validate_evidence_impl.py
tests/
  fixtures/evidence_request.{happy_001,partial_001}.json
  test_evidence_integration.py
  test_common_runtime.py
```

## 9. 1차 완료의 정확한 표현

현재 완료는 **공용 Happy/Partial fixture 기반 제한 통합 경로**다. 실제 OCR/AI,
queue, derived asset metadata, CorrectionRecord, CaseView 전체 E2E까지 완료됐다는
뜻은 아니다. Merge 회의에서는 `PARTIAL_READY`로 표현하고 위 Pending 접합을
상대 Owner와 확인한다.
