# evidence 1차 Mock 통합 수행 결과

> 상태: **PARTIAL_READY**
>
> 실행 기준: branch `docs/evidence-first-completion-checklist`, 구현 기준 커밋 `16c078f8b6fb7841c53bc97413fa16b90bda947d`, 실행 증빙 갱신 `08eb78c`
>
> 기준 계약/정책: `time-resolution/v1`, `evidence-record/v1.3`, `evidence-needs/v1`, `requirement-report/v1`, `report-package/v1`, `correction-record/v1.1`, `safety-report-policy/v1`

원본 [`first-completion-checklist.md`](first-completion-checklist.md)의 완료 정의와 작성 시점은 수정하지 않았다. 이 문서는 수행 결과만 별도로 연결한다. production/runtime 완성, 실제 AI·OCR·영상 생성, 외부 제출, 실제 `case`/web projection은 이 결과가 증명하지 않는다.

## 실행 결과 요약

| Scenario | baseline 결과 | Consumer Mock 판독 | 판정 |
| --- | --- | --- | --- |
| H `scenario_happy_001` | 공용 입력의 `NOT_ASKED`는 renderer/Package 미발행. 명시적 test-derived `CONFIRMED`를 추가하면 Time `OK`; Evidence `ev_h001`; Needs `[]`; Requirement `PASS/PASS`; Package `pkg_h001` | derived 확인 입력에서만 `EVIDENCE_SUFFICIENT=true`, `PACKAGE_READY=true`; `USER_REVIEWED=CASE_OWNED_NOT_DERIVED` | 정책 guard 검증 완료 + 파생 Mock 연결 검증 완료 |
| U `scenario_unknown_abstain_partial_001` | Time `NEEDS_REVIEW`와 충돌 provenance; visual type `null`; `USER_UNSURE`; Requirement `WARN/WARN`; Package 0건 | Evidence gate만 true, Package gate false | **Contract 변경 검토 필요(Q1)** |
| P `scenario_plate_reread_001` | `ev_p001` 번호판 부재 + `PLATE_REREAD` + UNKNOWN → `ev_p001_v2` 번호판 `17나2867` + 빈 Needs + PASS | 현재 Evidence는 v2, Package 없음 | Mock 연결 검증 완료(Package는 Scenario 범위 밖) |
| R `scenario_correction_rerun_001` | Time `NEEDS_REVIEW` → `OK/AGREED/USER_OVERRIDE`; Evidence/Requirement supersede; 번호판 `34나7890`·basis·`selection_rev=1` 보존 | 현재 Evidence/Requirement는 v2, Package 없음 | Mock 연결 검증 완료(Package는 Scenario 범위 밖) |

고정 출력은 [`artifacts/first-completion/run-summary.json`](artifacts/first-completion/run-summary.json)과 같은 폴더의 네 `*.baseline.json`이다. 각 파일은 원본 recording/search/readout/case JSON 경로, candidate Fine run, timeline revision/range, correction refs, 실제 출력 다섯 배열, 공용 evidence Fixture와의 비교, Consumer Mock 판독을 함께 기록한다.

## 처리 경계

- **실제 baseline 처리:** 시간 source 우선순위/offset/충돌, Evidence 조립, CorrectionRecord head와 타입 검증 및 반영, declarative Needs, 두 scope의 명시적 rule 평가, deterministic report rendering, ready-only Package 조립.
- **공용 Mock 입력:** recording/search/readout/case의 계약 JSON과 AssetFacts. 원본 46 JSON/7 Scenario는 수정하지 않았다. H의 공용 `NOT_ASKED` 경로는 specific renderer에서 차단한다.
- **evidence 전용 case context:** H의 specific Package 성공 경로에는 `CONFIRMED`, U의 snapshot에는 `USER_UNSURE`의 전체 필드를 test-derived 입력으로 명시한다. 공용 case 원본과 동일하다고 주장하지 않는다.
- **evidence 전용 Mock:** 신고영상 내부 번호판·시각 가시성 fact. 문자열 값만으로 가시성 PASS를 만들지 않도록 subject refs가 있는 별도 관찰로 주입한다.
- **Consumer Mock:** 공개 Contract JSON만 읽어 current head와 두 gate를 계산한다. CaseView를 만들거나 case 정책을 재구현하지 않으며 `USER_REVIEWED`는 산출하지 않는다.
- **Fixture 비교:** 실제 baseline 처리 후 상태/overall을 공용 evidence JSON과 비교한다. `scenario_id`별 canned output 재생을 처리 구현의 증거로 사용하지 않는다.

공개 사용자는 `daesingo.evidence`에서 순수 함수를 import하고 Final Contract payload를 직접 넘긴다. 자세한 함수 목록과 명령은 [`src/daesingo/evidence/README.md`](../../../src/daesingo/evidence/README.md)에 있다. Mock adapter의 `scenario_id`, 출력 ID, 평가 시각, rule 목록은 [`tests/evidence/fixtures/adapter_inputs.json`](../../../tests/evidence/fixtures/adapter_inputs.json)에만 있으며 Runtime 필드가 아니다.

## 체크리스트 추적표

| 체크리스트 위치/항목 | 구현·검증 위치 | 증빙 | 상태 | 남은 일/담당 |
| --- | --- | --- | --- | --- |
| 회의 핵심·Input·Core Flow: H/U/P/R 계약 입력과 차이 보존 | `mock_integration.py`, `assembly.py`, `time_resolution.py` / `test_mock_integration.py` | 네 Scenario baseline JSON의 `input_trace`, `outputs`, `comparison` | Mock 연결 검증 완료 | 실제 case 호출은 유소연 통합 대기 |
| Output Contract: 다섯 Contract와 ref/provenance/timeline | `validation.py`, `assembly.py` / `test_contract_validation.py` | 모든 생성 Contract validator 통과; artifact의 timeline revision/range | 검증 완료 | validator는 전체 JSON Schema·Owner 수락을 뜻하지 않음 |
| Failure/Partial: UNKNOWN/BLOCK/실패/ready-only | `requirements.py`, `errors.py` / `test_contract_units.py` | UNKNOWN/BLOCK 구분, 누락·불가 자산, 조립 실패, policy data 부재 시 미발행 검사 | 검증 완료 | 실행 lifecycle은 case/runtime 범위 |
| State/Lifecycle: immutable snapshot·supersede·selection_rev | `time_resolution.py`, `assembly.py`, `corrections.py` / 두 test 파일 | P/R 전후 JSON 및 literal 비교 | 검증 완료 | 실제 저장소 durability는 범위 밖 |
| TimeResolution 상세 | `time_resolution.py` / Scenario·UNKNOWN 단위 검사 | H/P OK, U/R-v1 NEEDS_REVIEW, R-v2 USER_OVERRIDE; no-source UNKNOWN | 검증 완료 | Q3은 기존 provenance ref로 추적 |
| EvidenceRecord 상세·초기 4종 매핑 | `assembly.py`, `policy_data.json` / renderer·correction 단위 검사 | U null+USER_UNSURE, R correction ref, 4종 mapping/길이 | 검증 완료 | 실영상 AI 정확도는 미검증 |
| EvidenceNeeds 상세 | `calculate_evidence_needs` / P Scenario 검사 | 첫 basis `ev_p001`, PLATE_REREAD; v2 basis와 빈 items | 검증 완료 | 재발주 변환은 case 담당 |
| RequirementReport 두 scope·우선순위 | `requirements.py` / Scenario·단위 검사 | H PASS/PASS, U WARN/WARN, P UNKNOWN→PASS, R WARN→PASS; precedence | 검증 완료 | 용량·기한 수치 정책은 결정 대기 |
| ReportPackage ready-only·template·optional plate image·lineage | `requirements.py`, `policy.py` / H·단위 검사 | H NOT_ASKED 차단 + derived CONFIRMED Package, U 미발행, optional plate image 생략, supersede ref | 정책 guard 및 Mock 연결 검증 완료 | 실제 H confirmation 전달은 case 통합 대기; U 정상 Package는 Q1; 공용 문구는 Q2 동기화 대기 |
| Integration: Consumer가 공개 출력 읽기 | `consume_contracts` / Scenario 검사 | 각 baseline JSON의 `consumer_mock` | Mock 연결 검증 완료 | 실제 CaseView projection은 유소연 통합 대기 |
| Operational: revision·정책·Mock 범위·재현 | CLI, artifact, 이 문서 | `base_revision`, `execution_mode`, source paths, 아래 명령 | 검증 완료 | 커밋 SHA는 커밋 후 갱신 가능 |
| Product Spec의 첨부 용량·신고기한 | `requirements.py`의 명시적 policy gap | `PolicyConfigurationError` 단위 검사 | 정책 결정 완료, Runtime 연결 미완료 | K1·K2·K3 `ACCEPTED`; `deadline_policy_v1.json`·`requirement_rules_v2.json` 작성 완료. evaluator 연결 필요 |

체크리스트 원문의 체크박스는 일괄 변경하지 않았다. 위 표의 “검증 완료”는 해당 코드/Contract 단위에 한정하며 공용 E2E, production, Consumer Owner 수락으로 확대하지 않는다.

## Q1·Q2·Q3 및 후속 작업

| 항목 | 최신 확인 | 영향 | 필요한 조치 / 담당 |
| --- | --- | --- | --- |
| Q1 U의 `report_inputs.location=null` | 현재 공용 U Package와 Final의 필수 location 객체가 여전히 충돌한다 | U Evidence/Requirement는 처리했지만 정상 Package baseline은 `package.input.location_missing`으로 보류 | **Contract 변경 검토 필요**. nullable/placeholder/새 필드를 임의 추가하지 않고 Contract Owner 협의 후 공용 Fixture 동기화 |
| Q2 H/U 문구·Template·policy provenance | `safety-report-policy-v1.md`는 확정됐으나 공용 Package는 옛 문구와 `policy/package-assembly-v1`을 보유한다 | H baseline은 확정 renderer와 `safety-report-policy/v1`; U renderer는 단위 검증만 가능 | evidence 구현은 완료, 공용 Fixture 동기화는 Mock Pack 담당/관련 Owner 대기 |
| Q3 timeline revision 직접 필드 | TimeResolution에 새 직접 필드는 확정되지 않았다 | CandidateEvent span과 IncidentClip provenance의 timeline ref/revision/range로 사용 입력 추적 가능 | 비차단 후속. 새 필드 없이 현 경로 유지; Contract 변경 시 반영 |
| 용량·기한 baseline | 채택된 제한값/계산 규칙을 현재 Final/정책에서 찾을 수 없다 | 수치를 요구하는 rule은 정상 Report를 만들지 않고 configuration error | 김준영 정책 결정과 근거 문서가 필요. Fixture `180` 등 임의 수치 승격 금지 |
| 실제 Consumer | 현재 `case` 공개 실행 구현은 골격이며 실제 projection 호출 경로가 없다 | Contract reader Mock까지만 입증 | 유소연이 실제 case 입력 경계/CaseView projection을 구현한 뒤 동일 artifact로 접합 확인 |

## 재현 명령과 검증 범위

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py' -v
python -m daesingo.evidence.mock_integration
python -m ruff check src/daesingo/evidence tests/evidence
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
git diff --check
```

시작 상태와 최종 상태에서 공용 검증은 각각 `46 JSON / 7 Scenario, 0 errors`, `structure 60 / JSON 26 / semantic 104 PASS`, boundary `0 violations`였다. 최종 evidence 검사는 `21 tests OK`, Ruff `All checks passed`, compileall 성공, `git diff --check` 성공이다. 품질 검토 중 AssetFacts `availability=UNKNOWN`과 `UNAVAILABLE`의 outcome 분리, CorrectionRecord chain 검증, RFC3339·candidate ref 경계와 specific/generic template confirmation guard를 보강한 뒤 전체 검사를 다시 실행했다. 공용 validator PASS는 baseline 의미 정확성, 실제 Consumer E2E, AI/OCR 정확도, Owner 수락을 증명하지 않는다.

## 인수인계

유소연 `case` Consumer는 같은 `case_id`/`selection_rev`의 선택된 CandidateEvent, VisualEvidence, time/readout 입력, CorrectionRecord, IncidentClip/AssetFacts를 공개 함수에 전달하고 반환된 opaque refs를 그대로 저장·projection하면 된다. P의 `PLATE_REREAD`를 실제 `PLATE_READ` Job으로 바꾸고 stale Need를 제거하는 책임, `USER_REVIEWED` 판정, CaseView head 선택은 case에 남는다. evidence는 readout/runtime/export를 호출하지 않는다.

검토 시 우선 볼 파일은 `run-summary.json` → 각 Scenario baseline → `test_mock_integration.py` → `test_contract_units.py` 순서다. U Package를 0건으로 둔 것은 실패 은폐가 아니라 Final 위반 Package 발행을 차단한 결과다.
