# ADR-EVIDENCE-001: 1차 Mock 통합 실행 경계와 검증 전략

> **상태:** Accepted — 1차 Mock 통합 범위
> **결정일:** 2026-09-07
> **Owner:** 김준영 (`evidence`, `common/runtime` 계약)
> **적용 범위:** `scenario_happy_001`, `scenario_partial_001`

관련 문서:

- `../../../architecture/module-architecture.md`
- `../../../architecture/contracts/contract-time-resolution.md`
- `../../../architecture/contracts/contract-evidence-record-needs.md`
- `../../../architecture/contracts/contract-requirement-report-package.md`
- `../first-integration-checklist.md`
- `../tech-spec.md`
- `../first-integration-code-review-response-2026-09-07.md`

## 1. Context

1차 구현은 실제 AI/OCR/외부 제출 연동이 없어도 upstream Contract JSON을 받아
`TimeResolution → EvidenceRecord → EvidenceNeeds → RequirementReport →
ReportPackage`를 실행할 수 있어야 한다. 동시에 다음 경계를 지켜야 한다.

- `evidence`는 `recording`, `search`, `readout` 구현을 import하지 않는다.
- 입력이 불확실하거나 없을 때 값을 생성하지 않는다.
- Consumer는 Evidence 내부 정책을 재구현하지 않고 JSON 출력만 읽는다.
- Final Contract와 Mock Seed 사이의 미결 접합은 구현 편의로 확정하지 않는다.
- 공용 Mock 검증과 한 모듈의 구현 회귀 검증을 섞지 않는다.

코드리뷰에서는 metadata source enum, 충돌 시각 verification, Package gate 증빙,
사용자 위치 단서 표현, 공용 validator 결합 문제가 확인됐다. 반면 영상 속
번호판/시각 가시성과 derived asset metadata는 입력 Contract가 아직 없어 첫
Scenario acceptance와 동시에 만족시킬 수 없다.

## 2. Decision

### 2.1 공개 실행 경계는 Contract-shaped pure function으로 둔다

공개 함수와 `assemble()`은 JSON 직렬화 가능한 mapping을 입력으로 받고 plain
dictionary를 반환한다. Clock, random ID, fixture 경로를 내부에서 읽지 않으며
ID와 평가시각은 orchestration envelope로 주입한다.

Contract를 만족하지 않는 입력은 `EvidenceContractError`로 fail closed 한다.
정상적인 불확실성은 예외가 아니라 필드 부재, `UNKNOWN`, `NEEDS_REVIEW`,
`BLOCK`, `report_package=None`으로 표현한다.

### 2.2 시간 판정은 Canonical enum과 독립 상태축을 그대로 사용한다

- Recording source enum은 `FILENAME`, `FILE_METADATA`, `VENDOR_METADATA`다.
- 검증된 overlay가 있으면 `VERIFIED`로 우선한다.
- 복수 후보의 값이 같을 때만 `AGREED`다.
- 값이 충돌한 fallback은 `NEEDS_REVIEW + UNVERIFIED`이며 conflict provenance를
  보존한다.
- 사용할 근거가 없으면 `UNKNOWN`이고 `resolved`를 만들지 않는다.

### 2.3 Package는 ready-only gate로 생성한다

`RequirementReport.scope=FINAL_PACKAGE`이고 `overall`이 `PASS` 또는 `WARN`이며
필수 handoff ref가 있을 때만 Package를 만든다. `BLOCK`이나 `UNKNOWN`이면 ref와
asset이 주어져도 `None`을 반환한다. 이 gate는 Partial fixture의 ref 부재와
독립된 단위 테스트로 검증한다.

### 2.4 사용자 위치 단서의 provenance를 Package까지 유지한다

`location.user_hint`는 주소나 GPS 사실로 승격하지 않는다. 신고문에 사용할 때는
사용자가 기억한 위치임을 문장에 드러낸다. confirmed `search_keyword`가 있으면
이를 우선하며, 없고 user hint만 있을 때는 Core User Flow의 GPS 없음 예시를
재현하는 제한적 검색어 projection을 사용한다. 최종 지도 핀 선택은 외부
안전신문고의 사용자 행동으로 남긴다.

### 2.5 1차 Requirement rule set은 두 Seed Scenario에 한정한다

현재 rule set은 번호판 확정, 사건시각 확정, 위치 근거만 평가한다. 영상 속
번호판 식별 가능성, 영상 속 시각 표시, asset 크기는 check를 만들 입력 Contract가
없으므로 이번 결정에서 PASS로 간주하지도, 임의 placeholder로 만들지도 않는다.

해당 check를 `UNKNOWN`으로 추가하면 Canonical precedence에 따라 Happy의
`overall=WARN`과 ReportPackage 생성이 사라진다. 따라서 이 범위 확장은
`readout`/`recording`/`case`와 Scenario acceptance를 함께 변경하는 후속
Owner 결정으로 둔다.

### 2.6 공용 검증과 구현 검증을 분리한다

- `validate_mock_pack.py`: 팀 공용 fixture parse/ref/invariant 검증
- `validate_evidence_impl.py`: Evidence 실제 출력, fixture shape/value,
  common/runtime 연결과 Package 안전 조건 검증
- `unittest`: 공개 함수의 행동과 회귀 테스트
- `evidence-contract-check.yml`: Pull Request에서 Python 3.11로 위 검증 실행

## 3. 검토한 대안

### A. fixture JSON을 그대로 반환

구현량은 작지만 Contract 입력을 처리하지 않고 fixture 경로에 결합된다. Consumer가
실제 Producer 출력으로 교체할 수 없으므로 채택하지 않았다.

### B. dataclass/Pydantic 모델을 모든 Consumer에 강제

초기 validation은 강해지지만 현재 모듈 전체에 공용 schema runtime이 없고 1차
Seed 범위보다 큰 의존성을 만든다. 표준 라이브러리 기반 명시적 boundary 검증을
선택하고 공용 model 도입은 별도 결정으로 남겼다.

### C. 근거 없는 asset/visibility check를 UNKNOWN으로 즉시 추가

Contract 의미에는 부합하지만 현재 Happy acceptance와 Package fixture를
무효화한다. 필요한 Producer 입력과 Scenario 변경 없이 Evidence만 수정하는 것은
cross-Owner 결정을 선점하므로 채택하지 않았다.

### D. 구현 회귀 검증을 공용 Mock validator에 포함

한 모듈의 import 실패가 팀 전체 fixture 검증을 막고 정적 데이터 정합성과 실행
회귀의 실패 원인이 섞인다. 모듈 전용 validator로 분리했다.

## 4. Consequences

### 긍정적 결과

- Consumer가 내부 클래스나 upstream 구현을 몰라도 JSON으로 연결할 수 있다.
- 같은 입력이 같은 출력을 만들어 fixture 기반 contract test가 재현 가능하다.
- ABSTAIN, UNKNOWN, conflict와 Package gate가 서로 다른 상태로 보존된다.
- 사용자 기억 단서가 객관 위치로 둔갑하지 않는다.
- 공용 Mock Pack 검증의 독립성이 유지된다.

### 감수하는 비용

- Mapping boundary 검증 코드가 반복되고 `service.py`가 커졌다.
- 1차 두 Scenario 밖의 fallback/no-result matrix는 아직 완전하지 않다.
- asset/visibility Requirement가 없으므로 현재 Package는 그 요건을 검사했다는
  증거가 아니다.
- 실제 queue, OCR/AI, derived asset 생성과 외부 제출은 검증하지 않는다.

## 5. Non-decisions / Pending

이 ADR은 다음을 확정하지 않는다.

- asset 크기·번호판 가시성·시각 표시용 Observation/metadata schema와 gate
- `VisualEvidence.NOT_OBSERVED`의 event 미확정/Need 흐름
- `CorrectionRecord` 기반 부분 재평가
- CaseView basis/projection과 source label 접합(B01/B02/B03)
- `ReadoutRun`과 `UsageRecord.run_ref` 접합(B05)
- `EvidenceValue.source.ref`의 optional 여부
- 신고기한/공휴일 source와 전체 신고 규정 matrix

## 6. Verification

결정은 다음 자동 검증으로 고정한다.

```text
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_mock_pack.py
python scripts/validate_evidence_impl.py
python scripts/check_boundaries.py
npm run build
```

실제 AI/OCR 성능, Owner 수락, 전체 E2E 완료는 위 명령의 PASS로 주장하지 않는다.

## 7. 변경 규칙

다음 변경은 이 ADR을 갱신하거나 supersede한다.

- 공개 함수가 plain Contract mapping이 아닌 공용 runtime model을 요구하게 됨
- timestamp source priority 또는 verification/conflict 의미 변경
- Package 생성 gate 변경
- 사용자 위치 단서가 신고문/검색어로 투영되는 정책 변경
- asset/visibility Requirement 입력이 확정되어 1차 rule set이 확대됨
- 공용 Mock validator와 모듈 구현 validator의 책임 재통합
