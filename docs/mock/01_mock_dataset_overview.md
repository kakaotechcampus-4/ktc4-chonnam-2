# 01. Mock Dataset Overview

## 목적

이미 확정된 Module Architecture(v4)와 Data Contract를 실제 실행 가능한 JSON/JSONL/CSV 예시 데이터로 펼쳐서, 각 모듈(recording/search/readout/evidence/case/eval/web)이 서로의 실제 구현 완료를 기다리지 않고 병렬 개발·parser/serializer 개발·상태 전이 검증·부분 실패/UNKNOWN/ABSTAIN 검증·1차 Mock E2E 통합을 할 수 있게 하는 것이 목적이다. 실제 AI/OCR/Search 성능을 증명하는 자료가 아니다.

## Source of Truth

- `docs/product/product-spec.md` (Must/Won't·불변 경계)
- `docs/architecture/module-architecture.md` (v4, §5-1~§5-9, §11-4)
- `docs/management/ownership.md` (R&R)
- `docs/architecture/contracts/*.md` — Final Data Contract 14건 + Draft 1건 (CorrectionRecord)
- `docs/architecture/contracts/adr/*.md` — 각 계약 대응 ADR + `adr-consistency-followup-2026-09-06.md`(현재 Pending 원장)
- `docs/architecture/contracts/contract-job-record-case-view.md` 부록 스키마(JobRecord/CaseView)
- `docs/product/core-user-flow.md` (핵심 사용자 흐름)

## 실행 모드: SEED MODE

이 Pack은 **SEED MODE**로 실행했다 — 이유는 편의가 아니라 사실이다. 원 지시문의 "Mock Pack(v1)"은 "9개 Final Contract + 9개 ADR"을 전제하는데, 실제 레포에는 **14개 계약 파일**이 있고 그중 `CorrectionRecord`는 Draft, `SourceAsset/MediaStream/FrameRef`와 `AnalysisSource/RemoteCopy/IncidentClip/DerivedAsset`을 다루는 계약 2건은 파일 자체가 없다. 나머지 Final 계약들도 상당수가 접합부 Pending(B01~B09 등, `CONTRACT_CONFLICTS.md` 참고)을 안고 있다. 이 상태에서 "9개+9개, Scenario 3~5개"를 그대로 실행하면 Pending 영역을 Mock 편의로 임의 확정하게 되므로, 대신 **Happy Path 1개 + 대표 Partial/UNKNOWN 1개**만 만들고 나머지는 `CONTRACT_CONFLICTS.md`에 기록했다.

## Contract Inventory

전체 계약과 데이터 흐름은 `03_mock_artifact_templates.md` 상단의 Inventory 표를 따른다(중복 방지를 위해 여기서는 요약만 적는다).

- Final: `RecordingTimeline`/`AssetSpan`/`SpanResolution`/`TimeSourceCandidate`(recording), `AnalysisScope`(search+case 공동), `AnalysisRun`/`CandidateEvent`(search), `VisualEvidence`(search), `PlateReadout`/`OverlayTimeReadout`/`ReadoutRun`(readout), `Observation<T>`(recording/search/readout 공통 envelope), `TimeResolution`/`EvidenceRecord`/`EvidenceNeeds`/`RequirementReport`/`ReportPackage`(evidence), `JobRecord`/`CaseView`(case), `JobExecution`/`UsageRecord`(common/runtime) — **21개 객체, 14개 파일**
- Draft: `CorrectionRecord`(case) — Seed Pack 제외
- 미작성(파일 없음): `SourceAsset`/`MediaStream`/`FrameRef`, `AnalysisSource`/`RemoteCopy`/`IncidentClip`/`DerivedAsset` — opaque id로만 참조

## 전체 Mock Pack 구성

- Scenario 2개: `scenario_happy_001`(Happy Path), `scenario_partial_001`(Partial Success/ABSTAIN/UNKNOWN)
- JSON 45개(계약/평가 fixture 42개 + 관리 JSON 3개), JSONL 1개(`scenario_catalog.jsonl`), CSV 1개(`fixture_index.csv`) — **총 47개 파일**
- 각 시나리오는 recording→search→readout→evidence→case 5개 모듈 체인을 관통하고, happy 시나리오는 eval(ground truth + 정답/오답 prediction)까지 포함한다

## 공통 기준 Scenario

- **대표 Happy Path:** `scenario_happy_001` — 위치는 사용자 기억 단서(NEEDS_REVIEW)이고 나머지는 모두 확정, `CaseView.stage=READY`·`package` non-null까지 도달
- **대표 Partial/Failure Path:** `scenario_partial_001` — 시간은 성공(overlay 검증), 번호판은 ABSTAIN, 위치는 GPS 없음+시각 단서 부족으로 UNKNOWN. `SpanResolution`도 PARTIAL(일부 자산 누락)을 함께 보여준다
- 대표 Rerun Path는 이번 Seed에서 만들지 않았다(`CorrectionRecord` Draft라서 재실행 트리거를 표현할 근거가 아직 Final이 아님 — `CONTRACT_CONFLICTS.md` §3)

## 폴더 구조

```
docs/mock/
  CONTRACT_CONFLICTS.md
  01_mock_dataset_overview.md
  02_mock_scenario_catalog.md
  03_mock_artifact_templates.md
  04_mock_validation_report.md
data/mock/
  manifest.json
  scenario_catalog.jsonl
  fixture_index.csv
  scenarios/
    scenario_happy_001.json
    scenario_partial_001.json
  recording/   (RecordingTimeline · TimeSourceCandidate · SpanResolution)
  search/      (AnalysisScope · AnalysisRun · CandidateEvent · VisualEvidence)
  readout/     (ReadoutRun · PlateReadout · OverlayTimeReadout)
  evidence/    (Observation · TimeResolution · EvidenceRecord · EvidenceNeeds · RequirementReport · ReportPackage)
  case/        (JobRecord · JobExecution · UsageRecord · CaseView)
  eval/        (prediction_correct / prediction_wrong — non-contract, harness 검증용)
  expected/    (ground truth — non-contract)
scripts/
  validate_mock_pack.py
```

기존 모듈 이름(`recording/search/readout/evidence/case/eval`)만 썼고 없는 모듈을 새로 만들지 않았다. `web` 전용 domain fixture는 만들지 않았다 — web은 `CaseView`만 읽는다(§19 원칙, `case/case_view.*.json`이 그 자료다).

## 사용 원칙

- Markdown 문서(01~04)보다 `data/mock/` 실제 파일이 기준이다. 03 문서의 JSON은 실제 fixture에서 그대로 옮긴 것이며 서로 달라지면 fixture가 맞다.
- Mock은 성능평가 자료가 아니다. AI/OCR 정확도를 증명하지 않는다.
- Contract가 바뀌면 Mock도 갱신해야 한다 — 이 문서는 2026-09-06 시점의 14개 계약 기준이다.
- 각 모듈 Owner의 검수가 필요하다(`04_mock_validation_report.md` §22/§23 참고).

## 1차 통합 준비 완료 기준

- [x] recording→search→readout→evidence→case 5개 모듈이 하나의 scenario_id로 연결됨 (Happy/Partial 각 1개)
- [x] 실제 JSON/JSONL/CSV 파일 존재, 경량 검증 스크립트 통과(`04_mock_validation_report.md`)
- [x] web이 읽을 `CaseView` fixture 존재 (safe projection, 원본 Evidence/Package 직접 노출 없음)
- [x] eval이 읽을 ground truth + 정답/오답 prediction 존재(happy 시나리오)
- [ ] 전체 E2E 6기준(`ownership.md` §7-④) 통과 — **아직 아님.** B01/B02(CaseView projection 파생 규칙)와 recording 자산 계약 2건이 닫히기 전까지는 "고정 입력에 대한 화면 렌더 확인" 이상의 통합 보증이 아니다
- [ ] `CorrectionRecord` 포함 Rerun 시나리오 — Draft가 Final로 오른 뒤 v1에서 추가
