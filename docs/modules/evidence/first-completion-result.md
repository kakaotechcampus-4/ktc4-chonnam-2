# evidence 1차 Mock 통합 수행 결과

> 상태: **PARTIAL_READY**
>
> 최신 실행 기준: branch `feature/evidence-location-nullable`, 구현 기준 커밋 `427ebb980361f7b2d41f6024e476a5269f7d91bc`, 실행일 `2026-09-14`
>
> 기준 계약/정책: `time-resolution/v1`, `evidence-record/v1.3`, `evidence-needs/v1`, `requirement-report/v1`, `report-package/v1.1`, `correction-record/v1.1`, `policy/requirement-rules-v3`, `safety-report-policy/v1.1`

원본 [`first-completion-checklist.md`](first-completion-checklist.md)의 완료 정의와 작성 시점은 수정하지 않았다. 이 문서는 수행 결과만 별도로 연결한다. production/runtime 완성, 실제 AI·OCR·영상 생성, 외부 제출, 실제 `case`/web projection은 이 결과가 증명하지 않는다.

> **반영 대기 결정 (2026-09-14).** [`ADR-EVIDENCE-005`](adr/adr-event-context-rules-removal.md)가 `FINAL_PACKAGE`의 사건 장면·전 상황·후 상황 세 rule을 제거하기로 확정했다. **아래 표는 그 반영 이전의 실행 결과다.** 반영 후에는 활성 catalog가 `policy/requirement-rules-v4`(무조건 rule 12개)가 되고 H는 `PASS`·U는 `WARN`으로 두 Package가 발행된다. 반영 범위는 같은 ADR §12, 확인 항목은 §9다. **그 전까지 아래 「Package 0건」은 현재 사실이며 지우지 않는다.**

## 실행 결과 요약

| Scenario | baseline 결과 | Consumer Mock 판독 | 판정 |
| --- | --- | --- | --- |
| H `scenario_happy_001` | Time `OK`; Evidence `ev_h001`; Requirement `PASS/UNKNOWN`; 신규 사건·전후 상황 관찰 fact 3종 부재로 Package 0건 | `EVIDENCE_SUFFICIENT=true`, `PACKAGE_READY=false`; `USER_REVIEWED=CASE_OWNED_NOT_DERIVED` | v3 catalog 연결 검증 완료. **Package 0건의 원인인 세 rule은 ADR-005로 제거 확정** — v4 반영 시 `PASS`·Package 발행 |
| U `scenario_unknown_abstain_partial_001` | Time `NEEDS_REVIEW`; visual type `null`; `USER_UNSURE`; Requirement `WARN/UNKNOWN`; 신규 사건·전후 상황 관찰 fact 3종 부재로 Package 0건 | Evidence gate만 true, Package gate false | 공용 입력 보존 결과. 별도 D1 test-derived 입력은 `WARN`·`pkg_u001_d1_unit` 발행 검증 완료. **ADR-005 반영 시 공용 U에서 `WARN`·`pkg_u001` 발행** — D1 증명이 test-derived 입력에 의존하지 않게 된다 |
| P `scenario_plate_reread_001` | `ev_p001` 번호판 부재 + `PLATE_REREAD` + UNKNOWN → `ev_p001_v2` 번호판 `17나2867` + 빈 Needs + Requirement `WARN` | 현재 Evidence는 v2, Package 없음 | v3 EVIDENCE catalog 연결 검증 완료(Package는 Scenario 범위 밖) |
| R `scenario_correction_rerun_001` | Time `NEEDS_REVIEW` → `OK/AGREED/USER_OVERRIDE`; Evidence/Requirement supersede; Requirement `WARN/WARN`; 번호판 `34나7890`·basis·`selection_rev=1` 보존 | 현재 Evidence/Requirement는 v2, Package 없음 | v3 EVIDENCE catalog 연결 검증 완료(Package는 Scenario 범위 밖) |

고정 출력은 [`artifacts/first-completion/run-summary.json`](artifacts/first-completion/run-summary.json)과 같은 폴더의 네 `*.baseline.json`이다. 각 파일은 원본 recording/search/readout/case JSON 경로, candidate Fine run, timeline revision/range, correction refs, 실제 출력 다섯 배열, 공용 evidence Fixture와의 비교, Consumer Mock 판독을 함께 기록한다.

## 처리 경계

- **실제 baseline 처리:** 시간 source 우선순위/offset/충돌, Evidence 조립, CorrectionRecord head와 타입 검증 및 반영, declarative Needs, 활성 catalog 기반 두 scope rule 선택, K1 첨부·K2 기한 평가, deterministic report rendering, ready-only Package 조립.
- **공용 Mock 입력:** recording/search/readout/case의 계약 JSON과 AssetFacts. 원본 46 JSON/7 Scenario는 수정하지 않았다. H의 공용 `NOT_ASKED` 경로는 specific renderer에서 차단한다.
- **evidence 전용 case context:** H의 specific Package 성공 경로에는 `CONFIRMED`, U의 snapshot에는 `USER_UNSURE`의 전체 필드를 test-derived 입력으로 명시한다. 공용 case 원본과 동일하다고 주장하지 않는다.
- **관찰 fact 경계:** 공용 H/U/P/R에 없는 사건 장면·전 상황·후 상황 fact를 adapter가 만들지 않는다. D1 Package 성공은 세 값을 명시한 단위 테스트 입력에서만 확인한다. 문자열 값만으로 가시성 PASS를 만들지 않는다. **ADR-005 반영 후에는 세 rule과 세 입력 key가 사라지므로 이 경계는 번호판·시각 표시·사후 각인 세 fact에만 적용된다.**
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
| RequirementReport 두 scope·우선순위 | `requirements.py`, `policy_catalog.py`, `deadline.py` / Scenario·정책 단위 검사 | EVIDENCE 4개, FINAL 15+조건부 1개; K1 경계·K2 날짜·precedence | 검증 완료 | 사건·전후 상황의 실제 관찰 전달은 I4 대기 |
| ReportPackage ready-only·template·optional plate image·lineage | `requirements.py`, `policy.py`, `validation.py` / D1·계약 단위 검사 | `location:null`, no-location template, v1.1 validator, optional plate image, supersede ref | 검증 완료 | 공용 fixture 재렌더와 case 고지/field state는 I2·case 담당 |
| Integration: Consumer가 공개 출력 읽기 | `consume_contracts` / Scenario 검사 | 각 baseline JSON의 `consumer_mock` | Mock 연결 검증 완료 | 실제 CaseView projection은 유소연 통합 대기 |
| Operational: revision·정책·Mock 범위·재현 | CLI, artifact, 이 문서 | `base_revision`, `execution_mode`, source paths, 아래 명령 | 검증 완료 | 커밋 SHA는 커밋 후 갱신 가능 |
| K1 첨부 용량·개수 | `attachment_policy_v1.json`, `requirements.py` | exact limit·1 byte 초과·null·부분합·dedup·개수·구성 오류 | 정책 엔진 반영 및 단위 검증 완료 | 실제 외부 제한 변경은 새 policy version 필요 |
| K2 신고기한 | `deadline_policy_v1.json`, `deadline.py` | 평일·금요일·연속 공휴일·연말·exclusive 경계·coverage 오류 | 정책 엔진 반영 및 단위 검증 완료 | 2028 이후 calendar revision 필요 |
| K3 rule catalog | `requirement_rules_v3.json`, `policy_catalog.py`, `requirements.py` | scope 수·조건부 selector 네 갈래·malformed catalog·출력 policy_ref | 활성 v3 연결 및 검증 완료 | v2는 채택 후 첫 실행 전 대체된 revision으로 보존 |
| K4 correction provenance | `source-kind-registry.md` v2, `assembly.py` / correction 단위 검사 | 비시각 9개 path의 kind/ref/OBSERVED/null label/user flags, 파생값 INFERRED, occurred_at 무변경 | registry 추인 및 단위 검증 완료 | 실제 Consumer 검증은 I7·I8 대기 |
| D1 위치 없는 Package | 계약 v1.1, 신고문 정책 v1.1, catalog v3, package/validator 구현 | 위치 null Package와 장소 없는 template, 두 catalog 변경의 결합 필요성 | 네 층 반영 및 단위 검증 완료 | 공용 U의 Package 미발행은 D1이 아니라 사건 장면·전후 상황 rule 때문이다 → ADR-005로 제거 확정; I2 대기 |

체크리스트 원문의 체크박스는 일괄 변경하지 않았다. 위 표의 “검증 완료”는 해당 코드/Contract 단위에 한정하며 공용 E2E, production, Consumer Owner 수락으로 확대하지 않는다.

## Q1·Q2·Q3 및 후속 작업

| 항목 | 최신 확인 | 영향 | 필요한 조치 / 담당 |
| --- | --- | --- | --- |
| Q1 U의 `report_inputs.location=null` | **종결.** ADR-EVIDENCE-003에 따라 `report-package/v1.1`에서 키 필수·값 nullable이며 위치 부재는 WARN이다 | D1 단위 경로에서 정상 Package가 발행된다 | evidence 네 층 반영 완료. `CaseView.report_field_states.location`, 고지 code, 공용 fixture 재렌더는 case/I2 담당 |
| Q2 H/U 문구·Template·policy provenance | `safety-report-policy/v1.1`과 장소 없는 template을 발행했다 | 새 Package는 선택 template과 v1.1 policy ref를 보존한다 | evidence 구현 완료, 공용 Fixture 동기화는 I2 담당 |
| Q3 timeline revision 직접 필드 | TimeResolution에 새 직접 필드는 확정되지 않았다 | CandidateEvent span과 IncidentClip provenance의 timeline ref/revision/range로 사용 입력 추적 가능 | 비차단 후속. 새 필드 없이 현 경로 유지; Contract 변경 시 반영 |
| 공용 H/U Package baseline | **원인 확정.** 위치 결론(D1)은 종결됐고 Package 0건의 원인은 사건 장면·전후 상황 rule 3건이다. 이 rule들은 판정 주체가 제품 안에 없어 영구 `UNKNOWN`이었다 | 정직한 재실행은 FINAL_PACKAGE `UNKNOWN`, Package 0건이다 | **[`ADR-EVIDENCE-005`](adr/adr-event-context-rules-removal.md)가 세 rule 제거를 확정했다.** catalog v4 반영이 필요한 조치이며(같은 ADR §12) I4 관찰 전달 확장은 취소됐다. 반영 후 I2 fixture 재렌더 |
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

2026-09-14 구현 검증에서 evidence `41 tests OK`, Ruff `All checks passed`, compileall 성공을 확인했다. 공용 검증은 `46 JSON / 7 Scenario`, `structure 60 / JSON 26 / semantic 104 PASS`, boundary `0 violations`였고 `git diff --check`도 통과했다. Artifact에는 활성 `policy/requirement-rules-v3`만 있고 v2 ref는 0건이다. 공용 validator PASS는 baseline 의미 정확성, 실제 Consumer E2E, AI/OCR 정확도, Owner 수락을 증명하지 않는다.

## 인수인계

유소연 `case` Consumer는 같은 `case_id`/`selection_rev`의 선택된 CandidateEvent, VisualEvidence, time/readout 입력, CorrectionRecord, IncidentClip/AssetFacts를 공개 함수에 전달하고 반환된 opaque refs를 그대로 저장·projection하면 된다. P의 `PLATE_REREAD`를 실제 `PLATE_READ` Job으로 바꾸고 stale Need를 제거하는 책임, `USER_REVIEWED` 판정, CaseView head 선택은 case에 남는다. evidence는 readout/runtime/export를 호출하지 않는다.

검토 시 우선 볼 파일은 `run-summary.json` → 각 Scenario baseline → `test_policy_decisions.py` → `test_mock_integration.py` → `test_contract_units.py` 순서다. 공용 U Package를 0건으로 둔 것은 위치 null을 차단한 결과가 아니라, 입력에 없는 신규 사건·전후 상황 관찰 사실을 만들어내지 않아 FINAL_PACKAGE가 `UNKNOWN`인 결과다.
