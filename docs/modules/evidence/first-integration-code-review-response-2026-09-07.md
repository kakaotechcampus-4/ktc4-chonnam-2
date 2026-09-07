# `evidence` + `common/runtime` 1차 통합 코드리뷰 검증 및 조치 보고서

- **검증일:** 2026-09-07
- **대상 리뷰:** `first-integration-code-review-2026-09-07.md`
- **대상 브랜치:** `codex/feat-evidence-first-integration`
- **기준:** Architecture v4, Final Canonical Contract, Mock Pack Seed v0,
  `first-integration-checklist.md`
- **최종 판정:** **PARTIAL_READY — Blocker 2건과 즉시 수정 가능한 Required 항목은
  조치 완료. R-2와 cross-Owner 계약 항목은 결정 전까지 명시적 Pending.**

이 보고서는 원 리뷰의 지적을 그대로 수용하지 않고 Canonical Contract, 공용
fixture, 제품 흐름, 현재 코드로 각각 재검증한 결과다. 원 리뷰 파일은 감사
기록으로 보존하고 이 문서에 조치 결과를 덧붙인다.

## 1. 결론 요약

| 항목 | 객관 판정 | 조치 |
| --- | --- | --- |
| B-1 | 맞음 | `MANUFACTURER_METADATA` 제거, Final enum `VENDOR_METADATA` 지원 및 회귀 테스트 추가 |
| B-2 | 맞음 | 후보 값이 실제로 같을 때만 `AGREED`; 충돌 fallback은 `UNVERIFIED`로 수정 |
| R-1 | 맞음 | BLOCK report에 유효한 asset/ref를 직접 주는 package gate 테스트 추가 |
| R-2 | 문제 제기는 맞으나 현재 문서끼리 충돌 | 코드 변경 보류, Tech Spec Pending 유지, Owner 결정 필요 |
| R-3 | 맞음 | `user_hint` 사용 신고문에 사용자 기억 단서임을 명시 |
| R-4 | confirmed 값 무시는 맞음. fallback 자체는 제품 흐름 근거가 있음 | explicit `search_keyword` 우선; 사용자 단서만 있을 때의 제한적 fallback은 문서화 후 유지 |
| R-5 | 맞음 | 공용 validator에서 구현 import 제거, `validate_evidence_impl.py`로 분리 |
| A-1 | 이름 지적은 맞음. 입력 처리 결함 주장은 과함 | 테스트명 수정, malformed GPS는 fail-closed 유지 |
| A-2 | 맞음 | 1차 범위 제약을 Tech Spec에 명시; no-result 설계 전까지 Pending |
| A-3 | 결함으로 볼 계약 근거 없음 | 변경 없음 |
| A-4 | 맞음. 다만 기존 Contract↔Mock 충돌 | 구현에서 임의 해결하지 않고 계약 정리 Pending |
| A-5 | 공유할 사항은 맞음 | Evidence 소유 namespace임을 유지하고 Consumer 접합 때 공유 |
| A-6 | 맞음 | Python 3.11 CI workflow 추가 |
| A-7 | 현상은 맞음 | 기준 체크박스 일괄 완료 처리 대신 본 보고서에 항목별 판정·실행 증빙 기록 |
| A-8 | 낮은 결합 우려이나 경계 위반은 아님 | 변경 없음 |
| A-9 | 사실이나 결함은 아님 | 사용자 검수 전이므로 미커밋·PR 미생성 상태 유지 |

## 2. 수정한 결함

### 2.1 Canonical timestamp source enum

Final Recording Contract의 `TimeSourceCandidate.source_kind` 최소 enum은
`FILENAME | FILE_METADATA | VENDOR_METADATA`다. 구현도 이 값 공간과 같게
고쳤고 `VENDOR_METADATA`가 `recording.vendor_metadata_time` provenance로
연결되는지, 비표준 `MANUFACTURER_METADATA`가 거절되는지 함께 테스트한다.

### 2.2 충돌 후보의 verification

`conflict.exists=true`인 후보 집합은 합의가 아니다. 이제 복수 후보의 값이 모두
같을 때만 `resolved.verification=AGREED`이고, 충돌 시 filename fallback을
선택하더라도 `NEEDS_REVIEW + UNVERIFIED + conflict provenance`를 보존한다.

### 2.3 Package gate 증빙

Partial fixture의 package/asset ref 부재와 무관하게 gate 자체를 검증하도록,
`overall=BLOCK`인 RequirementReport에 유효한 package ref, report video ref,
source ref를 전달해도 `build_report_package()`가 `None`을 반환하는 테스트를
추가했다.

### 2.4 사용자 위치 단서와 검색어

- 신고문은 `location.user_hint`를 객관 위치처럼 서술하지 않고
  `사용자가 '…'로 기억한 지점`이라고 provenance를 드러낸다.
- `location.search_keyword`가 있으면 해당 confirmed 값을 우선 사용한다.
- confirmed 검색어가 없고 입력이 `user_hint`뿐일 때만 `근처/인근/부근`을
  제거한 보조어를 쓴다. 이는 `core-user-flow.md`의 GPS 없음 예시
  (`미금역 근처` → 안전신문고 검색어 `미금역`)를 재현하는 제한적 projection이며,
  주소나 장소명을 새로 확정하지 않는다.

### 2.5 검증 책임 분리와 CI

`validate_mock_pack.py`는 다시 팀 공용 정적 fixture 검증만 담당한다. 실제
Evidence 코드 실행, fixture 회귀, runtime 연결 검증은 새 모듈 전용
`validate_evidence_impl.py`가 담당한다. Pull Request와 `develop` push에서는
Python 3.11로 unit test, 공용 Mock 검증, Evidence 구현 검증을 실행하는
`evidence-contract-check.yml`도 추가했다.

## 3. 수정하지 않은 지적과 이유

### R-2 — Requirement asset/visibility matrix

문제 제기 자체는 타당하다. 현재 첫 rule set에는 asset 크기, 영상 속 번호판
식별 가능성, 영상 속 시각 표시 여부 check가 없다. 하지만 지금 즉시
`UNKNOWN` check를 추가하는 것도 Canonical gate와 현 체크리스트를 동시에
깨뜨린다.

- 체크리스트 §RequirementReport 완료 조건은 근거가 없으면 해당 check를
  `UNKNOWN`으로 내라고 한다.
- 같은 체크리스트 §Scenario별 완료 조건은 Happy를
  `scope=FINAL_PACKAGE + overall=WARN`으로 고정하고 Package 생성을 요구한다.
- Final Requirement Contract는 UNKNOWN이 하나라도 있으면
  `overall=UNKNOWN`이며, `BLOCK/UNKNOWN`에서는 Package를 만들지 못하게 한다.
- 체크리스트의 1차 제외 범위는 전체 Requirement matrix를 제외하고 두
  Scenario가 쓰는 rule만 구현한다고도 적혀 있다.

따라서 이는 한 줄 수정이 아니라 **1차 Happy acceptance를 유지할지, 미측정
asset check를 추가해 Package를 닫을지**의 Owner 결정이다. 현재 코드는 기존
Happy fixture와 명시된 demo acceptance를 유지하고, 미검사 asset 요건을 Tech
Spec Pending으로 공개한다. PR 승인 전에 `evidence`·`readout`·`recording`·`case`
Owner가 다음 중 하나를 기록해야 한다.

1. 1차에서는 asset/visibility check 생략을 승인한다.
2. Observation/derived asset metadata 입력을 계약화하고 UNKNOWN check를 추가한
   뒤 Happy fixture와 Package 기대값을 바꾼다.

### A-1 — known-empty GPS

`Observation` 일반 규칙상 known-empty와 UNKNOWN은 다르다는 지적은 맞다.
그러나 GPS Coordinate의 값 공간은 object이고 `OK + []`는 유효한 빈 좌표가
아니라 타입 위반이다. 이를 UNKNOWN으로 낮추면 Producer 계약 오류를 숨긴다.
따라서 fail-closed 동작은 유지하고 테스트명을
`test_malformed_known_empty_gps_is_rejected`로 바로잡았다.

### A-2 — `NOT_OBSERVED`

`NOT_OBSERVED`가 VisualEvidence의 유효 enum이라는 지적은 맞다. 다만 1차
체크리스트는 두 OBSERVED Scenario만 최소 범위로 삼고 no-result scenario를
포함하지 않는다. 새 Need kind나 event 미확정 표현을 독단적으로 만들지 않고,
현재 조립 함수가 이 경로를 지원하지 않는다는 사실을 Tech Spec 제외 범위에
명시했다. 후속 Contract/scenario가 정해지기 전까지 Pending이다.

### A-3, A-8, A-9

- A-3: `evidence.location.confidence`와 `evidence.location.present`는 각각
  신뢰도 판정과 존재 판정이라 의미가 다르다. Canonical Contract에 두 branch가
  같은 `code`를 써야 한다는 규칙이 없고 fixture도 서로 다른 code를 사용한다.
- A-8: `aggregate_usage()`는 search 모듈을 import하지 않고 common이 소유한
  UsageRecord에서 Canonical summary를 계산한다. 현재 모듈 경계 위반은 아니다.
- A-9: 미커밋은 상태 설명이다. 사용자가 검수한 뒤 PR을 올리기로 했으므로 이번
  조치에서도 commit, push, PR 생성은 하지 않는다.

## 4. 남은 Contract/Owner 결정

다음은 이번 구현 안에서 임의로 닫지 않는다.

- R-2의 asset 크기·번호판 가시성·시각 표시 Requirement 입력과 Happy gate
- `EvidenceValue.source.ref`의 optional 여부(A-4): Final 문구와 Seed fixture의
  `null` 불일치
- `location.source.gps` label key와 CaseView 전달(B01/A-5)
- `CorrectionRecord`, CaseView basis/projection(B01/B02/B03),
  `ReadoutRun`↔`UsageRecord.run_ref`(B05)
- 실제 신고기한/공휴일 source와 전체 규정 matrix

## 5. 검증 결과

2026-09-07 수정 후 로컬에서 다음을 실행했다.

| 검증 | 결과 |
| --- | --- |
| `python -m unittest discover -s tests -p "test_*.py" -v` | **22/22 PASS** |
| `python scripts/validate_mock_pack.py` | **45 files / ERROR 0 / WARN 0** |
| `python scripts/validate_evidence_impl.py` | **2 scenarios / ERROR 0** |
| `python scripts/check_boundaries.py` | **PASS — 위반 0건**; 미구현 모듈/asset contract NOTE만 존재 |
| Happy CLI smoke | **JSON 5건, Package 생성** |
| Partial CLI smoke | **JSON 4건, Package 미생성** |
| `npm run build` | **PASS** |
| `git diff --check` | **PASS** |

추가된 회귀 범위는 canonical vendor metadata enum, conflict/agreement 분기,
BLOCK package gate, confirmed search keyword 우선, 사용자 위치 단서 표시다.

## 6. PR 산정

PR은 아직 만들지 않는다. 현재 브랜치는 선행 Mock 수정 `c4fcbf0`에 의존하므로,
그 변경이 `develop`에 반영된 뒤 rebase해서 올리는 편이 안전하다.

현재 ADR 반영 후 PR 예상 규모는 **변경 경로 24개, 약 +3,104/-4행**이다.
여기에는 원 리뷰와 이 조치 보고서, 약 420행의 1차
체크리스트가 포함되므로 코드만의 규모로 해석하면 안 된다. 검수 중 추가 수정에
따라 수치는 달라질 수 있다.

권장 커밋 분리는 다음과 같다.

1. `docs(evidence)`: Tech Spec, 체크리스트, 리뷰 및 조치 보고서
2. `feat(common)`: runtime contract helper와 privacy logger, tests
3. `feat(evidence)`: pipeline, policy, public API, request fixtures, tests, CLI
4. `ci(evidence)`: 전용 validator와 Evidence contract workflow, README

PR 본문에는 `PARTIAL_READY`, R-2 미결정, 신고문 provenance 변경,
`VENDOR_METADATA`/conflict 수정, Pending cross-Owner 접합을 반드시 적는다.
