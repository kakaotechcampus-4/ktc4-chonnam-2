# recording Technical Spec — 1차 Mock E2E

**Owner:** 정철원  
**Status:** Initial Implementation  
**범위:** Canonical recording Contract 경계와 공용 Seed Mock 실행

## 1. 목적

`recording` Consumer가 파일 probe, decoder, 저장소 같은 내부 구현을 알지 않고도 Canonical Contract 형식의 Timeline, 구간 해석 결과, 파일 기반 시각 후보와 Source 관찰값을 사용할 수 있게 한다.

이번 단계는 실제 미디어 처리의 완성이 아니라 공용 `scenario_happy_001`과 `scenario_partial_001`을 코드 경계로 재현하는 첫 baseline이다.

## 2. 기준 문서

- `docs/product/product-spec.md` §5·§7
- `docs/architecture/module-architecture.md` §4 모듈1·§5-2·§5-3
- `docs/management/ownership.md` §3 정철원·§7-④
- `docs/architecture/contracts/contract-recording-timeline-asset-span.md`
- `docs/architecture/contracts/contract-observation.md`
- `docs/architecture/contracts/adr/adr-recording-timeline-asset-span.md`
- `docs/architecture/contracts/adr/adr-consistency-followup-2026-09-06.md`
- `docs/mock/01_mock_dataset_overview.md`~`04_mock_validation_report.md`

충돌 시 위 문서들의 canonical 우선순위를 따르며 Pending 항목을 이 문서에서 확정하지 않는다.

## 3. 1차 구현 범위

### 포함

- Canonical JSON을 검증하는 immutable recording Contract 모델
- `RecordingTimeline`, `AssetSpan`, `SpanResolution`, `TimeSourceCandidate`, recording `Observation<T>` 직렬화 경계
- 공용 Mock Scenario를 로딩하는 교체 가능한 `FixtureRecordingService`
- Timeline 조회, exact Seed 구간 resolve, 시각 후보·Observation 조회
- Happy/Partial Smoke 및 Contract test

### 제외

- 실제 ffprobe/ffmpeg 기반 Source probe와 frame decode
- Timeline 자동 정렬 및 gap/overlap 판정 알고리즘
- `SourceAsset`·`MediaStream`·`FrameRef` 정식 모델
- `AnalysisSource`·`RemoteCopy`·`IncidentClip`·`DerivedAsset` 정식 모델
- 실제 provider upload/delete
- Report Video export와 retention 실행
- `JobExecution` 구현

제외 항목은 이후 독립 구현·커밋 단위로 추가한다.

## 4. 패키지 경계

```text
src/daesingo/recording/
  contracts.py  Canonical JSON 검증·직렬화
  service.py    1차 Mock E2E 공개 실행 경계
```

Consumer는 `daesingo.recording`의 공개 export를 사용한다. fixture 경로, JSON 파싱, dataclass 구성 등은 Consumer 책임이 아니다.

## 5. 공개 실행 경계

`FixtureRecordingService`는 다음 capability를 제공한다.

- 공용 Scenario fixture에서 서비스 구성
- `timeline_id + revision`으로 Timeline 조회
- `TimelineRef + requested Interval`로 준비된 `SpanResolution` 조회
- SourceAsset ref 기준 TimeSourceCandidate 조회
- recording Observation 조회
- 통합용 JSON-ready Artifact 출력

Seed에 없는 요청에는 결과를 추측하거나 새 Contract를 만들지 않고 `RecordingOutputNotPrepared`를 반환한다. 실제 resolver가 추가돼도 Consumer가 받는 Contract 모델은 유지한다.

## 6. Contract 검증

현재 코드 경계는 다음을 검증한다.

- 필수 식별자와 Contract discriminator
- revision 및 interval 기본 불변조건
- Contract enum 값 공간
- COMPLETE/PARTIAL/FAILED와 spans/missing_ranges 조합
- requested range 밖의 Span/MissingRange 금지
- offset-aware TimeSourceCandidate datetime
- UNKNOWN/ERROR Observation의 reason 존재
- Timeline이 참조하는 TimeSourceCandidate의 존재
- 서비스에 결합된 Timeline과 SpanResolution revision 일치

B06의 전체 coverage/failure reason 최종 표면, B07~B09 접합은 canonical 반영 전까지 이 모델에서 새 필드로 확정하지 않는다.

## 7. 실패 의미

- 잘못된 Canonical JSON: `ContractValidationError`
- Seed에 준비되지 않은 Timeline 또는 구간 요청: `RecordingOutputNotPrepared`
- GPS 없음: 실패가 아니라 `Observation.status=UNKNOWN`
- PARTIAL: usable `AssetSpan`과 `MissingRange`를 동시에 보존

Stub 미지원과 도메인 FAILED를 같은 상태로 취급하지 않는다.

## 8. 검증

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/recording -v
python scripts/validate_mock_pack.py
```

Merge 전 두 명령이 모두 성공해야 한다.

## 9. 다음 독립 구현 단위

1. Final Contract 확정 범위 안의 실제 Timeline/Span resolver baseline
2. Source probe 및 SourceAsset/MediaStream 계약 반영
3. Frame/AnalysisSource/Derived asset 계약 반영
4. common/runtime Owner 계약에 따른 `JobExecution` 구현

각 단계는 별도 커밋으로 유지하고 미작성 Contract 필드를 선행 구현으로 고정하지 않는다.
